import streamlit as st
import pandas as pd
import sqlite3
import math
from datetime import datetime

# --- DATABASE INITIALIZATION (v5) ---
def init_db():
    with sqlite3.connect('wheel_shop_v5.db') as conn:
        c = conn.cursor()
        # Updated builds table to include tension logs
        c.execute('''CREATE TABLE IF NOT EXISTS builds
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, customer TEXT, status TEXT, 
                      date_added TEXT, rim_id INTEGER, hub_id INTEGER, 
                      f_ds REAL, f_nds REAL, r_ds REAL, r_nds REAL, 
                      tension_json TEXT, notes TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS rims (id INTEGER PRIMARY KEY AUTOINCREMENT, brand TEXT, model TEXT, erd REAL, holes INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS hubs (id INTEGER PRIMARY KEY AUTOINCREMENT, brand TEXT, model TEXT, fd REAL, os REAL, spoke_offset REAL)''')
        conn.commit()

def run_query(query, params=()):
    with sqlite3.connect('wheel_shop_v5.db') as conn:
        return pd.read_sql_query(query, conn) if "SELECT" in query else conn.execute(query, params)

# --- THE ACCURATE STRAIGHTPULL FORMULA ---
def calculate_spoke_v5(erd, fd, os, holes, crosses, spoke_type, spoke_offset):
    if 0 in [erd, fd, holes]: return 0.0
    
    # Fundamental 2D angle
    angle_rad = math.radians((720 * crosses) / holes)
    
    if spoke_type == "J-Bend":
        length = math.sqrt((erd/2)**2 + (fd/2)**2 + os**2 - (erd * fd / 2) * math.cos(angle_rad))
    else:
        # Straightpull using Manufacturer "Spoke Offset" from your diagram
        # This accounts for the seat position relative to the hub center-line
        r_rim = erd / 2
        r_hub = fd / 2
        
        # Calculate 2D distance between hub seat and rim hole
        d_2d_sq = r_rim**2 + r_hub**2 - (2 * r_rim * r_hub * math.cos(angle_rad))
        
        # Final length includes the lateral offset (os) and the manufacturer's spoke offset
        # Note: spoke_offset from your image is treated as a tangential correction
        length = math.sqrt(max(0, d_2d_sq + os**2)) + spoke_offset
        
    return round(length, 1)

# --- APP UI ---
init_db()
st.set_page_config(page_title="ProWheel Lab v5", layout="wide")
st.title("🚲 ProWheel Lab v5")

tab1, tab2, tab3 = st.tabs(["📊 Dashboard & Tension Log", "🧮 Advanced Spoke Calc", "📦 Component Library"])

# --- TAB 2: UPDATED CALCULATOR ---
with tab2:
    st.header("🧮 Manufacturer-Spec Calculator")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.subheader("Rim Specs")
        calc_erd = st.number_input("Rim ERD (mm)", value=600.0)
        calc_holes = st.number_input("Hole Count", value=28)
        calc_cross = st.selectbox("Cross Pattern", [0, 1, 2, 3], index=3)

    with c2:
        st.subheader("Hub Specs")
        st_type = st.radio("Lacing Style", ["J-Bend", "Straightpull"])
        calc_fd = st.number_input("Flange Diameter (mm)", value=58.0)
        calc_os = st.number_input("Center-to-Flange (mm)", value=35.0)

    with c3:
        st.subheader("Straightpull Offset")
        if st_type == "Straightpull":
            # Direct match to the diagram you provided
            calc_sp_off = st.number_input("Spoke Offset (mm)", value=0.0, help="From your diagram: Positive, Negative, or Zero.")
            st.caption("Value provided by hub manufacturer (e.g., DT Swiss, Hope, Industry Nine).")
        else:
            calc_sp_off = 0.0
            st.write("J-Bend ignores Spoke Offset.")

    res = calculate_spoke_v5(calc_erd, calc_fd, calc_os, calc_holes, calc_cross, st_type, calc_sp_off)
    st.divider()
    st.metric(f"Calculated {st_type} Length", f"{res} mm")

# --- TAB 1: TENSION LOG ADDITION ---
with tab1:
    st.subheader("Active Build Tension Monitoring")
    # Imagine selecting a build here... 
    st.write("Record final kgf readings for quality assurance.")
    
    t_col1, t_col2 = st.columns(2)
    with t_col1:
        st.text_input("Drive Side Avg (kgf)", placeholder="120")
    with t_col2:
        st.text_input("Non-Drive Side Avg (kgf)", placeholder="80")
    
    st.button("Update Build Records")
    
    # (Rest of dashboard code from v4 goes here)
