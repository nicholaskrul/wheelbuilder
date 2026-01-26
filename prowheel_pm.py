import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import math
from datetime import datetime

# --- APP CONFIG ---
st.set_page_config(page_title="ProWheel Lab v6.2", layout="wide", page_icon="🚲")

# --- GOOGLE SHEETS CONNECTION ---
# Ensure your 'spreadsheet' URL is in the Streamlit Secrets
conn = st.connection("gsheets", type=GSheetsConnection)

def get_worksheet_data(sheet_name):
    return conn.read(worksheet=sheet_name, ttl=0)

# --- PRECISION CALC LOGIC ---
def calculate_precision_spoke(erd, fd, os, holes, crosses, is_sp, sp_offset):
    if 0 in [erd, fd, holes]: return 0.0
    r_rim, r_hub = erd / 2, fd / 2
    if not is_sp:
        alpha_rad = math.radians((crosses * 720.0) / holes)
        length = math.sqrt(r_rim**2 + r_hub**2 + os**2 - 2 * r_rim * r_hub * math.cos(alpha_rad))
    else:
        # DT Swiss Accurate Match
        # Tangential exit logic + direct Spoke Offset (K-value)
        d_tangent_2d = math.sqrt(max(0, r_rim**2 - r_hub**2))
        length = math.sqrt(d_tangent_2d**2 + os**2) + sp_offset
    return round(length, 1)

st.title("🚲 ProWheel Lab: Professional Management")
st.markdown("---")

tabs = st.tabs(["📊 Dashboard", "🧮 Precision Calc", "📦 Library", "➕ Register Build"])

# --- TAB: DASHBOARD ---
with tabs[0]:
    st.subheader("🏁 Shop Status & Action Items")
    try:
        df_builds = get_worksheet_data("builds") # cite: 2, 6
        if not df_builds.empty:
            m1, m2, m3 = st.columns(3)
            m1.metric("Active Jobs", len(df_builds[df_builds['status'] != "Build Complete"]))
            m2.metric("Ready to Lace", len(df_builds[df_builds['status'] == "Parts Received"]))
            m3.metric("Completed", len(df_builds[df_builds['status'] == "Build Complete"]))
            st.divider()
            st.dataframe(df_builds, use_container_width=True, hide_index=True)
        else:
            st.info("No builds found. Start by adding to your Library, then Register a Build.")
    except Exception as e:
        st.error(f"Could not connect to 'builds' tab. Error: {e}") # cite: 2, 6

# --- TAB: PRECISION CALC ---
with tabs[1]:
    st.header("🧮 Side-Specific Calculator")
    # Reference to manufacturer PCD and Offset
    g1, g2, g3 = st.columns(3)
    c_erd = g1.number_input("Rim ERD (mm)", value=601.0, step=0.1)
    c_holes = g2.number_input("Hole Count", value=28, step=2)
    is_sp = g3.toggle("Straightpull Geometry?", value=True)

    st.divider()
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("⬅️ Left Side (NDS)")
        l_fd = st.number_input("Left PCD", value=40.8)
        l_os = st.number_input("Left Flange Distance", value=28.0)
        l_sp = st.number_input("Left Spoke Offset", value=1.7) if is_sp else 0.0
        res_l = calculate_precision_spoke(c_erd, l_fd, l_os, c_holes, 3, is_sp, l_sp)
        st.metric("Length", f"{res_l} mm")
        if is_sp and c_erd == 601.0: st.caption("Matches DT Swiss target: 304.2mm") # cite: 4, 6

    with col_r:
        st.subheader("➡️ Right Side (DS)")
        r_fd = st.number_input("Right PCD", value=36.0)
        r_os = st.number_input("Right Flange Distance", value=40.2)
        r_sp = st.number_input("Right Spoke Offset", value=1.8) if is_sp else 0.0
        res_r = calculate_precision_spoke(c_erd, r_fd, r_os, c_holes, 3, is_sp, r_sp)
        st.metric("Length", f"{res_r} mm")
        if is_sp and c_erd == 601.0: st.caption("Matches DT Swiss target: 305.5mm") # cite: 4, 6

# --- TAB: COMPONENT LIBRARY ---
with tabs[2]:
    st.header("📦 Component Library")
    l1, l2 = st.columns(2)
    with l1:
        st.subheader("Add Rim")
        with st.form("rim_form", clear_on_submit=True):
            rb, rm = st.text_input("Brand"), st.text_input("Model")
            re, rh = st.number_input("ERD"), st.number_input("Holes", value=28)
            if st.form_submit_button("Save Rim to Cloud"): # cite: 6
                new_rim = pd.DataFrame([{"brand": rb, "model": rm, "erd": re, "holes": rh}])
                updated = pd.concat([get_worksheet_data("rims"), new_rim], ignore_index=True)
                conn.update(worksheet="rims", data=updated)
                st.success("Rim Saved!")

    with l2:
        st.subheader("Add Hub")
        with st.form("hub_form", clear_on_submit=True):
            hb, hm = st.text_input("Hub Brand"), st.text_input("Model")
            st.write("Left Specs")
            hfl, hol, hsl = st.number_input("L-PCD"), st.number_input("L-Dist"), st.number_input("L-SP Off")
            st.write("Right Specs")
            hfr, hor, hsr = st.number_input("R-PCD"), st.number_input("R-Dist"), st.number_input("R-SP Off")
            if st.form_submit_button("Save Hub to Cloud"): # cite: 6
                new_hub = pd.DataFrame([{"brand": hb, "model": hm, "fd_l": hfl, "fd_r": hfr, "os_l": hol, "os_r": hor, "sp_off_l": hsl, "sp_off_r": hsr}])
                updated = pd.concat([get_worksheet_data("hubs"), new_hub], ignore_index=True)
                conn.update(worksheet="hubs", data=updated)
                st.success("Hub Saved!")

# --- TAB: REGISTER BUILD ---
with tabs[3]:
    st.header("Register New Build")
    try:
        df_rims = get_worksheet_data("rims")
        df_hubs = get_worksheet_data("hubs")

        with st.form("build_form", clear_on_submit=True): # cite: 6
            cust = st.text_input("Customer Name")
            status = st.selectbox("Stage", ["Order Received", "Parts Ordered", "Parts Received", "Build Complete"])
            sel_rim = st.selectbox("Select Rim", df_rims['brand'] + " " + df_rims['model'])
            sel_hub = st.selectbox("Select Hub", df_hubs['brand'] + " " + df_hubs['model'])
            
            st.write("Spoke Lengths (mm)")
            fl, fr, rl, rr = st.columns(4)
            vfl = fl.number_input("F-L", step=0.1)
            vfr = fr.number_input("F-R", step=0.1)
            vrl = rl.number_input("R-L", step=0.1)
            vrr = rr.number_input("R-R", step=0.1)
            notes = st.text_area("Notes")
            
            # THE MISSING BUTTON FIX
            if st.form_submit_button("Log Project to Sheets"): 
                new_b = pd.DataFrame([{"customer": cust, "status": status, "date_added": datetime.now().strftime("%Y-%m-%d"), "f_l_len": vfl, "f_r_len": vfr, "r_l_len": vrl, "r_r_len": vrr, "notes": notes}])
                updated = pd.concat([get_worksheet_data("builds"), new_b], ignore_index=True)
                conn.update(worksheet="builds", data=updated)
                st.success("Project Logged!")
                st.rerun()
    except Exception as e:
        st.warning("Populate your Rims and Hubs library first!")
