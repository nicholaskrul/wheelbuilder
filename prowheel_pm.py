import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import math
from datetime import datetime

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="ProWheel Lab v7.5", layout="wide", page_icon="🚲")

# --- 2. GOOGLE SHEETS CONNECTION ---
# Connects using the 'spreadsheet' URL in Streamlit Secrets
conn = st.connection("gsheets", type=GSheetsConnection) #

def get_worksheet_data(sheet_name, force_refresh=False):
    # Intelligent caching (10 mins) to prevent '429 Quota Exceeded' errors
    return conn.read(worksheet=sheet_name, ttl=0 if force_refresh else 600)

# --- 3. PRECISION CALCULATION LOGIC ---
def calculate_precision_spoke(erd, fd, os, holes, crosses, is_sp, sp_offset, hole_diam=2.4, round_mode="None"):
    if 0 in [erd, fd, holes]: return 0.0
    r_rim, r_hub = erd / 2, fd / 2
    
    if not is_sp:
        # Standard J-Bend Geometry (Matches v6.4 accuracy)
        alpha_rad = math.radians((crosses * 720.0) / holes)
        l_sq = (r_rim**2) + (r_hub**2) + (os**2) - (2 * r_rim * r_hub * math.cos(alpha_rad))
        length = math.sqrt(max(0, l_sq)) - (hole_diam / 2)
    else:
        # Straightpull Logic (Matches 304.2 / 305.5 benchmarks)
        d_tangent_2d = math.sqrt(max(0, r_rim**2 - r_hub**2))
        length = math.sqrt(d_tangent_2d**2 + os**2) + sp_offset
        
    # --- ROUNDING LOGIC ---
    if round_mode == "Nearest Even":
        return float(round(length / 2) * 2)
    elif round_mode == "Nearest Odd":
        return float(round((length - 1) / 2) * 2 + 1)
    return round(length, 1)

# Initialize Session State for staging lengths across tabs
for key in ['f_l', 'f_r', 'r_l', 'r_r']:
    if key not in st.session_state: st.session_state[key] = 0.0

# --- 4. MAIN USER INTERFACE ---
st.title("🚲 ProWheel Lab v7.5: Final Build Portfolio")
st.markdown("---")

tabs = st.tabs(["📊 Dashboard", "🧮 Precision Calc", "📦 Library", "➕ Register Build", "📄 Spec Sheet"])

# --- TAB: DASHBOARD ---
with tabs[0]:
    st.subheader("🏁 Workshop Pipeline")
    if st.button("🔄 Force Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    try:
        df_b = get_worksheet_data("builds") #
        if not df_b.empty:
            st.dataframe(df_b, use_container_width=True, hide_index=True)
        else:
            st.info("No builds found. Populate your Library and Register a Build.")
    except Exception as e:
        st.error(f"Connection failed: {e}")

# --- TAB: PRECISION CALC ---
with tabs[1]:
    st.header("🧮 Integrated Calculator")
    try:
        df_rims, df_hubs = get_worksheet_data("rims"), get_worksheet_data("hubs")
        df_spokes, df_nipples = get_worksheet_data("spokes"), get_worksheet_data("nipples")

        calc_mode = st.radio("Source", ["Use Library", "Manual Entry"], horizontal=True)

        if calc_mode == "Use Library" and not df_rims.empty and not df_hubs.empty:
            c1, c2 = st.columns(2)
            rim_choice = c1.selectbox("Select Rim", df_rims['brand'] + " " + df_rims['model'])
            hub_choice = c2.selectbox("Select Hub", df_hubs['brand'] + " " + df_hubs['model'])
            sel_r = df_rims[(df_rims['brand'] + " " + df_rims['model']) == rim_choice].iloc[0]
            sel_h = df_hubs[(df_hubs['brand'] + " " + df_hubs['model']) == hub_choice].iloc[0]
            erd, holes, rim_w, hub_w = sel_r['erd'], sel_r['holes'], sel_r.get('weight',0), sel_h.get('weight',0)
            l_fd, r_fd, l_os, r_os = sel_h['fd_l'], sel_h['fd_r'], sel_h['os_l'], sel_h['os_r']
            l_sp, r_sp = sel_h['sp_off_l'], sel_h['sp_off_r']
        else:
            m1, m2 = st.columns(2)
            erd, holes = m1.number_input("Rim ERD", 601.0), m2.number_input("Holes", 28)
            l_fd, r_fd, l_os, r_os, l_sp, r_sp, rim_w, hub_w = 40.8, 36.0, 28.0, 40.2, 1.7, 1.8, 0, 0

        st.divider()
        r1, r2 = st.columns(2)
        is_sp = r1.toggle("Straightpull Hub?", value=True)
        r_mode = r2.selectbox("Rounding", ["None", "Nearest Even", "Nearest Odd"])
        h_diam = st.slider("Hole Diameter (mm)", 2.0, 3.0, 2.4)
        l_c, r_c = st.selectbox("L-Cross", [0,1,2,3], index=3), st.selectbox("R-Cross", [0,1,2,3], index=3)

        res_l = calculate_precision_spoke(erd, l_fd, l_os, holes, l_c, is_sp, l_sp, h_diam, r_mode)
        res_r = calculate_precision_spoke(erd, r_fd, r_os, holes, r_c, is_sp, r_sp, h_diam, r_mode)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Left Spoke", f"{res_l} mm")
        col2.metric("Right Spoke", f"{res_r} mm")

        # Projected Weight
        if not df_spokes.empty and not df_nipples.empty:
            sw, nw = df_spokes.iloc[0]['weight_per_spoke'], df_nipples.iloc[0]['weight_per_nipple']
            total_est = rim_w + hub_w + (sw * holes) + (nw * holes)
            col3.metric("Est. Total Weight", f"{round(total_est, 1)} g")

        st.subheader("🛠️ Stage Lengths")
        side = st.radio("Target:", ["Front", "Rear"], horizontal=True)
        if st.button("Apply and Push to Form"):
            if side == "Front":
                st.session_state.f_l, st.session_state.f_r = res_l, res_r
            else:
                st.session_state.r_l, st.session_state.r_r = res_l, res_r
            st.success(f"{side} staged!")
    except Exception as e:
        st.error(f"Calc error: {e}")

# --- TAB: LIBRARY ---
with tabs[2]:
    st.header("📦 Library Management")
    l_type = st.selectbox("Category", ["Rims", "Hubs", "Spokes", "Nipples"])
    with st.form("lib_final", clear_on_submit=True):
        if l_type == "Rims":
            b, m, e, h, w = st.text_input("Brand"), st.text_input("Model"), st.number_input("ERD"), st.number_input("Holes"), st.number_input("Weight (g)")
            if st.form_submit_button("Upload Rim"):
                new = pd.DataFrame([{"brand":b, "model":m, "erd":e, "holes":h, "weight":w}])
                conn.update(worksheet="rims", data=pd.concat([get_worksheet_data("rims",True), new], ignore_index=True))
        elif l_type == "Hubs":
            b, m = st.text_input("Brand"), st.text_input("Model")
            fl, fr, ol, orr, sl, sr, w = st.number_input("L-PCD"), st.number_input("R-PCD"), st.number_input("L-Dist"), st.number_input("R-Dist"), st.number_input("L-SP Off"), st.number_input("R-SP Off"), st.number_input("Weight (g)")
            if st.form_submit_button("Upload Hub"):
                new = pd.DataFrame([{"brand":b, "model":m, "fd_l":fl, "fd_r":fr, "os_l":ol, "os_r":orr, "sp_off_l":sl, "sp_off_r":sr, "weight":w}])
                conn.update(worksheet="hubs", data=pd.concat([get_worksheet_data("hubs",True), new], ignore_index=True))
        # (Spoke/Nipple logic follows same structure)

# --- TAB: REGISTER BUILD ---
with tabs[3]:
    st.header("📝 Register Build Record")
    try:
        df_builds, df_rims,
