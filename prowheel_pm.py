import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import math
from datetime import datetime

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Wheelbuilder Lab", layout="wide", page_icon="🚲")

# --- 2. GOOGLE SHEETS CONNECTION ---
# cite: 6
conn = st.connection("gsheets", type=GSheetsConnection)

def get_worksheet_data(sheet_name, force_refresh=False):
    # Set ttl to 600 seconds (10 mins) to prevent 429 Quota errors.
    return conn.read(worksheet=sheet_name, ttl=0 if force_refresh else 600)

# --- 3. RE-CALIBRATED CALCULATION LOGIC ---
# cite: 5, 6
def calculate_precision_spoke(erd, fd, os, holes, crosses, is_sp, sp_offset, hole_diam=2.4, round_mode="None"):
    if 0 in [erd, fd, holes]: return 0.0
    r_rim, r_hub = erd / 2, fd / 2
    
    if not is_sp:
        # Standard J-Bend Geometry (Matches v6.4 accuracy)
        alpha_rad = math.radians((crosses * 720.0) / holes)
        l_sq = (r_rim**2) + (r_hub**2) + (os**2) - (2 * r_rim * r_hub * math.cos(alpha_rad))
        # Deduction of half-hole diameter (approx 1.2mm)
        length = math.sqrt(max(0, l_sq)) - (hole_diam / 2)
    else:
        # Straightpull Logic (Matches 304.2 / 305.5 benchmarks)
        d_tangent_2d = math.sqrt(max(0, r_rim**2 - r_hub**2))
        length = math.sqrt(d_tangent_2d**2 + os**2) + sp_offset
        
    # --- ROUNDING LOGIC ---
    if round_mode == "Nearest Even":
        return float(round(length / 2) * 2)
    elif round_mode == "Nearest Odd":
        return float(round((length - 1) / 2) * 2 + 1)
    return round(length, 1)

# Initialize Session State for staging lengths across tabs
for key in ['f_l', 'f_r', 'r_l', 'r_r']:
    if key not in st.session_state: st.session_state[key] = 0.0

# --- 4. MAIN USER INTERFACE ---
st.title("🚲 Wheelbuilder Lab: Wheel Build Portfolio Suite")
st.markdown("---")

tabs = st.tabs(["📊 Dashboard", "🧮 Precision Spoke Calc", "📦 Library", "➕ Register Build", "📄 Spec Sheet"])

# --- TAB: DASHBOARD ---
with tabs[0]:
    st.subheader("🏁 Workshop Pipeline")
    if st.button("🔄 Force Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    try:
        df_b = get_worksheet_data("builds")
        if not df_b.empty:
            st.dataframe(df_b, use_container_width=True, hide_index=True)
        else:
            st.info("No builds found. Populate your Library and Register a Build.")
    except Exception as e:
        st.error(f"Connect to 'builds' tab failed: {e}")

# --- TAB: SPOKE CALC ---
with tabs[1]:
    st.header("🧮 Integrated Calculator & Weight Estimator")
    try:
        df_rims = get_worksheet_data("rims")
        df_hubs = get_worksheet_data("hubs")
        df_spokes = get_worksheet_data("spokes")
        df_nipples = get_worksheet_data("nipples")

        calc_mode = st.radio("Source", ["Use Library", "Manual Entry"], horizontal=True)

        if calc_mode == "Use Library" and not df_rims.empty and not df_hubs.empty:
            c1, c2 = st.columns(2)
            rim_choice = c1.selectbox("Select Rim", df_rims['brand'] + " " + df_rims['model'])
            hub_choice = c2.selectbox("Select Hub", df_hubs['brand'] + " " + df_hubs['model'])
            sel_r = df_rims[(df_rims['brand'] + " " + df_rims['model']) == rim_choice].iloc[0]
            sel_h = df_hubs[(df_hubs['brand'] + " " + df_hubs['model']) == hub_choice].iloc[0]
            erd, holes, rim_w, hub_w = sel_r['erd'], sel_r['holes'], sel_r.get('weight',0), sel_h.get('weight',0)
            l_fd, r_fd, l_os, r_os = sel_h['fd_l'], sel_h['fd_r'], sel_h['os_l'], sel_h['os_r']
            l_sp, r_sp = sel_h['sp_off_l'], sel_h['sp_off_r']
        else:
            m1, m2 = st.columns(2)
            erd, holes = m1.number_input("Rim ERD", 601.0), m2.number_input("Holes", 28)
            l_fd, r_fd, l_os, r_os = 40.8, 36.0, 28.0, 40.2
            l_sp, r_sp, rim_w, hub_w = 1.7, 1.8, 0, 0

        st.divider()
        r1, r2 = st.columns(2)
        is_sp = r1.toggle("Straightpull Hub?", value=True)
        r_mode = r2.selectbox("Rounding Mode", ["None", "Nearest Even", "Nearest Odd"])
        h_diam = st.slider("Hole Diameter (mm)", 2.0, 3.0, 2.4)
        l_c, r_c = st.selectbox("L-Cross Pattern", [0,1,2,3], index=3), st.selectbox("R-Cross Pattern", [0,1,2,3], index=3)

        res_l = calculate_precision_spoke(erd, l_fd, l_os, holes, l_c, is_sp, l_sp, h_diam, r_mode)
        res_r = calculate_precision_spoke(erd, r_fd, r_os, holes, r_c, is_sp, r_sp, h_diam, r_mode)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Left Spoke", f"{res_l} mm")
        col2.metric("Right Spoke", f"{res_r} mm")

        if not df_spokes.empty and not df_nipples.empty:
            sw = df_spokes.iloc[0]['weight_per_spoke']
            nw = df_nipples.iloc[0]['weight_per_nipple']
            total_est = rim_w + hub_w + (sw * holes) + (nw * holes)
            col3.metric("Est. Weight", f"{round(total_est, 1)} g")

        st.subheader("🛠️ Push to Build Form")
        side = st.radio("Target Side:", ["Front", "Rear"], horizontal=True)
        if st.button("Apply and Stage"):
            if side == "Front":
                st.session_state.f_l, st.session_state.f_r = res_l, res_r
            else:
                st.session_state.r_l, st.session_state.r_r = res_l, res_r
            st.success(f"{side} staged!")
    except Exception as e:
        st.error(f"Calculator error: {e}")

# --- TAB: COMPONENT LIBRARY ---
with tabs[2]:
    st.header("📦 Library Management")
    l_type = st.selectbox("Category", ["Rims", "Hubs", "Spokes", "Nipples"])
    with st.form("lib_f_final", clear_on_submit=True):
        if l_type == "Rims":
            b, m, e, h, w = st.text_input("Brand"), st.text_input("Model"), st.number_input("ERD"), st.number_input("Holes"), st.number_input("Weight (g)")
            if st.form_submit_button("Upload Rim"):
                new = pd.DataFrame([{"brand":b, "model":m, "erd":e, "holes":h, "weight":w}])
                conn.update(worksheet="rims", data=pd.concat([get_worksheet_data("rims",True), new], ignore_index=True))
        elif l_type == "Hubs":
            b, m = st.text_input("Brand"), st.text_input("Model")
            fl, fr, ol, orr, sl, sr, w = st.number_input("L-PCD"), st.number_input("R-PCD"), st.number_input("L-Dist"), st.number_input("R-Dist"), st.number_input("L-SP Off"), st.number_input("R-SP Off"), st.number_input("Weight (g)")
            if st.form_submit_button("Upload Hub"):
                new = pd.DataFrame([{"brand":b, "model":m, "fd_l":fl, "fd_r":fr, "os_l":ol, "os_r":orr, "sp_off_l":sl, "sp_off_r":sr, "weight":w}])
                conn.update(worksheet="hubs", data=pd.concat([get_worksheet_data("hubs",True), new], ignore_index=True))
        elif l_type == "Spokes":
            b, m, w = st.text_input("Brand"), st.text_input("Model"), st.number_input("Weight (g)", step=0.01)
            if st.form_submit_button("Upload Spoke"):
                new = pd.DataFrame([{"brand":b, "model":m, "weight_per_spoke":w}])
                conn.update(worksheet="spokes", data=pd.concat([get_worksheet_data("spokes",True), new], ignore_index=True))
        elif l_type == "Nipples":
            b, m, w = st.text_input("Brand"), st.text_input("Model"), st.number_input("Weight (g)", step=0.01)
            if st.form_submit_button("Upload Nipple"):
                new = pd.DataFrame([{"brand":b, "model":m, "weight_per_nipple":w}])
                conn.update(worksheet="nipples", data=pd.concat([get_worksheet_data("nipples",True), new], ignore_index=True))

# --- TAB: REGISTER BUILD ---
with tabs[3]:
    st.header("📝 Register Build Portfolio")
    try:
        df_builds = get_worksheet_data("builds")
        df_rims = get_worksheet_data("rims")
        df_hubs = get_worksheet_data("hubs")
        df_spokes = get_worksheet_data("spokes")
        df_nipples = get_worksheet_data("nipples")
        
        mode = st.radio("Action", ["New Build", "Update Existing"], horizontal=True)
        with st.form("build_form_v75", clear_on_submit=True):
            cust = st.text_input("Customer Name") if mode == "New Build" else st.selectbox("Project", df_builds['customer'])
            status = st.selectbox("Build Status", ["Order Received", "Parts Ordered", "Ready to Lace", "Build Complete"])
            
            sel_r = st.selectbox("Assign Rim", df_rims['brand'] + " " + df_rims['model'])
            sel_h = st.selectbox("Assign Hub", df_hubs['brand'] + " " + df_hubs['model'])
            sel_s = st.selectbox("Assign Spokes", df_spokes['brand'] + " " + df_spokes['model'])
            sel_n = st.selectbox("Assign Nipples", df_nipples['brand'] + " " + df_nipples['model'])

            c1, c2, c3, c4 = st.columns(4)
            vfl, vfr = c1.number_input("F-L", value=st.session_state.f_l), c2.number_input("F-R", value=st.session_state.f_r)
            vrl, vrr = c3.number_input("R-L", value=st.session_state.r_l), c4.number_input("R-R", value=st.session_state.r_r)
            
            notes = st.text_area("Workshop Notes")
            if st.form_submit_button("Commit to Cloud"):
                entry = {"customer":cust, "status":status, "date":datetime.now().strftime("%Y-%m-%d"), 
                         "rim":sel_r, "hub":sel_h, "spoke":sel_s, "nipple":sel_n,
                         "f_l":vfl, "f_r":vfr, "r_l":vrl, "r_r":vrr, "notes":notes}
                if mode == "Update Existing": df_builds = df_builds[df_builds['customer'] != cust]
                conn.update(worksheet="builds", data=pd.concat([df_builds, pd.DataFrame([entry])], ignore_index=True))
                st.success("Synced!")
                st.rerun()
    except Exception as e:
        st.warning(f"Error: {e}")

# --- TAB: CUSTOMER SPEC SHEET ---
with tabs[4]:
    st.header("📄 Build Portfolio & Customer Spec Sheet")
    df_builds = get_worksheet_data("builds")
    if not df_builds.empty:
        target = st.selectbox("Select Build", df_builds['customer'])
        data = df_builds[df_builds['customer'] == target].iloc[0]
        
        st.markdown(f"## {target}'s Build Spec")
        st.write(f"**Date:** {data['date']} | **Status:** {data['status']}")
        
        st.divider()
        st.markdown("#### 📦 Components")
        c1, c2, c3, c4 = st.columns(4)
        c1.write(f"**Rim:** {data.get('rim','N/A')}")
        c2.write(f"**Hub:** {data.get('hub','N/A')}")
        c3.write(f"**Spokes:** {data.get('spoke','N/A')}")
        c4.write(f"**Nipples:** {data.get('nipple','N/A')}")

        st.divider()
        s1, s2 = st.columns(2)
        with s1:
            st.info("**FRONT WHEEL**")
            st.write(f"- Non-Drive Side: {data['f_l']} mm")
            st.write(f"- Drive Side: {data['f_r']} mm")
        with s2:
            st.success("**REAR WHEEL**")
            st.write(f"- Non-Drive Side: {data['r_l']} mm")
            st.write(f"- Drive Side: {data['r_r']} mm")

        st.markdown("---")
        st.write(f"**Workshop Notes:** {data['notes']}")
        
        if st.button("Download Spec Card"):
            out = f"PROWHEEL LAB - {target}\nComponents:\n- Rim: {data.get('rim','N/A')}\n- Hub: {data.get('hub','N/A')}\n- Spoke: {data.get('spoke','N/A')}\n- Nipple: {data.get('nipple','N/A')}\n\nFRONT: L {data['f_l']} / R {data['f_r']}\nREAR: L {data['r_l']} / R {data['r_r']}"
            st.download_button("Download", out, f"{target}_Specs.txt")



