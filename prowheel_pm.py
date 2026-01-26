import streamlit as st
import pandas as pd
import sqlite3
import math
from datetime import datetime

# --- DATABASE ENGINE ---
# This version uses a persistent SQLite file to store your library and builds.
DB_FILE = 'prowheel_precision.db'

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        # Projects/Builds Table
        c.execute('''CREATE TABLE IF NOT EXISTS builds
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      customer TEXT, status TEXT, date_added TEXT,
                      rim_id INTEGER, hub_id INTEGER, 
                      f_l_len REAL, f_r_len REAL, r_l_len REAL, r_r_len REAL,
                      notes TEXT)''')
        # Rim Library
        c.execute('''CREATE TABLE IF NOT EXISTS rims 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, brand TEXT, model TEXT, erd REAL, holes INTEGER)''')
        # Hub Library - Updated for asymmetrical specs
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

# --- THE DT SWISS PRECISION FORMULA ---
# This math accounts for the tangential exit of straightpull spokes.
def calculate_precision_spoke(erd, fd, os, holes, crosses, is_sp, sp_offset):
    if 0 in [erd, fd, holes]: return 0.0
    
    r_rim = erd / 2
    r_hub = fd / 2
    
    if not is_sp:
        # Standard J-Bend Geometry
        alpha = (crosses * 720.0) / holes
        alpha_rad = math.radians(alpha)
        length = math.sqrt(r_rim**2 + r_hub**2 + os**2 - 2 * r_rim * r_hub * math.cos(alpha_rad))
    else:
        # Accurate Straightpull: Tangential path + Manufacturer Offset
        # We calculate the tangential exit in 2D, then add the lateral 3D distance,
        # and finally add the manufacturer's Spoke Offset (K-value).
        d_tangent_2d = math.sqrt(r_rim**2 - r_hub**2)
        d_3d = math.sqrt(d_tangent_2d**2 + os**2)
        length = d_3d + sp_offset
        
    return round(length, 1)

# --- APP CONFIG & UI ---
st.set_page_config(page_title="ProWheel Lab v5.3", layout="wide", page_icon="🚲")
init_db()

st.title("🚲 ProWheel Precision Lab v5.3")
st.markdown("---")

tabs = st.tabs(["📊 Workshop Dashboard", "➕ Register Build", "🧮 Precision Calc", "📦 Component Library"])

# --- TAB: DASHBOARD ---
with tabs[0]:
    df_display = run_query("""
        SELECT b.id, b.customer, b.status, b.date_added, 
               r.brand || ' ' || r.model as Rim, 
               h.brand || ' ' || h.model as Hub,
               b.f_l_len, b.f_r_len, b.r_l_len, b.r_r_len, b.notes
        FROM builds b
        LEFT JOIN rims r ON b.rim_id = r.id
        LEFT JOIN hubs h ON b.hub_id = h.id
    """)

    if not df_display.empty:
        # Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Active Jobs", len(df_display[df_display['status'] != "Build Complete"]))
        m2.metric("Ready to Lace", len(df_display[df_display['status'] == "Parts Received"]))
        m3.metric("Completed", len(df_display[df_display['status'] == "Build Complete"]))
        
        st.divider()
        search = st.text_input("🔍 Search customer or parts...")
        if search:
            df_display = df_display[df_display.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        # Status Update Utility
        with st.expander("🛠️ Update Job Status"):
            u_id = st.selectbox("Select Job ID", df_display['id'])
            u_stat = st.selectbox("New Status", ["Order Received", "Parts Ordered", "Parts Received", "Build Complete"])
            if st.button("Apply Status Change"):
                run_query("UPDATE builds SET status = ? WHERE id = ?", (u_stat, u_id))
                st.success(f"Job {u_id} updated.")
                st.rerun()
    else:
        st.info("No builds logged. Use the 'Register Build' tab.")

# --- TAB: REGISTER BUILD ---
with tabs[1]:
    st.header("Register New Customer Build")
    rims = run_query("SELECT id, brand, model FROM rims")
    hubs = run_query("SELECT id, brand, model FROM hubs")

    if rims.empty or hubs.empty:
        st.warning("⚠️ Please populate your Component Library before logging a build.")
    else:
        with st.form("build_form"):
            c1, c2 = st.columns(2)
            cust = c1.text_input("Customer Name")
            dt = c2.date_input("Start Date")

            r_map = {f"{r['brand']} {r['model']}": r['id'] for _, r in rims.iterrows()}
            h_map = {f"{h['brand']} {h['model']}": h['id'] for _, h in hubs.iterrows()}
            
            sel_r = st.selectbox("Select Rim", list(r_map.keys()))
            sel_h = st.selectbox("Select Hub", list(h_map.keys()))

            st.markdown("### Measured Spoke Lengths (mm)")
            sc1, sc2, sc3, sc4 = st.columns(4)
            fl = sc1.number_input("Front Left", step=0.1)
            fr = sc2.number_input("Front Right", step=0.1)
            rl = sc3.number_input("Rear Left", step=0.1)
            rr = sc4.number_input("Rear Right", step=0.1)
            
            note = st.text_area("Builder Notes")
            
            if st.form_submit_button("Save Build"):
                run_query("""INSERT INTO builds 
                             (customer, status, date_added, rim_id, hub_id, f_l_len, f_r_len, r_l_len, r_r_len, notes) 
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                          (cust, "Order Received", dt.strftime("%Y-%m-%d"), r_map[sel_r], h_map[sel_h], fl, fr, rl, rr, note))
                st.success("Build added to Workshop Dashboard!")
                st.rerun()

# --- TAB: PRECISION CALCULATOR ---
with tabs[2]:
    st.header("🧮 Straightpull & J-Bend Calculator")
    st.write("Calculations optimized to match industry-standard tangential geometry.")
    
    g1, g2, g3 = st.columns(3)
    c_erd = g1.number_input("Rim ERD (mm)", value=601.0, step=0.1)
    c_holes = g2.number_input("Total Hole Count", value=28, step=2)
    is_sp = g3.toggle("Straightpull Hub Geometry?", value=True)

    st.divider()
    
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("⬅️ Left Side (NDS)")
        l_fd = st.number_input("Left PCD (mm)", value=40.8, key="lfd")
        l_os = st.number_input("Left Flange Distance (mm)", value=28.0, key="los")
        l_sp_off = st.number_input("Left Spoke Offset (mm)", value=1.7, key="lsp") if is_sp else 0.0
        
        # We assume 3-cross for the SP logic provided in screenshot
        res_l = calculate_precision_spoke(c_erd, l_fd, l_os, c_holes, 3, is_sp, l_sp_off)
        st.metric("Left Spoke Length", f"{res_l} mm")
        if is_sp and c_erd == 601.0: st.caption("DT Swiss Target: 304.2 mm")

    with col_r:
        st.subheader("➡️ Right Side (DS)")
        r_fd = st.number_input("Right PCD (mm)", value=36.0, key="rfd")
        r_os = st.number_input("Right Flange Distance (mm)", value=40.2, key="ros")
        r_sp_off = st.number_input("Right Spoke Offset (mm)", value=1.8, key="rsp") if is_sp else 0.0
        
        res_r = calculate_precision_spoke(c_erd, r_fd, r_os, c_holes, 3, is_sp, r_sp_off)
        st.metric("Right Spoke Length", f"{res_r} mm")
        if is_sp and c_erd == 601.0: st.caption("DT Swiss Target: 305.5 mm")

# --- TAB: LIBRARY ---
with tabs[3]:
    st.header("📦 Component Library")
    lib1, lib2 = st.columns(2)
    
    with lib1:
        st.subheader("Add Rim")
        with st.form("rlib"):
            br, mo = st.text_input("Brand"), st.text_input("Model")
            er, ho = st.number_input("ERD"), st.number_input("Holes", value=28)
            if st.form_submit_button("Save Rim"):
                run_query("INSERT INTO rims (brand, model, erd, holes) VALUES (?,?,?,?)", (br, mo, er, ho))
                st.rerun()

    with lib2:
        st.subheader("Add Asymmetrical Hub")
        with st.form("hlib"):
            hb, hm = st.text_input("Hub Brand"), st.text_input("Hub Model")
            st.write("**Specs**")
            hfl, hfr = st.number_input("L-PCD"), st.number_input("R-PCD")
            hol, hor = st.number_input("L-Flange Dist"), st.number_input("R-Flange Dist")
            hsl, hsr = st.number_input("L-SP Offset"), st.number_input("R-SP Offset")
            if st.form_submit_button("Save Hub"):
                run_query("""INSERT INTO hubs (brand, model, fd_l, fd_r, os_l, os_r, sp_off_l, sp_off_r) 
                             VALUES (?,?,?,?,?,?,?,?)""", (hb, hm, hfl, hfr, hol, hor, hsl, hsr))
                st.rerun()
