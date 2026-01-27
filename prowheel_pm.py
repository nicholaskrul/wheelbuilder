import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import math
from datetime import datetime

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="ProWheel Lab v10.1", layout="wide", page_icon="🚲")

# --- 2. GOOGLE SHEETS CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_worksheet_data(sheet_name, force_refresh=False):
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
st.title("🚲 ProWheel Lab v10.1: Contextual Build Suite")
st.markdown("---")

tab_list = ["📊 Dashboard", "🧮 Precision Calc", "📦 Library", "➕ Register Build", "📄 Spec Sheet"]
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
    except Exception as e: st.error(f"Sync error: {e}")

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
        l_fd, r_fd, l_os, r_os, l_sp, r_sp = sel_h['fd_l'], sel_h['fd_r'], sel_h['os_l'], sel_h['os_r'], sel_h['sp_off_l'], sel_h['sp_off_r']

        st.divider()
        i1, i2, i3 = st.columns(3)
        holes = i1.number_input("Spoke Count", value=holes_init, step=2)
        l_cross, r_cross = i2.selectbox("L-Cross", [0,1,2,3,4], index=3), i3.selectbox("R-Cross", [0,1,2,3,4], index=3)
        is_sp, r_mode = st.toggle("Straightpull Hub?", value=True), st.selectbox("Rounding", ["None", "Nearest Even", "Nearest Odd"])
        
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

# --- TAB: REGISTER BUILD ---
with tabs[3]:
    st.header("📝 Register / Update Build")
    try:
        df_rims, df_hubs = get_worksheet_data("rims"), get_worksheet_data("hubs")
        df_spokes, df_nipples = get_worksheet_data("spokes"), get_worksheet_data("nipples")
        
        hub_options = ["None"] + list(df_hubs['brand'] + " " + df_hubs['model'])
        rim_options = ["None"] + list(df_rims['brand'] + " " + df_rims['model'])
        
        with st.form("build_form_v10.1"):
            cust = st.text_input("Customer Name", value=st.session_state.edit_customer if st.session_state.edit_customer else "")
            stat = st.selectbox("Status", ["Order received", "Awaiting parts", "Parts received", "Build in progress", "Complete"])
            
            c_rim1, c_rim2 = st.columns(2)
            f_rim = c_rim1.selectbox("Front Rim", rim_options)
            r_rim = c_rim2.selectbox("Rear Rim", rim_options)
            
            c_hub1, c_hub2 = st.columns(2)
            f_hub = c_hub1.selectbox("Front Hub", hub_options)
            r_hub = c_hub2.selectbox("Rear Hub", hub_options)
            
            sp, ni = st.selectbox("Spoke", ["None"] + list(df_spokes['brand'] + " " + df_spokes['model'])), st.selectbox("Nipple", ["None"] + list(df_nipples['brand'] + " " + df_nipples['model']))
            
            # Smart Default: If one hub is None, default to single wheel spoke count
            default_qty = int(st.session_state.staged_holes) if (f_hub == "None" or r_hub == "None") else int(st.session_state.staged_holes * 2)
            total_qty = st.number_input("Total Spokes (Set Total)", value=default_qty, step=2)
            
            # --- CONTEXTUAL SPOKE LENGTHS ---
            sc1, sc2, sc3, sc4 = st.columns(4)
            vfl = sc1.number_input("F-L", value=st.session_state.f_l) if f_hub != "None" else 0.0
            vfr = sc2.number_input("F-R", value=st.session_state.f_r) if f_hub != "None" else 0.0
            vrl = sc3.number_input("R-L", value=st.session_state.r_l) if r_hub != "None" else 0.0
            vrr = sc4.number_input("R-R", value=st.session_state.r_r) if r_hub != "None" else 0.0
            
            inv, notes = st.text_input("Invoice URL"), st.text_area("Notes")
            
            if st.form_submit_button("💾 Sync Build"):
                entry = {"date":datetime.now().strftime("%Y-%m-%d"), "customer":cust, "status":stat, "f_hub":f_hub, "r_hub":r_hub, "f_rim":f_rim, "r_rim":r_rim, "spoke":sp, "nipple":ni, "spoke_count":total_qty, "f_l":vfl, "f_r":vfr, "r_l":vrl, "r_r":vrr, "invoice_url":inv, "notes":notes}
                conn.update(worksheet="builds", data=pd.concat([get_worksheet_data("builds"), pd.DataFrame([entry])], ignore_index=True))
                st.session_state.edit_customer = None
                st.session_state.active_tab = "📊 Dashboard"
                st.success("Synced!")
                st.rerun()
    except Exception as e: st.warning(f"Registration Error: {e}")

# --- TAB: SPEC SHEET ---
with tabs[4]:
    st.header("📄 Portfolio Spec Sheet")
    df_builds = get_worksheet_data("builds")
    if not df_builds.empty:
        target = st.selectbox("Select Project", df_builds['customer'])
        d = df_builds[df_builds['customer'] == target].iloc[0]
        
        def get_safe_w(sheet_name, part_name):
            if part_name == "None": return 0.0
            try:
                df = get_worksheet_data(sheet_name)
                match = df[(df['brand'] + " " + df['model']) == part_name]
                return float(pd.to_numeric(match['weight'].values[0], errors='coerce')) if not match.empty else 0.0
            except: return 0.0

        w_f_rim, w_r_rim = get_safe_w("rims", d.get('f_rim', 'None')), get_safe_w("rims", d.get('r_rim', 'None'))
        w_fh, w_rh = get_safe_w("hubs", d.get('f_hub', 'None')), get_safe_w("hubs", d.get('r_hub', 'None'))
        w_sp, w_ni = get_safe_w("spokes", d.get('spoke', 'None')), get_safe_w("nipples", d.get('nipple', 'None'))
        qty = float(pd.to_numeric(d.get('spoke_count', 0), errors='coerce'))
        
        total_w = w_f_rim + w_r_rim + w_fh + w_rh + (w_sp * qty) + (w_ni * qty)

        st.markdown(f"### Build for: **{target}**")
        st.divider()
        wc1, wc2, wc3 = st.columns(3)
        if d.get('f_rim', 'None') != 'None': wc1.write(f"**Front Rim:** {d['f_rim']} ({w_f_rim}g)")
        if d.get('r_rim', 'None') != 'None': wc1.write(f"**Rear Rim:** {d['r_rim']} ({w_r_rim}g)")
        if d.get('f_hub', 'None') != 'None': wc1.write(f"**Front Hub:** {d['f_hub']} ({w_fh}g)")
        if d.get('r_hub', 'None') != 'None': wc2.write(f"**Rear Hub:** {d['r_hub']} ({w_rh}g)")
        if d.get('spoke', 'None') != 'None': wc2.write(f"**Spokes (x{int(qty)}):** {d['spoke']} ({w_sp}g ea)")
        if d.get('nipple', 'None') != 'None': wc3.write(f"**Nipples (x{int(qty)}):** {d['nipple']} ({w_ni}g ea)")
        
        wc3.metric("Total Weight", f"{round(total_w, 1)} g")
        st.divider()
        # Only show relevant lengths
        if d['f_l'] > 0: st.info(f"**Front:** L {d['f_l']} / R {d['f_r']} mm")
        if d['r_l'] > 0: st.success(f"**Rear:** L {d['r_l']} / R {d['r_r']} mm")
