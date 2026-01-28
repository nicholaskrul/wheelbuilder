import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import math
from datetime import datetime

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Wheelbuilder Lab v11.3", layout="wide", page_icon="🚲")

# --- 2. GOOGLE SHEETS CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_worksheet_data(sheet_name, force_refresh=False):
    """
    Fetches data with a 15-minute cache to respect API rate limits.
   
    """
    return conn.read(worksheet=sheet_name, ttl=0 if force_refresh else 900)

# --- 3. PRECISION CALCULATION LOGIC ---
def calculate_precision_spoke(erd, fd, os, holes, crosses, is_sp, sp_offset, hole_diam=2.4, round_mode="None"):
    """
    Calculates spoke length for J-Bend and Straightpull geometries.
    Refined in v11.3 for better radial SP accuracy.
    """
    if 0 in [erd, fd, holes]: return 0.0
    r_rim, r_hub = erd / 2, fd / 2
    
    if not is_sp:
        # Standard J-Bend Geometry
        alpha_rad = math.radians((crosses * 720.0) / holes)
        l_sq = (r_rim**2) + (r_hub**2) + (os**2) - (2 * r_rim * r_hub * math.cos(alpha_rad))
        length = math.sqrt(max(0, l_sq)) - (hole_diam / 2)
    else:
        # Refined Straightpull Logic
        # Calculates tangential path for non-zero crosses or radial SP offsets
        d_tangent_2d = math.sqrt(max(0, r_rim**2 - r_hub**2))
        length = math.sqrt(d_tangent_2d**2 + os**2) + sp_offset
    
    if round_mode == "Nearest Even": return float(round(length / 2) * 2)
    elif round_mode == "Nearest Odd": return float(round((length - 1) / 2) * 2 + 1)
    return round(length, 1)

# --- 4. SESSION STATE & NAVIGATION ---
if 'active_tab' not in st.session_state: st.session_state.active_tab = "📊 Dashboard"
if 'edit_customer' not in st.session_state: st.session_state.edit_customer = None
if 'staged_holes' not in st.session_state: st.session_state.staged_holes = 28

for key in ['f_l', 'f_r', 'r_l', 'r_r']:
    if key not in st.session_state: st.session_state[key] = 0.0

def trigger_edit(customer_name):
    st.session_state.edit_customer = customer_name
    st.session_state.active_tab = "➕ Register Build"

# --- 5. MAIN USER INTERFACE ---
st.title("🚲 Wheelbuilder Lab")
st.markdown("---")

tab_list = ["📊 Dashboard", "🧮 Precision Calc", "📦 Library", "📦 Inventory", "➕ Register Build", "📄 Spec Sheet"]
active_idx = tab_list.index(st.session_state.active_tab) if st.session_state.active_tab in tab_list else 0
tabs = st.tabs(tab_list)

# --- TAB: DASHBOARD ---
with tabs[0]:
    st.subheader("🏁 Workshop Pipeline")
    if st.button("🔄 Refresh Pipeline"):
        st.cache_data.clear()
        st.rerun()
    try:
        df_b = get_worksheet_data("builds")
        if not df_b.empty:
            for index, row in df_b.iterrows():
                col1, col2, col3, col4 = st.columns([2, 1.5, 2, 1])
                status_icon = "✅" if row.get('status') == "Complete" else "🛠️"
                col1.write(f"{status_icon} **{row['customer']}**")
                col2.write(f"📅 {row['date']}")
                col3.write(f"**Status:** {row.get('status', 'Order received')}")
                if col4.button("Edit", key=f"edit_btn_{index}"):
                    trigger_edit(row['customer'])
                    st.rerun()
    except Exception as e: st.error(f"Dashboard Sync error: {e}")

# --- TAB: PRECISION CALC ---
with tabs[1]:
    st.header("🧮 Spoke Calculator")
    try:
        df_rims, df_hubs = get_worksheet_data("rims"), get_worksheet_data("hubs")
        cl1, cl2 = st.columns(2)
        rim_sel = cl1.selectbox("Select Rim", df_rims['brand'] + " " + df_rims['model'])
        hub_sel = cl2.selectbox("Select Hub", df_hubs['brand'] + " " + df_hubs['model'])
        
        sel_r = df_rims[(df_rims['brand'] + " " + df_rims['model']) == rim_sel].iloc[0]
        sel_h = df_hubs[(df_hubs['brand'] + " " + df_hubs['model']) == hub_sel].iloc[0]
        
        erd, holes_init = sel_r['erd'], int(sel_r['holes'])
        l_fd, r_fd, l_os, r_os = sel_h['fd_l'], sel_h['fd_r'], sel_h['os_l'], sel_h['os_r']
        l_sp, r_sp = sel_h['sp_off_l'], sel_h['sp_off_r']

        st.divider()
        i1, i2, i3 = st.columns(3)
        holes = i1.number_input("Spoke Count", value=holes_init, step=2)
        l_cross = i2.selectbox("L-Cross", [0,1,2,3,4], index=3)
        r_cross = i3.selectbox("R-Cross", [0,1,2,3,4], index=3)
        
        is_sp = st.toggle("Straightpull Hub?", value=True)
        r_mode = st.selectbox("Rounding", ["None", "Nearest Even", "Nearest Odd"])
        
        res_l = calculate_precision_spoke(erd, l_fd, l_os, holes, l_cross, is_sp, l_sp, 2.4, r_mode)
        res_r = calculate_precision_spoke(erd, r_fd, r_os, holes, r_cross, is_sp, r_sp, 2.4, r_mode)
        
        st.metric("L Spoke Length", f"{res_l} mm")
        st.metric("R Spoke Length", f"{res_r} mm")
        
        target = st.radio("Stage to Wheel Side:", ["Front", "Rear"], horizontal=True)
        if st.button("Apply and Stage"):
            if target == "Front": st.session_state.f_l, st.session_state.f_r = res_l, res_r
            else: st.session_state.r_l, st.session_state.r_r = res_l, res_r
            st.session_state.staged_holes = holes
            st.success(f"{target} staged!")
    except Exception as e: st.error(f"Calculator Error: {e}")

# --- TAB: COMPONENT LIBRARY ---
with tabs[2]:
    st.header("📦 Library Management")
    l_type = st.selectbox("Category", ["Rims", "Hubs", "Spokes", "Nipples"])
    with st.form("lib_form_v11_3", clear_on_submit=True):
        b, m = st.text_input("Brand"), st.text_input("Model")
        w = st.number_input("Weight (g)", 0.0, step=0.1)
        if l_type == "Rims":
            e, h = st.number_input("ERD", 601.0), st.number_input("Holes", 28)
            if st.form_submit_button("Save Rim"):
                new = pd.DataFrame([{"brand":b, "model":m, "erd":e, "holes":h, "weight":w}])
                conn.update(worksheet="rims", data=pd.concat([get_worksheet_data("rims",True), new], ignore_index=True))
                st.success("Rim saved!")
        elif l_type == "Hubs":
            fl, fr, ol, orr = st.number_input("L-PCD", 40.0), st.number_input("R-PCD", 40.0), st.number_input("L-OS", 30.0), st.number_input("R-OS", 30.0)
            sl, sr = st.number_input("L-SP Off", 0.0), st.number_input("R-SP Off", 0.0)
            if st.form_submit_button("Save Hub"):
                new = pd.DataFrame([{"brand":b, "model":m, "fd_l":fl, "fd_r":fr, "os_l":ol, "os_r":orr, "sp_off_l":sl, "sp_off_r":sr, "weight":w}])
                conn.update(worksheet="hubs", data=pd.concat([get_worksheet_data("hubs",True), new], ignore_index=True))
                st.success("Hub saved!")
        elif l_type == "Spokes":
            s_type = st.radio("Type", ["J-Bend", "Straightpull"], horizontal=True)
            if st.form_submit_button("Save Spoke Model"):
                new = pd.DataFrame([{"brand":b, "model":m, "type":s_type, "weight":w}])
                conn.update(worksheet="spokes", data=pd.concat([get_worksheet_data("spokes",True), new], ignore_index=True))
                st.success(f"{b} {m} model saved!")
        else:
             if st.form_submit_button(f"Save {l_type}"):
                new = pd.DataFrame([{"brand":b, "model":m, "weight":w}])
                conn.update(worksheet=l_type.lower(), data=pd.concat([get_worksheet_data(l_type.lower(),True), new], ignore_index=True))
                st.success(f"{l_type} saved!")

# --- TAB: INVENTORY ---
with tabs[3]:
    st.header("📦 Spoke Inventory")
    try:
        # cite: 11.1
        df_inv = get_worksheet_data("spoke_inventory")
        if not df_inv.empty:
            st.dataframe(df_inv.sort_values(by=['brand', 'model', 'length']), use_container_width=True)
        else:
            st.info("Inventory currently empty. Add items via your Google Sheet 'spoke_inventory' tab.")
    except Exception as e: st.info(f"Inventory loading: {e}")

# --- TAB: REGISTER BUILD ---
with tabs[4]:
    st.header("📝 Register Build")
    try:
        df_rims, df_hubs = get_worksheet_data("rims"), get_worksheet_data("hubs")
        df_spokes = get_worksheet_data("spokes")
        
        hub_opts = ["None"] + list(df_hubs['brand'] + " " + df_hubs['model'])
        rim_opts = ["None"] + list(df_rims['brand'] + " " + df_rims['model'])
        sp_opts = ["None"] + list(df_spokes['brand'] + " " + df_spokes['model'])
        
        with st.form("build_form_v11_3"):
            cust = st.text_input("Customer Name", value=st.session_state.edit_customer if st.session_state.edit_customer else "")
            stat = st.selectbox("Status", ["Order received", "Awaiting parts", "Build in progress", "Complete"])
            
            c_r1, c_r2 = st.columns(2)
            f_rim = c_r1.selectbox("Front Rim", rim_opts)
            r_rim = c_r2.selectbox("Rear Rim", rim_opts)
            
            c_h1, c_h2 = st.columns(2)
            f_hub = c_h1.selectbox("Front Hub", hub_opts)
            r_hub = c_h2.selectbox("Rear Hub", hub_opts)
            
            sp = st.selectbox("Spoke Model", sp_opts)
            qty = st.number_input("Total Spokes Used", value=int(st.session_state.staged_holes * 2), step=2)
            
            st.divider()
            st.caption("Staged Lengths (from Calculator)")
            sc1, sc2, sc3, sc4 = st.columns(4)
            vfl = sc1.number_input("F-L", value=st.session_state.f_l)
            vfr = sc2.number_input("F-R", value=st.session_state.f_r)
            vrl = sc3.number_input("R-L", value=st.session_state.r_l)
            vrr = sc4.number_input("R-R", value=st.session_state.r_r)
            
            if st.form_submit_button("💾 Save Build"):
                entry = {
                    "date": datetime.now().strftime("%Y-%m-%d"), 
                    "customer": cust, 
                    "status": stat, 
                    "f_hub": f_hub, "r_hub": r_hub, 
                    "f_rim": f_rim, "r_rim": r_rim, 
                    "spoke": sp, "spoke_count": qty, 
                    "f_l": vfl, "f_r": vfr, "r_l": vrl, "r_r": vrr
                }
                conn.update(worksheet="builds", data=pd.concat([get_worksheet_data("builds"), pd.DataFrame([entry])], ignore_index=True))
                st.cache_data.clear()
                st.success("Registered!")
                st.rerun()
    except Exception as e: st.error(f"Tab Error: {e}")

# --- TAB: SPEC SHEET ---
with tabs[5]:
    st.header("📄 Portfolio Spec Sheet")
    try:
        df_builds = get_worksheet_data("builds")
        if not df_builds.empty:
            target = st.selectbox("Select Project", df_builds['customer'])
            d = df_builds[df_builds['customer'] == target].iloc[0]
            
            st.markdown(f"### Build Portfolio: **{target}**")
            st.divider()
            
            c1, c2 = st.columns(2)
            with c1:
                st.write(f"**Front:** {d.get('f_rim', 'N/A')} / {d.get('f_hub', 'N/A')}")
                st.info(f"Lengths: L {d.get('f_l', 0)} / R {d.get('f_r', 0)} mm")
            with c2:
                st.write(f"**Rear:** {d.get('r_rim', 'N/A')} / {d.get('r_hub', 'N/A')}")
                st.success(f"Lengths: L {d.get('r_l', 0)} / R {d.get('r_r', 0)} mm")
            
            st.divider()
            st.write(f"**Spoke Model:** {d.get('spoke', 'N/A')} (x{int(d.get('spoke_count', 0))})")
    except Exception as e: st.error(f"Spec Sheet Error: {e}")
