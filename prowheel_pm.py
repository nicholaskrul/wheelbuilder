import streamlit as st
import pandas as pd
import sqlite3
import math
import json
from datetime import datetime

# --- DATABASE ENGINE ---
DB_FILE = 'prowheel_workshop.db'

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        # Projects/Builds Table
        c.execute('''CREATE TABLE IF NOT EXISTS builds
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      customer TEXT, status TEXT, date_added TEXT,
                      rim_id INTEGER, hub_id INTEGER, 
                      f_ds_len REAL, f_nds_len REAL, r_ds_len REAL, r_nds_len REAL,
                      tension_data TEXT, notes TEXT)''')
        # Rim Library
        c.execute('''CREATE TABLE IF NOT EXISTS rims 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, brand TEXT, model TEXT, erd REAL, holes INTEGER)''')
        # Hub Library
        c.execute('''CREATE TABLE IF NOT EXISTS hubs 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, brand TEXT, model TEXT, fd REAL, os REAL, spoke_offset REAL)''')
        conn.commit()

def run_query(query, params=()):
    with sqlite3.connect(DB_FILE) as conn:
        if query.strip().upper().startswith("SELECT"):
            return pd.read_sql_query(query, conn)
        else:
            conn.execute(query, params)
            conn.commit()

# --- CALCULATOR LOGIC (Manufacturer Spec Edition) ---
def calculate_spoke(erd, fd, os, holes, crosses, is_sp, sp_offset):
    if 0 in [erd, fd, holes]: return 0.0
    
    angle_rad = math.radians((720 * crosses) / holes)
    
    # Standard 2D Projection
    # Using the Law of Cosines to find the distance from hub flange to rim hole
    d_2d_sq = (erd/2)**2 + (fd/2)**2 - (erd * fd / 2 * math.cos(angle_rad))
    
    if not is_sp:
        # J-Bend: Basic 3D triangle calculation
        length = math.sqrt(d_2d_sq + os**2)
    else:
        # Straightpull: Based on the "Spoke Offset" from your diagram
        # This correction factor is applied to the 2D path
        length = math.sqrt(max(0, d_2d_sq + os**2)) + sp_offset
        
    return round(length, 1)

# --- APP CONFIG ---
st.set_page_config(page_title="ProWheel Lab v5", layout="wide", page_icon="🚲")
init_db()

# --- CUSTOM CSS FOR SHOP VISIBILITY ---
st.markdown("""
    <style>
    .metric-card { background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #ff4b4b; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { font-size: 18px; font-weight: bold; }
    </style>
    """, unsafe_all_original_markup=True)

st.title("🚲 ProWheel Lab v5: Workshop Manager")

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
        # Shop Stats
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Active Jobs", len(df_builds[df_builds['status'] != "Build Complete"]))
        c2.metric("Awaiting Parts", len(df_builds[df_builds['status'] == "Parts Ordered"]))
        c3.metric("Ready to Lace", len(df_builds[df_builds['status'] == "Parts Received"]))
        c4.metric("Completed", len(df_builds[df_builds['status'] == "Build Complete"]))
        
        st.divider()
        
        # Search & Table
        search = st.text_input("🔍 Search active builds...")
        display_df = df_builds if not search else df_builds[df_builds['customer'].str.contains(search, case=False)]
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # Quick Update Section
        st.subheader("🛠️ Quick Status Update")
        col_up1, col_up2, col_up3 = st.columns([2,2,1])
        target_id = col_up1.selectbox("Select ID to Update", df_builds['id'])
        new_status = col_up2.selectbox("New Status", ["Order Received", "Parts Ordered", "Parts Received", "Build Complete"])
        if col_up3.button("Apply Update", use_container_width=True):
            run_query("UPDATE builds SET status = ? WHERE id = ?", (new_status, target_id))
            st.rerun()
    else:
        st.info("No active builds in the queue.")

# --- TAB 2: NEW BUILD ---
with tabs[1]:
    st.header("Register New Customer Build")
    rims_list = run_query("SELECT id, brand, model FROM rims")
    hubs_list = run_query("SELECT id, brand, model FROM hubs")

    with st.form("new_build_form"):
        col1, col2 = st.columns(2)
        cust = col1.text_input("Customer Name")
        date = col2.date_input("Start Date")

        st.markdown("### Component Selection")
        r_opt = {f"{r['brand']} {r['model']}": r['id'] for _, r in rims_list.iterrows()}
        h_opt = {f"{h['brand']} {h['model']}": h['id'] for _, h in hubs_list.iterrows()}
        
        sel_rim = st.selectbox("Select Rim from Library", options=list(r_opt.keys()))
        sel_hub = st.selectbox("Select Hub from Library", options=list(h_opt.keys()))

        st.markdown("### Final Spoke Lengths (From Calc)")
        sc1, sc2, sc3, sc4 = st.columns(4)
        f_ds = sc1.number_input("Front DS (mm)", step=0.5)
        f_nds = sc2.number_input("Front NDS (mm)", step=0.5)
        r_ds = sc3.number_input("Rear DS (mm)", step=0.5)
        r_nds = sc4.number_input("Rear NDS (mm)", step=0.5)
        
        notes = st.text_area("Builder Notes / Tension Targets")
        
        if st.form_submit_button("Save Build to Database"):
            run_query("""
