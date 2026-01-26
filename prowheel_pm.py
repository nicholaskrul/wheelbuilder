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
                      f_ds_len REAL, f_nds_len REAL, r_ds_len REAL, r_nds_len REAL,
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

# --- ASYMMETRICAL CALCULATOR LOGIC ---
def calculate_side(erd, fd, os, holes, crosses, is_sp, sp_offset):
    if 0 in [erd, fd, holes]: return 0.0
    angle_rad = math.radians((720 * crosses) / holes)
    d_2d_sq = (erd/2)**2 + (fd/2)**2 - (erd * fd / 2 * math.cos(angle_rad))
    
    # Base calculation + Lateral Offset (os)
    base_len = math.sqrt(max(0, d_2d_sq + os**2))
    
    # Add Straightpull offset if applicable (directly additive/subtractive per your diagram)
    final_len = base_len + sp_offset if is_sp else base_len
    return round(final_len, 1)

# --- APP CONFIG ---
st.set_page_config(page_title="ProWheel Lab v5.1", layout="wide", page_icon="🚲")
init_db()

st.title("🚲 ProWheel Lab v5.1: Asymmetrical Workshop")

tabs = st.tabs(["📊 Dashboard", "➕ New Build", "🧮 Spoke Calc", "📦 Library"])

# --- TAB 1: DASHBOARD ---
with tabs[0]:
    df_builds = run_query("""
        SELECT b.id, b.customer, b.status, b.date_added, 
               r.brand || ' ' || r.model as rim, 
               h.brand || ' ' || h.model as hub,
               b.f_ds_len, b.f_nds_len, b.r_ds_len, b.r_nds_len, b.notes
        FROM builds b
        LEFT JOIN rims r ON b.rim_id = r.id
        LEFT JOIN hubs h ON b.hub_id = h.id
    """)

    if not df_builds.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Active Jobs", len(df_builds[df_builds['status'] != "Build Complete"]))
        c2.metric("Ready to Lace", len(df_builds[df_builds['status'] == "Parts Received"]))
        c3.metric("Completed", len(df_builds[df_builds['status'] == "Build Complete"]))
        
        st.divider()
        search = st.text_input("🔍 Search active builds...")
        display_df = df_builds if not search else df_builds[df_builds['customer'].str.contains(search, case=False)]
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("No active builds.")

# --- TAB 3: ASYMMETRICAL CALCULATOR ---
with tabs[2]:
    st.header("🧮 Independent Side Calculator")
    
    # General Specs
    g1, g2, g3 = st.columns(3)
    c_erd = g1.number_input("Rim ERD (mm)", value=600.0, step=0.1)
    c_holes = g2.number_input("Total Hole Count", value=28, step=2)
    is_sp = g3.toggle("Straightpull Hub Geometry?")

    

    st.divider()
    
    # LEFT SIDE (NDS)
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("⬅️ Left Side (NDS)")
        l_fd = st.number_input("Left Flange PCD (mm)", value=58.0, key="lfd")
        l_os = st.number_input("Left Center-to-Flange (mm)", value=32.0, key="los")
        l_cross = st.selectbox("Left Cross Pattern", [0,1,2,3,4], index=3, key="lc")
        l_sp_off = st.number_input("Left Spoke Offset (mm)", value=0.0, key="lsp") if is_sp else 0.0
        
        res_l = calculate_side(c_erd, l_fd, l_os, c_holes, l_cross, is_sp, l_sp_off)
        st.metric("Left Spoke Length", f"{res_l} mm")

    # RIGHT SIDE (DS)
    with col_r:
        st.subheader("➡️ Right Side (DS)")
        r_fd = st.number_input("Right Flange PCD (mm)", value=58.0, key="rfd")
        r_os = st.number_input("Right Center-to-Flange (mm)", value=20.0, key="ros")
        r_cross = st.selectbox("Right Cross Pattern", [0,1,2,3,4], index=3, key="rc")
        r_sp_off = st.number_input("Right Spoke Offset (mm)", value=0.0, key="rsp") if is_sp else 0.0
        
        res_r = calculate_side(c_erd, r_fd, r_os, c_holes, r_cross, is_sp, r_sp_off)
        st.metric("Right Spoke Length", f"{res_r} mm")

# --- TAB 4: LIBRARY (Updated for Asymmetrical Hubs) ---
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
        st.subheader("Add Asymmetrical Hub")
        with st.form("hub_lib"):
            hb, hm = st.text_input("Hub Brand"), st.text_input("Model")
            st.write("**Left (NDS) Specs**")
            hfl, hol, hsl = st.number_input("L-PCD"), st.number_input("L-Offset"), st.number_input("L-SP Offset")
            st.write("**Right (DS) Specs**")
            hfr, hor, hsr = st.number_input("R-PCD"), st.number_input("R-Offset"), st.number_input("R-SP Offset")
            if st.form_submit_button("Save Hub"):
                run_query("""INSERT INTO hubs (brand, model, fd_l, fd_r, os_l, os_r, sp_off_l, sp_off_r) 
                             VALUES (?,?,?,?,?,?,?,?)""", (hb, hm, hfl, hfr, hol, hor, hsl, hsr))
                st.rerun()

# --- TAB 2: NEW BUILD (Remains similar to v5) ---
with tabs[1]:
    st.header("Register New Build")
    # ... Logic to fetch from DB and save build ...
    st.info("Ensure you enter the Left and Right lengths generated in the Calculator tab.")

