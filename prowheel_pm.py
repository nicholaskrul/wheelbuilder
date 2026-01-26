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
        # J-Bend Calculation: standard Pythagorean 3D triangle
        length = math.sqrt(d_2d_sq + os**2)
    else:
        # Straightpull Calculation based on your diagram:
        # The offset directly influences the length 1:1.
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

        st.subheader("🛠️ Quick Status Update")
        col_up1, col_up2, col_up3 = st.columns([2,2,1])
        target_id = col_up1.selectbox("Select Job ID to Update", df_builds['id'])
        current_status = df_builds[df_builds['id'] == target_id]['status'].values[0]
        
        status_options = ["Order Received", "Parts Ordered", "Parts Received", "Build Complete"]
        new_status = col_up2.selectbox("Set New Status", status_options, index=status_options.index(current_status))
        
        if col_up3.button("Apply Changes", use_container_width=True):
            run_query("UPDATE builds SET status = ? WHERE id = ?", (new_status, target_id))
            st.success(f"Job {target_id} updated!")
            st.rerun()
    else:
        st.info("No active builds. Head to the 'New Build' tab to get started.")

# --- TAB 2: NEW BUILD ---
with tabs[1]:
    st.header("Register New Customer Build")
    rims_list = run_query("SELECT id, brand, model FROM rims")
    hubs_list = run_query("SELECT id, brand, model FROM hubs")

    if rims_list.empty or hubs_list.empty:
        st.warning("⚠️ Your Component Library is empty. Please add at least one Rim and Hub in the 'Library' tab before creating a build.")
    else:
        with st.form("new_build_form"):
            col1, col2 = st.columns(2)
            cust = col1.text_input("Customer Name")
            date = col2.date_input("Start Date")

            r_opt = {f"{r['brand']} {r['model']}": r['id'] for _, r in rims_list.iterrows()}
            h_opt = {f"{h['brand']} {h['model']}": h['id'] for _, h in hubs_list.iterrows()}
            
            sel_rim = st.selectbox("Select Rim", options=list(r_opt.keys()))
            sel_hub = st.selectbox("Select Hub", options=list(h_opt.keys()))

            st.markdown("### Measured Spoke Lengths (mm)")
            sc1, sc2, sc3, sc4 = st.columns(4)
            f_ds = sc1.number_input("Front DS", step=0.1)
            f_nds = sc2.number_input("Front NDS", step=0.1)
            r_ds = sc3.number_input("Rear DS", step=0.1)
            r_nds = sc4.number_input("Rear NDS", step=0.1)
            
            notes = st.text_area("Builder Notes (Tension targets, special requests)")
            
            if st.form_submit_button("Save Build to Database"):
                run_query("""INSERT INTO builds 
                             (customer, status, date_added, rim_id, hub_id, f_ds_len, f_nds_len, r_ds_len, r_nds_len, notes) 
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                          (cust, "Order Received", date.strftime("%Y-%m-%d"), r_opt[sel_rim], h_opt[sel_hub], f_ds, f_nds, r_ds, r_nds, notes))
                st.success("Build registered successfully!")
                st.rerun()

# --- TAB 3: SPOKE CALC ---
with tabs[2]:
    st.header("🧮 Professional Spoke Length Calculator")
    
    calc_col1, calc_col2, calc_col3 = st.columns(3)
    
    with calc_col1:
        st.subheader("Rim Dimensions")
        c_erd = st.number_input("Rim ERD (mm)", value=600.0, step=0.1)
        c_holes = st.number_input("Hole Count", value=28, step=2)
        c_cross = st.selectbox("Cross Pattern", [0,1,2,3,4], index=3)
    
    with calc_col2:
        st.subheader("Hub Dimensions")
        is_sp = st.toggle("Straightpull Hub?")
        c_fd = st.number_input("Flange Diameter / PCD (mm)", value=58.0, step=0.1)
        c_os = st.number_input("Center-to-Flange Offset (mm)", value=32.0, step=0.1)
    
    with calc_col3:
        st.subheader("Straightpull Correction")
        c_sp_off = 0.0
        if is_sp:
            c_sp_off = st.number_input("Spoke Offset (mm)", value=0.0, step=0.1, help="Positive, negative, or zero based on manufacturer spec.")
            st.info("From your diagram: A measuring error of 1mm in offset results in a 1mm error in spoke length.")
        else:
            st.write("J-bend uses standard center-of-hole geometry.")

    final_len = calculate_spoke(c_erd, c_fd, c_os, c_holes, c_cross, is_sp, c_sp_off)
    st.divider()
    st.metric("Suggested Spoke Length", f"{final_len} mm")

# --- TAB 4: LIBRARY ---
with tabs[3]:
    st.header("📦 Component Library")
    lcol1, lcol2 = st.columns(2)
    
    with lcol1:
        st.subheader("Add Rim to Database")
        with st.form("rim_lib"):
            rb = st.text_input("Rim Brand (e.g., DT Swiss)")
            rm = st.text_input("Rim Model (e.g., RR 411)")
            re = st.number_input("ERD (mm)", step=0.1)
            rh = st.number_input("Hole Count", value=28, step=2)
            if st.form_submit_button("Add Rim"):
                run_query("INSERT INTO rims (brand, model, erd, holes) VALUES (?,?,?,?)", (rb, rm, re, rh))
                st.success("Rim added!")
                st.rerun()
    
    with lcol2:
        st.subheader("Add Hub to Database")
        with st.form("hub_lib"):
            hb = st.text_input("Hub Brand (e.g., Hope)")
            hm = st.text_input("Hub Model (e.g., Pro 4)")
            hf = st.number_input("Flange PCD (mm)", step=0.1)
            ho = st.number_input("Center-to-Flange (mm)", step=0.1)
            hsp = st.number_input("SP Spoke Offset (If applicable)", value=0.0, step=0.1)
            if st.form_submit_button("Add Hub"):
                run_query("INSERT INTO hubs (brand, model, fd, os, spoke_offset) VALUES (?,?,?,?,?)", (hb, hm, hf, ho, hsp))
                st.success("Hub added!")
                st.rerun()

    st.divider()
    st.subheader("Stored Inventory")
    inv1, inv2 = st.columns(2)
    inv1.write("**Saved Rims**")
    inv1.dataframe(run_query("SELECT brand, model, erd, holes FROM rims"), hide_index=True)
    inv2.write("**Saved Hubs**")
    inv2.dataframe(run_query("SELECT brand, model, fd, os, spoke_offset FROM hubs"), hide_index=True)
