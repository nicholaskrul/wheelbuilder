import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import math
from datetime import datetime

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="ProWheel Lab v8.9", layout="wide", page_icon="🚲")

# --- 2. GOOGLE SHEETS CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_worksheet_data(sheet_name, force_refresh=False):
    # Intelligent caching to manage API Quota (10 mins)
    return conn.read(worksheet=sheet_name, ttl=0 if force_refresh else 600)

# --- 3. PRECISION CALCULATION LOGIC ---
def calculate_precision_spoke(erd, fd, os, holes, crosses, is_sp, sp_offset, hole_diam=2.4, round_mode="None"):
    if 0 in [erd, fd, holes]: return 0.0
    r_rim, r_hub = erd / 2, fd / 2
    if not is_sp:
        alpha_rad = math.radians((crosses * 720.0) / holes)
        l_sq = (r_rim**2) + (r_hub**2) + (os**2) - (2 * r_rim * r_hub * math.cos(alpha_rad))
        length = math.sqrt(max(0, l_sq)) - (hole_diam / 2)
    else:
        d_tangent_2d = math.sqrt(max(0, r_rim**2 - r_hub**2))
        length = math.sqrt(d_tangent_2d**2 + os**2) + sp_offset
    
    if round_mode == "Nearest Even": return float(round(length / 2) * 2)
    elif round_mode == "Nearest Odd": return float(round((length - 1) / 2) * 2 + 1)
    return round(length, 1)

# --- 4. SESSION STATE INITIALIZATION ---
if 'active_tab' not in st.session_state: st.session_state.active_tab = "📊 Dashboard"
if 'edit_customer' not in st.session_state: st.session_state.edit_customer = None

# Stage lengths from calculator
for key in ['f_l', 'f_r', 'r_l', 'r_r']:
    if key not in st.session_state: st.session_state[key] = 0.0

def trigger_edit(customer_name):
    st.session_state.edit_customer = customer_name
    st.session_state.active_tab = "➕ Register Build" # Force tab switch

# --- 5. MAIN USER INTERFACE ---
st.title("🚲 ProWheel Lab v8.9: Seamless Edit Suite")
st.markdown("---")

# Use session state to control which tab is visible
tab_list = ["📊 Dashboard", "🧮 Precision Calc", "📦 Library", "➕ Register Build", "📄 Spec Sheet"]
active_idx = tab_list.index(st.session_state.active_tab)

tabs = st.tabs(tab_list)

# --- TAB: DASHBOARD ---
with tabs[0]:
    st.subheader("🏁 Workshop Pipeline")
    if st.button("🔄 Force Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    try:
        df_b = get_worksheet_data("builds")
        if not df_b.empty:
            for index, row in df_b.iterrows():
                col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
                status_icon = "✅" if row.get('status') == "Complete" else "🛠️"
                col1.write(f"{status_icon} **{row['customer']}**")
                col2.write(f"📅 {row['date']}")
                col3.write(f"**Status:** {row.get('status', 'Order received')}")
                if col4.button("Edit", key=f"edit_btn_{index}"):
                    trigger_edit(row['customer'])
                    st.rerun()
    except Exception as e: st.error(f"Dashboard sync error: {e}")

# --- TAB: PRECISION CALC ---
with tabs[1]:
    st.header("🧮 Spoke Calculator")
    try:
        df_rims, df_hubs = get_worksheet_data("rims"), get_worksheet_data("hubs")
        calc_mode = st.radio("Source", ["Use Library", "Manual Entry"], horizontal=True)
        
        if calc_mode == "Use Library" and not df_rims.empty and not df_hubs.empty:
            cl1, cl2 = st.columns(2)
            rim_sel = cl1.selectbox("Select Rim", df_rims['brand'] + " " + df_rims['model'])
            hub_sel = cl2.selectbox("Select Hub", df_hubs['brand'] + " " + df_hubs['model'])
            sel_r = df_rims[(df_rims['brand'] + " " + df_rims['model']) == rim_sel].iloc[0]
            sel_h = df_hubs[(df_hubs['brand'] + " " + df_hubs['model']) == hub_sel].iloc[0]
            erd, holes_init = sel_r['erd'], int(sel_r['holes'])
            l_fd, r_fd, l_os, r_os = sel_h['fd_l'], sel_h['fd_r'], sel_h['os_l'], sel_h['os_r']
            l_sp, r_sp = sel_h['sp_off_l'], sel_h['sp_off_r']
        else:
            erd, holes_init = st.number_input("ERD", 601.0), 28
            l_fd, r_fd, l_os, r_os, l_sp, r_sp = 40.8, 36.0, 28.0, 40.2, 1.7, 1.8

        st.divider()
        i1, i2, i3 = st.columns(3)
        holes = i1.number_input("Spoke Count", value=holes_init, step=2)
        l_cross, r_cross = i2.selectbox("L-Cross", [0,1,2,3,4], index=3), i3.selectbox("R-Cross", [0,1,2,3,4], index=3)
        is_sp, r_mode = st.toggle("Straightpull?", value=True), st.selectbox("Rounding", ["None", "Nearest Even", "Nearest Odd"])
        
        res_l = calculate_precision_spoke(erd, l_fd, l_os, holes, l_cross, is_sp, l_sp, 2.4, r_mode)
        res_r = calculate_precision_spoke(erd, r_fd, r_os, holes, r_cross, is_sp, r_sp, 2.4, r_mode)
        
        mc1, mc2 = st.columns(2)
        mc1.metric("L Spoke", f"{res_l} mm")
        mc2.metric("R Spoke", f"{res_r} mm")
        
        side = st.radio("Stage to Wheel:", ["Front", "Rear"], horizontal=True)
        if st.button("Apply and Stage"):
            if side == "Front": st.session_state.f_l, st.session_state.f_r = res_l, res_r
            else: st.session_state.r_l, st.session_state.r_r = res_l, res_r
            st.success(f"{side} staged!")
    except Exception as e: st.error(f"Calculator Error: {e}")

# --- TAB: COMPONENT LIBRARY ---
with tabs[2]:
    st.header("📦 Library Management")
    l_type = st.selectbox("Category", ["Rims", "Hubs", "Spokes", "Nipples"])
    with st.form("lib_form_v89", clear_on_submit=True):
        b, m = st.text_input("Brand"), st.text_input("Model")
        w = st.number_input("Weight (g)", step=0.1)
        if st.form_submit_button("Save Component"):
            if l_type == "Rims":
                new = pd.DataFrame([{"brand":b, "model":m, "erd":0.0, "holes":0, "weight":w}])
                conn.update(worksheet="rims", data=pd.concat([get_worksheet_data("rims",True), new], ignore_index=True))
            elif l_type == "Hubs":
                new = pd.DataFrame([{"brand":b, "model":m, "fd_l":0.0, "fd_r":0.0, "os_l":0.0, "os_r":0.0, "sp_off_l":0.0, "sp_off_r":0.0, "weight":w}])
                conn.update(worksheet="hubs", data=pd.concat([get_worksheet_data("hubs",True), new], ignore_index=True))
            else:
                new = pd.DataFrame([{"brand":b, "model":m, "weight":w}])
                conn.update(worksheet=l_type.lower(), data=pd.concat([get_worksheet_data(l_type.lower(),True), new], ignore_index=True))

# --- TAB: REGISTER BUILD (NOW FULLY EDITABLE) ---
with tabs[3]:
    st.header("📝 Register / Update Build")
    try:
        df_builds, df_rims, df_hubs = get_worksheet_data("builds"), get_worksheet_data("rims"), get_worksheet_data("hubs")
        df_spokes, df_nipples = get_worksheet_data("spokes"), get_worksheet_data("nipples")
        
        mode = "Update Existing" if st.session_state.edit_customer else "New Build"
        
        with st.form("build_form_v89"):
            if mode == "New Build":
                cust = st.text_input("Customer Name")
            else:
                cust_list = list(df_builds['customer'])
                def_idx = cust_list.index(st.session_state.edit_customer) if st.session_state.edit_customer in cust_list else 0
                cust = st.selectbox("Editing Project:", cust_list, index=def_idx)
            
            # Form fields
            stat = st.selectbox("Status", ["Order received", "Awaiting parts", "Parts received", "Build in progress", "Complete"])
            rim = st.selectbox("Rim", df_rims['brand'] + " " + df_rims['model'])
            fh, rh = st.selectbox("Front Hub", df_hubs['brand'] + " " + df_hubs['model']), st.selectbox("Rear Hub", df_hubs['brand'] + " " + df_hubs['model'])
            sp, ni = st.selectbox("Spoke", df_spokes['brand'] + " " + df_spokes['model']), st.selectbox("Nipple", df_nipples['brand'] + " " + df_nipples['model'])
            sc1, sc2, sc3, sc4 = st.columns(4)
            vfl, vfr = sc1.number_input("F-L", value=st.session_state.f_l), sc2.number_input("F-R", value=st.session_state.f_r)
            vrl, vrr = sc3.number_input("R-L", value=st.session_state.r_l), sc4.number_input("R-R", value=st.session_state.r_r)
            inv, notes = st.text_input("Invoice URL"), st.text_area("Notes")
            
            if st.form_submit_button("💾 Save Build Data"):
                entry = {"date":datetime.now().strftime("%Y-%m-%d"), "customer":cust, "status":stat, "f_hub":fh, "r_hub":rh, "rim":rim, "spoke":sp, "nipple":ni, "f_l":vfl, "f_r":vfr, "r_l":vrl, "r_r":vrr, "invoice_url":inv, "notes":notes}
                if mode == "Update Existing": 
                    df_builds = df_builds[df_builds['customer'] != cust]
                
                conn.update(worksheet="builds", data=pd.concat([df_builds, pd.DataFrame([entry])], ignore_index=True))
                st.session_state.edit_customer = None
                st.session_state.active_tab = "📊 Dashboard" # Return to home
                st.success("Synced!")
                st.rerun()
    except Exception as e: st.warning(f"Registration Error: {e}")

# --- TAB: SPEC SHEET ---
with tabs[4]:
    st.header("📄 Spec Sheet")
    df_builds = get_worksheet_data("builds")
    if not df_builds.empty:
        target = st.selectbox("Select Project", df_builds['customer'])
        d = df_builds[df_builds['customer'] == target].iloc[0]
        st.markdown(f"### Build Portfolio: **{target}**")
        st.write(f"**Status:** {d.get('status', 'N/A')} | **Date:** {d['date']}")
        st.info(f"**Front:** L {d['f_l']} / R {d['f_r']} mm")
        st.success(f"**Rear:** L {d['r_l']} / R {d['r_r']} mm")
