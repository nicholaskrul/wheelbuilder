import streamlit as st
import pandas as pd
import sqlite3
import math
from datetime import datetime

# --- DATABASE ENGINE ---
DB_FILE = 'prowheel_precision.db'

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS builds
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, customer TEXT, status TEXT, 
                      f_l_len REAL, f_r_len REAL, r_l_len REAL, r_r_len REAL, notes TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS rims 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, brand TEXT, model TEXT, erd REAL, holes INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS hubs 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, brand TEXT, model TEXT, 
                      fd_l REAL, fd_r REAL, os_l REAL, os_r REAL, sp_off_l REAL, sp_off_r REAL)''')
        conn.commit()

def run_query(query, params=()):
    with sqlite3.connect(DB_FILE) as conn:
        if query.strip().upper().startswith("SELECT"):
            return pd.read_sql_query(query, conn)
        else:
            conn.execute(query, params)
            conn.commit()

# --- THE DT SWISS PRECISION FORMULA ---
def calculate_precision_spoke(erd, fd, os, holes, crosses, is_sp, sp_offset):
    if 0 in [erd, fd, holes]: return 0.0
    
    r_rim = erd / 2
    r_hub = fd / 2
    
    if not is_sp:
        # Standard J-Bend (Law of Cosines)
        alpha = (crosses * 720.0) / holes
        alpha_rad = math.radians(alpha)
        length = math.sqrt(r_rim**2 + r_hub**2 + os**2 - 2 * r_rim * r_hub * math.cos(alpha_rad))
    else:
        # Accurate Straightpull: Tangential path + Manufacturer Offset
        # 1. Calculate the distance of the tangential exit in 2D
        d_tangent_2d = math.sqrt(r_rim**2 - r_hub**2)
        # 2. Factor in the lateral flange distance (os)
        d_3d = math.sqrt(d_tangent_2d**2 + os**2)
        # 3. Apply the Spoke Offset correction from your diagram (Direct 1:1 match)
        length = d_3d + sp_offset
        
    return round(length, 1)

# --- APP UI ---
st.set_page_config(page_title="ProWheel Lab v5.3", layout="wide")
init_db()

st.title("🚲 ProWheel Precision Lab")
st.caption("Synchronized with DT Swiss Accuracy Standards")

tabs = st.tabs(["📊 Dashboard", "🧮 Precision Calc", "📦 Component Library"])

# --- TAB: PRECISION CALCULATOR ---
with tabs[1]:
    st.header("🧮 Accurate Spoke Calculator")
    
    # Global Inputs
    g1, g2, g3 = st.columns(3)
    c_erd = g1.number_input("Rim ERD (mm)", value=601.0, step=0.1)
    c_holes = g2.number_input("Total Hole Count", value=28, step=2)
    is_sp = g3.toggle("Straightpull Hub Geometry?", value=True)

    st.divider()
    
    # Comparison Data from your screenshot
    # Left: PCD 40.8, Dist 28.0, Offset 1.7 -> Target 304.2
    # Right: PCD 36.0, Dist 40.2, Offset 1.8 -> Target 305.5

    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("⬅️ Left Side (NDS)")
        l_fd = st.number_input("Left PCD (mm)", value=40.8, key="lfd")
        l_os = st.number_input("Left Flange Distance (mm)", value=28.0, key="los")
        l_sp_off = st.number_input("Left Spoke Offset (mm)", value=1.7, key="lsp") if is_sp else 0.0
        
        res_l = calculate_precision_spoke(c_erd, l_fd, l_os, c_holes, 3, is_sp, l_sp_off)
        st.metric("Calculated Length", f"{res_l} mm")
        st.write("🎯 **Target:** 304.2 mm")

    with col_r:
        st.subheader("➡️ Right Side (DS)")
        r_fd = st.number_input("Right PCD (mm)", value=36.0, key="rfd")
        r_os = st.number_input("Right Flange Distance (mm)", value=40.2, key="ros")
        r_sp_off = st.number_input("Right Spoke Offset (mm)", value=1.8, key="rsp") if is_sp else 0.0
        
        res_r = calculate_precision_spoke(c_erd, r_fd, r_os, c_holes, 3, is_sp, r_sp_off)
        st.metric("Calculated Length", f"{res_r} mm")
        st.write("🎯 **Target:** 305.5 mm")

# --- TAB: LIBRARY ---
with tabs[2]:
    st.subheader("Add Hub to Library")
    with st.form("hub_lib_new"):
        hb, hm = st.text_input("Brand"), st.text_input("Model")
        hfl, hfr = st.number_input("L-PCD"), st.number_input("R-PCD")
        hol, hor = st.number_input("L-Flange Dist"), st.number_input("R-Flange Dist")
        hsl, hsr = st.number_input("L-SP Offset"), st.number_input("R-SP Offset")
        if st.form_submit_button("Save Hub"):
            run_query("INSERT INTO hubs VALUES (NULL,?,?,?,?,?,?,?,?)", (hb, hm, hfl, hfr, hol, hor, hsl, hsr))
            st.success("Hub saved!")
            st.rerun()

# --- TAB: DASHBOARD ---
with tabs[0]:
    st.write("Dashboard logic remains as per v5.2")
    df = run_query("SELECT * FROM builds")
    st.dataframe(df, use_container_width=True)
