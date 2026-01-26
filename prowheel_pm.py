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
        # Projects/Builds Table
        c.execute('''CREATE TABLE IF NOT EXISTS builds
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      customer TEXT, status TEXT, date_added TEXT,
                      rim_id INTEGER, hub_id INTEGER, 
                      f_ds_len REAL, f_nds_len REAL, r_ds_len REAL, r_nds_len REAL,
                      notes TEXT)''')
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
    
    # Fundamental 2D angle calculation
    angle_rad = math.radians((720 * crosses) / holes)
    
    # Law of Cosines for the 2D path
    d_2d_sq = (erd/2)**2 + (fd/2)**2 - (erd * fd / 2 * math.cos(angle_rad))
    
    if not is_sp:
        # J-Bend Calculation
        length = math.sqrt(d_2d_sq + os**2)
    else:
        # Straightpull Calculation
        # Measurement is taken from centre line to where spoke head seats
        # Error of 1mm in offset = 1mm error in spoke length
        length = math.sqrt(max(0, d_2d_sq + os**2)) + sp_offset
        
    return round(length, 1)

# --- APP CONFIG ---
st.set_page_config(page_title="ProWheel Lab v5", layout="wide", page_icon="🚲")
init_db()

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
        c1, c2, c3 = st.columns(3)
        c1.metric("Active Jobs", len(df_builds[df_builds['status'] != "Build Complete"]))
        c2.metric("Ready to Lace", len(df_builds[df_builds['status'] == "Parts Received"]))
        c3.metric("Completed", len(df_builds[df_builds['status'] == "Build Complete"]))
        
        st.divider()
        search = st.text_input("🔍 Search active builds...")
        display_df = df_builds if not search else df_builds[df_builds['customer'].str.contains(search, case=False)]
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        st.subheader("🛠️ Status Update")
        col_up1, col_up2, col_up3 = st.columns([2,2,1])
        target_id = col_up1.selectbox("Select ID", df_builds['id'])
        new_status = col_up2.selectbox("New Status", ["Order Received", "Parts Ordered", "Parts Received", "Build Complete"])
        if col_up3.button("Apply Update"):
            run_query("UPDATE builds SET status = ? WHERE id = ?", (new_status, target_id))
            st.rerun()
    else:
        st.info("No active builds. Add one in the 'New Build' tab.")

# --- TAB 2: NEW BUILD ---
with tabs[1]:
    st.header("Register New Customer Build")
    rims_list = run_query("SELECT id, brand, model FROM rims")
    hubs_list = run_query("SELECT id, brand, model FROM hubs")

    with st.form("new_build_form"):
        col1, col2 = st.columns(2)
        cust = col1.text_input("Customer Name")
        date = col2.date_input("Start Date")

        r_opt = {f"{r['brand']} {r['model']}": r['id'] for _, r in rims_list.iterrows()}
        h_opt = {f"{h['brand']} {h['model']}": h['id'] for _, h in hubs_list.iterrows()}
        
        sel_rim = st.selectbox("Select Rim", options=list(r_opt.keys()) if r_opt else ["Add Rims in Library First"])
        sel_hub = st.selectbox("Select Hub", options=list(h_opt.keys()) if h_opt else ["Add Hubs in Library First"])

        st.markdown("### Measured Spoke Lengths")
        sc1, sc2, sc3, sc4 = st.columns(4)
        f_ds = sc1.number_input("Front DS", step=0.5)
        f_nds = sc2.number_input("Front NDS", step=0.5)
        r_ds = sc3.number_input("Rear DS", step=0.5)
        r_nds = sc4.number_input("Rear NDS", step=0.5)
        
        notes = st.text_area("Special Instructions")
        
        if st.form_submit_
