import streamlit as st
import pandas as pd
import sqlite3
import math
from datetime import datetime

# --- DATABASE ENGINE ---
# Renaming the file forces Streamlit to create a brand new, clean database.
DB_FILE = 'prowheel_final.db'

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

# --- DT SWISS MATCHING FORMULA ---
def calculate_precision_spoke(erd, fd, os, holes, crosses, is_sp, sp_offset):
    if 0 in [erd, fd, holes]: return 0.0
    r_rim, r_hub = erd / 2, fd / 2
    if not is_sp:
        alpha_rad = math.radians((crosses * 720.0) / holes)
        length = math.sqrt(r_rim**2 + r_hub**2 + os**2 - 2 * r_rim * r_hub * math.cos(alpha_rad))
    else:
        # Precision Tangential Logic
        d_tangent_2d = math.sqrt(max(0, r_rim**2 - r_hub**2))
        length = math.sqrt(d_tangent_2d**2 + os**2) + sp_offset
    return round(length, 1)

# --- UI SETUP ---
st.set_page_config(page_title="ProWheel Lab v5.4", layout="wide")
init_db()

st.title("🚲 ProWheel Precision Lab v5.4")
tabs = st.tabs(["📊 Dashboard", "➕ Register Build", "🧮 Precision Calc", "📦 Library"])

# --- TAB: PRECISION CALCULATOR ---
with tabs[2]:
    st.header("🧮 Precision Calculator")
    g1, g2, g3 = st.columns(3)
    c_erd = g1.number_input("Rim ERD (mm)", value=601.0)
    c_holes = g2.number_input("Hole Count", value=28)
    is_sp = g3.toggle("Straightpull?", value=True)

    st.divider()
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("⬅️ Left Side (NDS)")
        l_fd = st.number_input("Left PCD", value=40.8)
        l_os = st.number_input("Left Offset", value=28.0)
        l_sp = st.number_input("Left Spoke Offset", value=1.7) if is_sp else 0.0
        st.metric("Length", f"{calculate_precision_spoke(c_erd, l_fd, l_os, c_holes, 3, is_sp, l_sp)} mm")

    with col_r:
        st.subheader("➡️ Right Side (DS)")
        r_fd = st.number_input("Right PCD", value=36.0)
        r_os = st.number_input("Right Offset", value=40.2)
        r_sp = st.number_input("Right Spoke Offset", value=1.8) if is_sp else 0.0
        st.metric("Length", f"{calculate_precision_spoke(c_erd, r_fd, r_os, c_holes, 3, is_sp, r_sp)} mm")

# --- TAB: LIBRARY ---
with tabs[3]:
    st.header("📦 Component Library")
    l1, l2 = st.columns(2)
    with l1:
        with st.form("rim_add"):
            rb, rm, re, rh = st.text_input("Rim Brand"), st.text_input("Model"), st.number_input("ERD"), st.number_input("Holes", value=28)
            if st.form_submit_button("Save Rim"):
                run_query("INSERT INTO rims (brand, model, erd, holes) VALUES (?,?,?,?)", (rb, rm, re, rh))
    with l2:
        with st.form("hub_add"):
            hb, hm = st.text_input("Hub Brand"), st.text_input("Hub Model")
            hfl, hol, hsl = st.number_input("L-PCD"), st.number_input("L-Dist"), st.number_input("L-SP Off")
            hfr, hor, hsr = st.number_input("R-PCD"), st.number_input("R-Dist"), st.number_input("R-SP Off")
            if st.form_submit_button("Save Hub"):
                run_query("INSERT INTO hubs (brand, model, fd_l, fd_r, os_l, os_r, sp_off_l, sp_off_r) VALUES (?,?,?,?,?,?,?,?)", (hb, hm, hfl, hfr, hol, hor, hsl, hsr))

# --- TAB: DASHBOARD ---
with tabs[0]:
    df = run_query("SELECT b.id, b.customer, b.status, r.model as Rim, h.model as Hub FROM builds b LEFT JOIN rims r ON b.rim_id = r.id LEFT JOIN hubs h ON b.hub_id = h.id")
    st.dataframe(df, use_container_width=True)

# --- TAB: REGISTER ---
with tabs[1]:
    # Form logic to register builds based on library selection...
    st.info("Add components to the Library first.")
