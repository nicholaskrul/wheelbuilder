import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import math
from datetime import datetime

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="ProWheel Lab v6.7", layout="wide", page_icon="🚲")

# --- 2. GOOGLE SHEETS CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_worksheet_data(sheet_name):
    # ttl=0 ensures live data fetching from Google Sheets
    return conn.read(worksheet=sheet_name, ttl=0)

# --- 3. PRECISION CALCULATION LOGIC ---
def calculate_precision_spoke(erd, fd, os, holes, crosses, is_sp, sp_offset, hole_diam=2.5):
    if 0 in [erd, fd, holes]: return 0.0
    r_rim, r_hub = erd / 2, fd / 2
    
    if not is_sp:
        # J-Bend: Law of Cosines + Flange Hole Correction for ProWheelBuilder parity
        alpha_rad = math.radians((crosses * 720.0) / holes)
        length_sq = (r_rim**2) + (r_hub**2) + (os**2) - (2 * r_rim * r_hub * math.cos(alpha_rad))
        length = math.sqrt(max(0, length_sq)) - (hole_diam / 2)
    else:
        # Straightpull: Tangential Exit + Spoke Offset (K-Value) for DT Swiss parity
        d_tangent_2d = math.sqrt(max(0, r_rim**2 - r_hub**2))
        length = math.sqrt(d_tangent_2d**2 + os**2) + sp_offset
        
    return round(length, 1)

# Initialize session state for staging lengths across tabs
if 'staged_lengths' not in st.session_state:
    st.session_state.staged_lengths = {"f_l": 0.0, "f_r": 0.0, "r_l": 0.0, "r_r": 0.0}

# --- 4. MAIN USER INTERFACE ---
st.title("🚲 ProWheel Lab: Master Workshop v6.7")
st.markdown("---")

tabs = st.tabs(["📊 Dashboard", "🧮 Precision Calc", "📦 Component Library", "➕ Register Build"])

# --- TAB: DASHBOARD ---
with tabs[0]:
    st.subheader("🏁 Workshop Pipeline")
    try:
        df_builds = get_worksheet_data("builds")
        if not df_builds.empty:
            st.dataframe(df_builds, use_container_width=True, hide_index=True)
        else:
            st.info("No builds found. Populate your Library and Register a Build.")
    except Exception as e:
        st.error(f"Connect to 'builds' tab failed: {e}")

# --- TAB: PRECISION CALC ---
with tabs[1]:
    st.header("🧮 Precision Calculator")
    calc_mode = st.radio("Data Source", ["Use Library", "Manual Entry"], horizontal=True)
    
    try:
        df_rims = get_worksheet_data("rims")
        df_hubs = get_worksheet_data("hubs")

        if calc_mode == "Use Library" and not df_rims.empty and not df_hubs.empty:
            c1, c2 = st.columns(2)
            rim_choice = c1.selectbox("Select Rim", df_rims['brand'] + " " + df_rims['model'])
            hub_choice = c2.selectbox("Select Hub", df_hubs['brand'] + " " + df_hubs['model'])

            sel_r = df_rims[(df_rims['brand'] + " " + df_rims['model']) == rim_choice].iloc[0]
            sel_h = df_hubs[(df_hubs['brand'] + " " + df_hubs['model']) == hub_choice].iloc[0]

            c_erd, c_holes = sel_r['erd'], sel_r['holes']
            l_fd, r_fd = sel_h['fd_l'], sel_h['fd_r']
            l_os, r_os = sel_h['os_l'], sel_h['os_r']
            l_sp, r_sp = sel_h['sp_off_l'], sel_h['sp_off_r']
        else:
            m1, m2 = st.columns(2)
            c_erd = m1.number_input("Rim ERD (mm)", value=601.0)
            c_holes = m2.number_input("Hole Count", value=28)
            l_fd, r_fd = m1.number_input("Left PCD", 40.8), m2.number_input("Right PCD", 36.0)
            l_os, r_os = m1.number_input("Left Offset", 28.0), m2.number_input("Right Offset", 40.2)
            l_sp, r_sp = m1.number_input("Left SP Offset", 1.7), m2.number_input("Right SP Offset", 1.8)

        st.divider()
        is_sp = st.toggle("Straightpull Hub Geometry?", value=True)
        h_diam = st.slider("Hub Spoke Hole Diameter (mm)", 2.0, 3.0, 2.5)
        l_cross = st.selectbox("Left Cross Pattern", [0,1,2,3], index=3)
        r_cross = st.selectbox("Right Cross Pattern", [0,1,2,3], index=3)

        col_l, col_r = st.columns(2)
        res_l = calculate_precision_spoke(c_erd, l_fd, l_os, c_holes, l_cross, is_sp, l_sp, h_diam)
        res_r = calculate_precision_spoke(c_erd, r_fd, r_os, c_holes, r_cross, is_sp, r_sp, h_diam)
        
        col_l.metric("Left Spoke Length", f"{res_l} mm")
        col_r.metric("Right Spoke Length", f"{res_r} mm")

        # --- STAGING SECTION ---
        st.divider()
        st.subheader("🛠️ Save Calculation to Build")
        wheel_pos = st.radio("Is this for the Front or Rear wheel?", ["Front", "Rear"], horizontal=True)
        
        if st.button("Stage Lengths for Build"):
            if wheel_pos == "Front":
                st.session_state.staged_lengths["f_l"] = res_l
                st.session_state.staged_lengths["f_r"] = res_r
            else:
                st.session_state.staged_lengths["r_l"] = res_l
                st.session_state.staged_lengths["r_r"] = res_r
            st.success(f"Lengths saved! Finalize in the 'Register Build' tab.")

    except Exception as e:
        st.error(f"Error: {e}")

# --- TAB: COMPONENT LIBRARY ---
with tabs[2]:
    st.header("📦 Library Management")
    l1, l2, l3 = st.columns(3)
    
    with l1:
        st.subheader("Add Rim/Hub")
        sub_tab = st.selectbox("Select Component", ["Rim", "Hub"])
        if sub_tab == "Rim":
            with st.form("rim_f", clear_on_submit=True):
                rb, rm = st.text_input("Brand"), st.text_input("Model")
                re, rh = st.number_input("ERD", step=0.1), st.number_input("Holes", 28)
                if st.form_submit_button("Save Rim"):
                    new_rim = pd.DataFrame([{"brand": rb, "model": rm, "erd": re, "holes": rh}])
                    conn.update(worksheet="rims", data=pd.concat([get_worksheet_data("rims"), new_rim], ignore_index=True))
                    st.success("Rim Saved!")
        else:
            with st.form("hub_f", clear_on_submit=True):
                hb, hm = st.text_input("Brand"), st.text_input("Model")
                hfl, hol, hsl = st.number_input("L-PCD"), st.number_input("L-Dist"), st.number_input("L-SP Off")
                hfr, hor, hsr = st.number_input("R-PCD"), st.number_input("R-Dist"), st.number_input("R-SP Off")
                if st.form_submit_button("Save Hub"):
                    new_hub = pd.DataFrame([{"brand": hb, "model": hm, "fd_l": hfl, "fd_r": hfr, "os_l": hol, "os_r": hor, "sp_off_l": hsl, "sp_off_r": hsr}])
                    conn.update(worksheet="hubs", data=pd.concat([get_worksheet_data("hubs"), new_hub], ignore_index=True))
                    st.success("Hub Saved!")

    with l2:
        st.subheader("Add Spokes")
        with st.form("spoke_f", clear_on_submit=True):
            sb, sm = st.text_input("Spoke Brand"), st.text_input("Model")
            sw = st.number_input("Weight per spoke (g)", step=0.01)
            if st.form_submit_button("Save Spoke"):
                new_spoke = pd.DataFrame([{"brand": sb, "model": sm, "weight_per_spoke": sw}])
                conn.update(worksheet="spokes", data=pd.concat([get_worksheet_data("spokes"), new_spoke], ignore_index=True))
                st.success("Spoke Saved!")

    with l3:
        st.subheader("Add Nipples")
        with st.form("nipple_f", clear_on_submit=True):
            nb, nm = st.text_input("Nipple Brand"), st.text_input("Model")
            nw = st.number_input("Weight per nipple (g)", step=0.01)
            if st.form_submit_button("Save Nipple"):
                new_nipple = pd.DataFrame([{"brand": nb, "model": nm, "weight_per_nipple": nw}])
                conn.update(worksheet="nipples", data=pd.concat([get_worksheet_data("nipples"), new_nipple], ignore_index=True))
                st.success("Nipple Saved!")

# --- TAB: REGISTER BUILD ---
with tabs[3]:
    st.header("Finalize Build Record")
    try:
        df_builds = get_worksheet_data("builds")
        df_rims = get_worksheet_data("rims")
        df_hubs = get_worksheet_data("hubs")
        df_spokes = get_worksheet_data("spokes")
        df_nipples = get_worksheet_data("nipples")

        build_type = st.radio("Action", ["Create New Build", "Update Existing Build"], horizontal=True)

        with st.form("build_final_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            if build_type == "Create New Build":
                cust = c1.text_input("Customer Name")
            else:
                cust = c1.selectbox("Select Existing Build", df_builds['customer'])
            
            status = c2.selectbox("Stage", ["Order Received", "Parts Ordered", "Parts Received", "Build Complete"])
            
            sel_r = st.selectbox("Assign Rim", df_rims['brand'] + " " + df_rims['model'])
            sel_h = st.selectbox("Assign Hub", df_hubs['brand'] + " " + df_hubs['model'])
            sel_s = st.selectbox("Assign Spokes", df_spokes['brand'] + " " + df_spokes['model'])
            sel_n = st.selectbox("Assign Nipples", df_nipples['brand'] + " " + df_nipples['model'])

            st.write("Confirm Staged Spoke Lengths:")
            sc1, sc2, sc3, sc4 = st.columns(4)
            vfl = sc1.number_input("Front Left", value=st.session_state.staged_lengths["f_l"])
            vfr = sc2.number_input("Front Right", value=st.session_state.staged_lengths["f_r"])
            vrl = sc3.number_input("Rear Left", value=st.session_state.staged_lengths["r_l"])
            vrr = sc4.number_input("Rear Right", value=st.session_state.staged_lengths["r_r"])
            
            notes = st.text_area("Workshop Notes")
            
            if st.form_submit_button("Update Google Sheet"):
                new_entry = {"customer": cust, "status": status, "date_added": datetime.now().strftime("%Y-%m-%d"), 
                             "rim": sel_r, "hub": sel_h, "spoke": sel_s, "nipple": sel_n,
                             "f_l_len": vfl, "f_r_len": vfr, "r_l_len": vrl, "r_r_len": vrr, "notes": notes}
                
                if build_type == "Update Existing Build":
                    df_final = pd.concat([df_builds[df_builds['customer'] != cust], pd.DataFrame([new_entry])], ignore_index=True)
                else:
                    df_final = pd.concat([df_builds, pd.DataFrame([new_entry])], ignore_index=True)
                
                conn.update(worksheet="builds", data=df_final)
                st.success("Database Updated!")
                st.rerun()
    except Exception as e:
        st.warning("Please ensure all library tabs (rims, hubs, spokes, nipples) have at least one entry.")
