import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# --- DATABASE FUNCTIONS ---
def init_db():
    conn = sqlite3.connect('wheel_shop.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS builds
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  customer TEXT, status TEXT, date_added TEXT,
                  rim_model TEXT, rim_holes INTEGER,
                  hub_model TEXT, hub_type TEXT,
                  f_ds REAL, f_nds REAL, r_ds REAL, r_nds REAL,
                  notes TEXT)''')
    conn.commit()
    conn.close()

def save_build(data):
    conn = sqlite3.connect('wheel_shop.db')
    c = conn.cursor()
    c.execute('''INSERT INTO builds (customer, status, date_added, rim_model, rim_holes, hub_model, hub_type, f_ds, f_nds, r_ds, r_nds, notes)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', data)
    conn.commit()
    conn.close()

def update_status(build_id, new_status):
    conn = sqlite3.connect('wheel_shop.db')
    c = conn.cursor()
    c.execute("UPDATE builds SET status = ? WHERE id = ?", (new_status, build_id))
    conn.commit()
    conn.close()

def delete_build(build_id):
    conn = sqlite3.connect('wheel_shop.db')
    c = conn.cursor()
    c.execute("DELETE FROM builds WHERE id = ?", (build_id,))
    conn.commit()
    conn.close()

def load_builds():
    conn = sqlite3.connect('wheel_shop.db')
    df = pd.read_sql_query("SELECT * FROM builds", conn)
    conn.close()
    return df

# --- APP UI ---
init_db()
st.set_page_config(page_title="Pro Wheel Lab", layout="wide")

# Sidebar for new entries (keeping your existing logic)
with st.sidebar:
    st.header("🛠️ New Job Card")
    with st.form("job_form", clear_on_submit=True):
        cust = st.text_input("Customer Name")
        stat = st.selectbox("Stage", ["Order Received", "Parts Ordered", "Parts Received", "Build Complete"])
        r_mod = st.text_input("Rim Model")
        r_hole = st.number_input("Holes", 16, 36, 28)
        h_mod = st.text_input("Hub Model")
        h_type = st.selectbox("Freehub", ["HG", "MS", "XDR", "Fixed"])
        
        st.write("**Spoke Lengths (mm)**")
        c1, c2 = st.columns(2)
        fds = c1.number_input("F-DS", 0.0, 310.0, 0.0)
        fnds = c2.number_input("F-NDS", 0.0, 310.0, 0.0)
        rds = c1.number_input("R-DS", 0.0, 310.0, 0.0)
        rnds = c2.number_input("R-NDS", 0.0, 310.0, 0.0)
        notes = st.text_area("Notes")
        
        if st.form_submit_button("Save Build"):
            save_build((cust, stat, datetime.now().strftime("%Y-%m-%d"), r_mod, r_hole, h_mod, h_type, fds, fnds, rds, rnds, notes))
            st.rerun()

# --- MAIN DASHBOARD ---
st.title("🚲 Wheelbuilding Project Manager")
df = load_builds()

if not df.empty:
    # 1. Metrics
    m1, m2, m3 = st.columns(3)
    pending = df[df['status'] != "Build Complete"]
    m1.metric("Active Builds", len(pending))
    m2.metric("Awaiting Parts", len(df[df['status'] == "Parts Ordered"]))
    m3.metric("Ready to Lace", len(df[df['status'] == "Parts Received"]))

    # 2. The Action Center (Edit/Delete)
    with st.expander("⚡ Quick Actions (Update Status or Delete)"):
        col_sel, col_stat, col_btn = st.columns([2, 2, 1])
        
        # Create a display name for the dropdown: "ID: Customer Name (Current Status)"
        pending_options = {f"{row['id']}: {row['customer']} ({row['status']})": row['id'] for _, row in df.iterrows()}
        selected_label = col_sel.selectbox("Select Build", options=list(pending_options.keys()))
        selected_id = pending_options[selected_label]
        
        new_stat = col_stat.selectbox("Set New Status", ["Order Received", "Parts Ordered", "Parts Received", "Build Complete"])
        
        btn_col1, btn_col2 = col_btn.columns(2)
        if btn_col1.button("✅ Update"):
            update_status(selected_id, new_stat)
            st.success("Status Updated!")
            st.rerun()
            
        if btn_col2.button("🗑️ Delete"):
            delete_build(selected_id)
            st.warning("Build Deleted.")
            st.rerun()

    # 3. Data Display
    st.divider()
    search = st.text_input("🔍 Search Customers, Rims, or Hubs...")
    if search:
        df = df[df.stack().str.contains(search, case=False, na=False).groupby(level=0).any()]
    
    st.dataframe(df.sort_values(by="id", ascending=False), use_container_width=True, hide_index=True)

else:

    st.info("No builds in the system yet.")
