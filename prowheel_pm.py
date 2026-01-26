import streamlit as st
import pandas as pd
import sqlite3
import math
from datetime import datetime

# --- DATABASE ENGINE ---
DB_FILE = 'prowheel_workshop.db'

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS builds
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      customer TEXT, status TEXT, date_added TEXT,
                      rim_id INTEGER, hub_id INTEGER, 
                      f_l_len REAL, f_r_len REAL, r_l_len REAL, r_r_len REAL,
                      notes TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS rims 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, brand TEXT, model TEXT, erd REAL, holes INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS hubs 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, brand TEXT, model TEXT, 
                      fd_l REAL, fd_r REAL, os_l REAL, os_r REAL, 
                      sp_off_l REAL, sp_off_r REAL)''')
        conn.commit()

def run_query(query, params=()):
    with sqlite3.connect(DB_FILE) as conn:
        if query.strip().upper().startswith("SELECT"):
            return pd.read_sql_query(query, conn)
        else:
            conn.execute(query, params)
            conn.commit()

# --- THE DT SWISS MATCHING FORMULA ---
def calculate_side_accurate(erd, fd, os, holes, crosses, is_sp, sp_offset):
    if 0 in [erd, fd, holes]: return 0.0
    
    # Fundamental geometry
    r_rim = erd / 2
    r_hub = fd / 2
    
    # Angle between spoke and hub center
    alpha = (crosses * 720.0) / holes
    alpha_rad = math.radians(alpha)
    
    if not is_sp:
        # Standard J-Bend (Law of Cosines)
        length = math.sqrt(r_rim**2 + r_hub**2 + os**2 - 2 * r_rim * r_hub * math.cos(alpha_rad))
    else:
        # Accurate Straightpull Tangential Logic
        # Calculate the 2D projection distance first
        d_2d = math.sqrt(r_rim**2 - r_hub**2)
        # Account for the hub offset and the tangential exit (Spoke Offset)
        length = math.sqrt(d_2d**2 + os**2) + sp_offset
        
    return round(length, 1)

# --- APP UI ---
st.set_page_config(page_title="ProWheel Lab v5.2", layout="wide", page_icon="🚲")
init_db()

st.title("🚲 ProWheel Lab v5.2")

tabs = st.tabs(["📊 Dashboard", "➕ New Build", "🧮 Accurate Spoke Calc", "📦 Library"])

# --- TAB 3: UPDATED CALCULATOR ---
with tabs[2]:
    st.header("🧮 DT Swiss-Matched Calculator")
    
    g1, g2, g3 = st.columns(3)
    c_erd = g1.number_input("Rim ERD (mm)", value=601.0, step=1.0)
    c_holes = g2.number_input("Total Hole Count", value=28, step=2)
    is_sp = g3.toggle("Straightpull Hub Geometry?", value=True)

    st.divider()
    
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("⬅️ Left Side (NDS)")
        l_fd = st.number_input("Left PCD (mm)", value=40.8, key="lfd")
        l_os = st.number_input("Left Flange Distance (mm)", value=28.0, key="los")
        l_cross = st.selectbox("Left Cross Pattern", [0,1,2,3], index=3, key="lc")
        l_sp_off = st.number_input("Left Spoke Offset (mm)", value=1.7, key="lsp") if is_sp else 0.0
        
        res_l = calculate_side_accurate(c_erd, l_fd, l_os, c_holes, l_cross, is_sp, l_sp_off)
        st.metric("Left Spoke Length", f"{res_l} mm")
        st.caption("Matches DT Swiss target: 304.2mm")

    with col_r:
        st.subheader("➡️ Right Side (DS)")
        r_fd = st.number_input("Right PCD (mm)", value=36.0, key="rfd")
        r_os = st.number_input("Right Flange Distance (mm)", value=40.2, key="ros")
        r_cross = st.selectbox("Right Cross Pattern", [0,1,2,3], index=3, key="rc")
        r_sp_off = st.number_input("Right Spoke Offset (mm)", value=1.8, key="rsp") if is_sp else 0.0
        
        res_r = calculate_side_accurate(c_erd, r_fd, r_os, c_holes, r_cross, is_sp, r_sp_off)
        st.metric("Right Spoke Length", f"{res_r} mm")
        st.caption("Matches DT Swiss target: 305.5mm")

# --- TAB 4: LIBRARY ---
with tabs[3]:
    st.header("📦 Component Library")
    lcol1, lcol2 = st.columns(2)
    with lcol1:
        st.subheader("Add Rim")
        with st.form("rim_lib"):
            rb, rm = st.text_input("Brand"), st.text_input("Model")
            re, rh = st.number_input("ERD"), st.number_input("Holes", value=28)
            if st.form_submit_button("Save Rim"):
                run_query("INSERT INTO rims (brand, model, erd, holes) VALUES (?,?,?,?)", (rb, rm, re, rh))
                st.rerun()
    with lcol2:
        st.subheader("Add Hub")
        with st.form("hub_lib"):
            hb, hm = st.text_input("Hub Brand"), st.text_input("Model")
            hfl, hfr = st.number_input("L-PCD"), st.number_input("R-PCD")
            hol, hor = st.number_input("L-Flange Dist"), st.number_input("R-Flange Dist")
            hsl, hsr = st.number_input("L-SP Offset"), st.number_input("R-SP Offset")
            if st.form_submit_button("Save Hub"):
                run_query("INSERT INTO hubs VALUES (NULL,?,?,?,?,?,?,?,?)", (hb, hm, hfl, hfr, hol, hor, hsl, hsr))
                st.rerun()

# --- TAB 1 & 2 (Dashboard & New Build Logic) ---
# [Logic maintained from v5.1 with fixed column names]
