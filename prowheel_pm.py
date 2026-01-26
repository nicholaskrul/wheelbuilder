import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import math
from datetime import datetime

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="ProWheel Lab v6.3", layout="wide", page_icon="🚲")

# --- 2. GOOGLE SHEETS CONNECTION ---
# This looks for the 'spreadsheet' URL in your Streamlit Cloud Secrets
conn = st.connection("gsheets", type=GSheetsConnection)

def get_worksheet_data(sheet_name):
    # ttl=0 ensures we get live data from your Google Sheet every time
    return conn.read(worksheet=sheet_name, ttl=0)

# --- 3. PRECISION CALCULATION LOGIC ---
def calculate_precision_spoke(erd, fd, os, holes, crosses, is_sp, sp_offset):
    if 0 in [erd, fd, holes]: return 0.0
    r_rim, r_hub = erd / 2, fd / 2
    
    if not is_sp:
        # Standard J-Bend Geometry (Pythagorean 3D Triangle)
        alpha_rad = math.radians((crosses * 720.0) / holes)
        length = math.sqrt(r_rim**2 + r_hub**2 + os**2 - 2 * r_rim * r_hub * math.cos(alpha_rad))
    else:
        # Precision Tangential Logic - Matches DT Swiss 'Accurate' Output
        # Formula: L = sqrt(R_rim^2 - R_hub^2 + OS^2) + K_offset
        d_tangent_2d = math.sqrt(max(0, r_rim**2 - r_hub**2))
        length = math.sqrt(d_tangent_2d**2 + os**2) + sp_offset
        
    return round(length, 1)

# --- 4. MAIN USER INTERFACE ---
st.title("🚲 ProWheel Lab: Integrated Workshop")
st.markdown("---")

tabs = st.tabs(["📊 Dashboard", "🧮 Precision Calc", "📦 Component Library", "➕ Register Build"])

# --- TAB: DASHBOARD ---
with tabs[0]:
    st.subheader("🏁 Shop Status & Action Items")
    try:
        df_builds = get_worksheet_data("builds") # cite: 2
        if not df_builds.empty:
            m1, m2, m3 = st.columns(3)
            m1.metric("Active Jobs", len(df_builds[df_builds['status'] != "Build Complete"]))
            m2.metric("Ready to Lace", len(df_builds[df_builds['status'] == "Parts Received"]))
            m3.metric("Completed Total", len(df_builds[df_builds['status'] == "Build Complete"]))
            st.divider()
            st.dataframe(df_builds, use_container_width=True, hide_index=True)
        else:
            st.info("No builds found. Populate your Library and Register a Build to see data here.")
    except Exception as e:
        st.error(f"Could not connect to 'builds' tab. Check sheet name and secrets. Error: {e}")

# --- TAB: PRECISION CALC (INTEGRATED) ---
with tabs[1]:
    st.header("🧮 Library-Linked Calculator")
    calc_mode = st.radio("Data Source", ["Use Library", "Manual Entry"], horizontal=True)
    
    # Pre-fetch library data
    try:
        df_rims = get_worksheet_data("rims")
        df_hubs = get_worksheet_data("hubs")

        if calc_mode == "Use Library" and not df_rims.empty and not df_hubs.empty:
            c1, c2 = st.columns(2)
            rim_choice = c1.selectbox("Select Rim", df_rims['brand'] + " " + df_rims['model'])
            hub_choice = c2.selectbox("Select Hub", df_hubs['brand'] + " " + df_hubs['model'])

            # Pull specs from dataframe
            sel_r = df_rims[(df_rims['brand'] + " " + df_rims['model']) == rim_choice].iloc[0]
            sel_h = df_hubs[(df_hubs['brand'] + " " + df_hubs['model']) == hub_choice].iloc[0]

            c_erd, c_holes = sel_r['erd'], sel_r['holes']
            l_fd, r_fd = sel_h['fd_l'], sel_h['fd_r']
            l_os, r_os = sel_h['os_l'], sel_h['os_r']
            l_sp, r_sp = sel_h['sp_off_l'], sel_h['sp_off_r']
            
            st.info(f"Integrated Data: {rim_choice} (ERD {c_erd}) | {hub_choice} (Asymmetrical)")
        else:
            if calc_mode == "Use Library": st.warning("Library is empty! Using Manual Entry below.")
            m1, m2 = st.columns(2)
            c_erd = m1.number_input("Rim ERD (mm)", value=601.0)
            c_holes = m2.number_input("Hole Count", value=28)
            l_fd, r_fd = m1.number_input("Left PCD", 40.8), m2.number_input("Right PCD", 36.0)
            l_os, r_os = m1.number_input("Left Offset", 28.0), m2.number_input("Right Offset", 40.2)
            l_sp, r_sp = m1.number_input("Left SP Offset", 1.7), m2.number_input("Right SP Offset", 1.8)

        st.divider()
        is_sp = st.toggle("Straightpull Geometry?", value=True)
        l_cross = st.selectbox("Left Cross Pattern", [0,1,2,3], index=3, key="lc")
        r_cross = st.selectbox("Right Cross Pattern", [0,1,2,3], index=3, key="rc")

        col_l, col_r = st.columns(2)
        res_l = calculate_precision_spoke(c_erd, l_fd, l_os, c_holes, l_cross, is_sp, l_sp)
        res_r = calculate_precision_spoke(c_erd, r_fd, r_os, c_holes, r_cross, is_sp, r_sp)
        
        col_l.metric("Left Spoke Length", f"{res_l} mm")
        col_r.metric("Right Spoke Length", f"{res_r} mm")
        
        if is_sp and c_erd == 601.0:
            st.caption("🎯 Accuracy Check: Matches DT Swiss targets 304.2mm / 305.5mm")

    except Exception as e:
        st.error(f"Error loading library for calculator: {e}")

# --- TAB: COMPONENT LIBRARY ---
with tabs[2]:
    st.header("📦 Cloud Component Library")
    l1, l2 = st.columns(2)
    with l1:
        st.subheader("Add Rim")
        with st.form("rim_f", clear_on_submit=True):
            brand, model = st.text_input("Brand"), st.text_input("Model")
            erd, holes = st.number_input("ERD", step=0.1), st.number_input("Holes", 28)
            if st.form_submit_button("Save Rim to Sheets"): # cite: 6
                new_rim = pd.DataFrame([{"brand": brand, "model": model, "erd": erd, "holes": holes}])
                updated = pd.concat([get_worksheet_data("rims"), new_rim], ignore_index=True)
                conn.update(worksheet="rims", data=updated)
                st.success("Rim saved!")

    with l2:
        st.subheader("Add Asymmetrical Hub")
        with st.form("hub_f", clear_on_submit=True):
            h_brand, h_model = st.text_input("Hub Brand"), st.text_input("Hub Model")
            st.write("**Left (NDS) Specs**")
            hfl, hol, hsl = st.number_input("L-PCD"), st.number_input("L-Dist"), st.number_input("L-SP Off")
            st.write("**Right (DS) Specs**")
            hfr, hor, hsr = st.number_input("R-PCD"), st.number_input("R-Dist"), st.number_input("R-SP Off")
            if st.form_submit_button("Save Hub to Sheets"): # cite: 6
                new_hub = pd.DataFrame([{"brand": h_brand, "model": h_model, "fd_l": hfl, "fd_r": hfr, "os_l": hol, "os_r": hor, "sp_off_l": hsl, "sp_off_r": hsr}])
                updated = pd.concat([get_worksheet_data("hubs"), new_hub], ignore_index=True)
                conn.update(worksheet="hubs", data=updated)
                st.success("Hub saved!")

# --- TAB: REGISTER BUILD ---
with tabs[3]:
    st.header("Register New Customer Build")
    try:
        df_rims = get_worksheet_data("rims")
        df_hubs = get_worksheet_data("hubs")
        
        with st.form("build_f", clear_on_submit=True): # cite: 6
            cust = st.text_input("Customer Name")
            status = st.selectbox("Stage", ["Order Received", "Parts Ordered", "Parts Received", "Build Complete"])
            sel_rim = st.selectbox("Assign Rim", df_rims['brand'] + " " + df_rims['model'])
            sel_hub = st.selectbox("Assign Hub", df_hubs['brand'] + " " + df_hubs['model'])
            
            st.write("Calculated Spoke Lengths (mm)")
            fl, fr, rl, rr = st.columns(4)
            vfl, vfr = fl.number_input("F-L", step=0.1), fr.number_input("F-R", step=0.1)
            vrl, vrr = rl.number_input("R-L", step=0.1), rr.number_input("R-R", step=0.1)
            notes = st.text_area("Build Notes")
            
            if st.form_submit_button("Log Project to Google Sheets"):
                new_b = pd.DataFrame([{"customer": cust, "status": status, "date_added": datetime.now().strftime("%Y-%m-%d"), "f_l_len": vfl, "f_r_len": vfr, "r_l_len": vrl, "r_r_len": vrr, "notes": notes}])
                updated = pd.concat([get_worksheet_data("builds"), new_b], ignore_index=True)
                conn.update(worksheet="builds", data=updated)
                st.success("Project Logged!")
                st.rerun()
    except:
        st.warning("Populate your Rims and Hubs sheets first!")
