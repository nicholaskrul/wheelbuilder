import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import math
from datetime import datetime

# --- APP CONFIG ---
st.set_page_config(page_title="ProWheel Lab v6.0", layout="wide", page_icon="🚲")

# --- GOOGLE SHEETS CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

# Helper function to refresh and get data
def get_worksheet_data(sheet_name):
    # ttl=0 ensures we get fresh data from Google, not a cached version
    return conn.read(worksheet=sheet_name, ttl=0)

# --- PRECISION CALC LOGIC ---
def calculate_precision_spoke(erd, fd, os, holes, crosses, is_sp, sp_offset):
    if 0 in [erd, fd, holes]: return 0.0
    r_rim, r_hub = erd / 2, fd / 2
    if not is_sp:
        # Standard J-Bend Geometry (3D Triangle)
        alpha_rad = math.radians((crosses * 720.0) / holes)
        length = math.sqrt(r_rim**2 + r_hub**2 + os**2 - 2 * r_rim * r_hub * math.cos(alpha_rad))
    else:
        # Precision Tangential Logic (Matches DT Swiss Accurate)
        d_tangent_2d = math.sqrt(max(0, r_rim**2 - r_hub**2))
        length = math.sqrt(d_tangent_2d**2 + os**2) + sp_offset
    return round(length, 1)

# --- UI LAYOUT ---
st.title("🚲 ProWheel Lab Portal")
st.markdown("---")

tabs = st.tabs(["📊 Dashboard", "🧮 Precision Calc", "📦 Component Library", "➕ Register Build"])

# --- TAB 1: DASHBOARD ---
with tabs[0]:
    st.subheader("Live Build Pipeline")
    try:
        df_builds = get_worksheet_data("builds")
        if not df_builds.empty:
            # Simple Status Filter
            status_filter = st.multiselect("Filter by Status", 
                                           options=df_builds['status'].unique(), 
                                           default=df_builds['status'].unique())
            filtered_df = df_builds[df_builds['status'].isin(status_filter)]
            st.dataframe(filtered_df, use_container_width=True, hide_index=True)
        else:
            st.info("The builds sheet is currently empty.")
    except Exception as e:
        st.error(f"Could not connect to 'builds' tab. Check your sheet headers. Error: {e}")

# --- TAB 2: PRECISION CALC ---
with tabs[1]:
    st.header("🧮 Side-Specific Calculator")
    
    
    g1, g2, g3 = st.columns(3)
    c_erd = g1.number_input("Rim ERD (mm)", value=601.0, step=0.1)
    c_holes = g2.number_input("Hole Count", value=28, step=2)
    is_sp = g3.toggle("Straightpull Geometry?", value=True)

    st.divider()
    col_l, col_r = st.columns(2)
    
    with col_l:
        st.subheader("⬅️ Left Side (NDS)")
        l_fd = st.number_input("Left PCD", value=40.8, key="lfd")
        l_os = st.number_input("Left Offset", value=28.0, key="los")
        l_sp = st.number_input("Left Spoke Offset", value=1.7, key="lsp") if is_sp else 0.0
        res_l = calculate_precision_spoke(c_erd, l_fd, l_os, c_holes, 3, is_sp, l_sp)
        st.metric("Suggested Length", f"{res_l} mm")

    with col_r:
        st.subheader("➡️ Right Side (DS)")
        r_fd = st.number_input("Right PCD", value=36.0, key="rfd")
        r_os = st.number_input("Right Offset", value=40.2, key="ros")
        r_sp = st.number_input("Right Spoke Offset", value=1.8, key="rsp") if is_sp else 0.0
        res_r = calculate_precision_spoke(c_erd, r_fd, r_os, c_holes, 3, is_sp, r_sp)
        st.metric("Suggested Length", f"{res_r} mm")

# --- TAB 3: COMPONENT LIBRARY ---
with tabs[2]:
    st.header("📦 Cloud Library")
    l1, l2 = st.columns(2)
    
    with l1:
        st.subheader("Add Rim")
        with st.form("add_rim_gs"):
            brand = st.text_input("Brand")
            model = st.text_input("Model")
            erd = st.number_input("ERD", step=0.1)
            holes = st.number_input("Holes", value=28)
            if st.form_submit_button("Upload to Cloud"):
                new_rim = pd.DataFrame([{"brand": brand, "model": model, "erd": erd, "holes": holes}])
                # Fetch existing, append, and update
                existing_rims = get_worksheet_data("rims")
                updated_rims = pd.concat([existing_rims, new_rim], ignore_index=True)
                conn.update(worksheet="rims", data=updated_rims)
                st.success("Rim saved to Google Sheets!")

    with l2:
        st.subheader("Add Hub")
        with st.form("add_hub_gs"):
            h_brand = st.text_input("Hub Brand")
            h_model = st.text_input("Hub Model")
            st.write("Left Specs")
            hfl, hol, hsl = st.number_input("L-PCD"), st.number_input("L-Dist"), st.number_input("L-Offset")
            st.write("Right Specs")
            hfr, hor, hsr = st.number_input("R-PCD"), st.number_input("R-Dist"), st.number_input("R-Offset")
            if st.form_submit_button("Upload to Cloud"):
                new_hub = pd.DataFrame([{"brand": h_brand, "model": h_model, "fd_l": hfl, "fd_r": hfr, 
                                         "os_l": hol, "os_r": hor, "sp_off_l": hsl, "sp_off_r": hsr}])
                existing_hubs = get_worksheet_data("hubs")
                updated_hubs = pd.concat([existing_hubs, new_hub], ignore_index=True)
                conn.update(worksheet="hubs", data=updated_hubs)
                st.success("Hub saved to Google Sheets!")

# --- TAB 4: REGISTER BUILD ---
with tabs[3]:
    st.header("Register New Build")
    try:
        df_rims = get_worksheet_data("rims")
        df_hubs = get_worksheet_data("hubs")

        with st.form("new_build_gs"):
            cust = st.text_input("Customer Name")
            status = st.selectbox("Stage", ["Order Received", "Parts Ordered", "Parts Received", "Build Complete"])
            
            # Selection from Sheets data
            sel_rim = st.selectbox("Select Rim", df_rims['brand'] + " " + df_rims['model'])
            sel_hub = st.selectbox("Select Hub", df_hubs['brand'] + " " + df_hubs['model'])
            
            st.write("Input Final Spoke Lengths")
            fl, fr, rl, rr = st.columns(4)
            val_fl = fl.number_input("F-L", step=0.1)
            val_fr = fr.number_input("F-R", step=0.1)
            val_rl = rl.number_input("R-L", step=0.1)
            val_rr = rr.number_input("R-R", step=0.1)
            
            notes = st.text_area("Builder Notes")
            
            if st.form_submit_button("Log Build to Sheets"):
                new_build = pd.DataFrame([{
                    "customer": cust, "status": status, "date_added": datetime.now().strftime("%Y-%m-%d"),
                    "f_l_len": val_fl, "f_r_len": val_fr, "r_l_len": val_rl, "r_r_len": val_rr, "notes": notes
                }])
                existing_builds = get_worksheet_data("builds")
                updated_builds = pd.concat([existing_builds, new_build], ignore_index=True)
                conn.update(worksheet="builds", data=updated_builds)
                st.success("Project logged successfully!")
    except:
        st.warning("Populate your Rims and Hubs sheets first!")

