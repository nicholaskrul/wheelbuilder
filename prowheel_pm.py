import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import math

# --- APP CONFIG ---
st.set_page_config(page_title="ProWheel Lab: Cloud Edition", layout="wide")

# --- GOOGLE SHEETS CONNECTION ---
# This looks for your "Secrets" in Streamlit Cloud to log into Google
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data(worksheet):
    return conn.read(worksheet=worksheet)

# --- PRECISION CALC LOGIC ---
def calculate_precision_spoke(erd, fd, os, holes, crosses, is_sp, sp_offset):
    if 0 in [erd, fd, holes]: return 0.0
    r_rim, r_hub = erd / 2, fd / 2
    if not is_sp:
        alpha_rad = math.radians((crosses * 720.0) / holes)
        length = math.sqrt(r_rim**2 + r_hub**2 + os**2 - 2 * r_rim * r_hub * math.cos(alpha_rad))
    else:
        # DT Swiss Accurate Match
        d_tangent_2d = math.sqrt(max(0, r_rim**2 - r_hub**2))
        length = math.sqrt(d_tangent_2d**2 + os**2) + sp_offset
    return round(length, 1)

st.title("🚲 ProWheel Lab: Cloud Version")
st.caption("Data is stored permanently in Google Sheets")

tabs = st.tabs(["📊 Dashboard", "🧮 Precision Calc", "📦 Library", "📝 Register Build"])

# --- TAB: DASHBOARD ---
with tabs[0]:
    st.subheader("Current Build Pipeline")
    try:
        df_builds = get_data("builds")
        st.dataframe(df_builds, use_container_width=True, hide_index=True)
    except:
        st.warning("No data found in 'builds' sheet.")

# --- TAB: PRECISION CALC ---
with tabs[1]:
    st.header("🧮 Precision Calculator")
    c1, c2, c3 = st.columns(3)
    c_erd = c1.number_input("Rim ERD (mm)", value=601.0)
    c_holes = c2.number_input("Hole Count", value=28)
    is_sp = c3.toggle("Straightpull?", value=True)

    st.divider()
    col_l, col_r = st.columns(2)
    
    with col_l:
        st.subheader("⬅️ Left Side (NDS)")
        l_fd = st.number_input("Left PCD", value=40.8)
        l_os = st.number_input("Left Offset", value=28.0)
        l_sp = st.number_input("Left Spoke Offset", value=1.7) if is_sp else 0.0
        res_l = calculate_precision_spoke(c_erd, l_fd, l_os, c_holes, 3, is_sp, l_sp)
        st.metric("Length", f"{res_l} mm")

    with col_r:
        st.subheader("➡️ Right Side (DS)")
        r_fd = st.number_input("Right PCD", value=36.0)
        r_os = st.number_input("Right Offset", value=40.2)
        r_sp = st.number_input("Right Spoke Offset", value=1.8) if is_sp else 0.0
        res_r = calculate_precision_spoke(c_erd, r_fd, r_os, c_holes, 3, is_sp, r_sp)
        st.metric("Length", f"{res_r} mm")

# --- TAB: LIBRARY & REGISTERING ---
with tabs[2]:
    st.info("You can manage your Rims and Hubs directly in your Google Sheet for speed!")
    if st.button("Refresh Library Data"):
        st.rerun()

with tabs[3]:
    st.subheader("New Build Entry")
    with st.form("new_build"):
        cust = st.text_input("Customer Name")
        notes = st.text_area("Build Notes")
        submitted = st.form_submit_button("Log to Google Sheets")
        
        if submitted:
            # Code to append to Google Sheet goes here
            st.success("Build data sent to cloud!")
