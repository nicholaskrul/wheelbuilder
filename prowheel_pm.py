import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import math
from datetime import datetime

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="ProWheel Lab v10.9", layout="wide", page_icon="🚲")

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

# --- TAB: SPEC SHEET (FIXED WEIGHT RETRIEVAL) ---
with tabs[5]:
    st.header("📄 Portfolio Spec Sheet")
    df_builds = get_worksheet_data("builds")
    if not df_builds.empty:
        target = st.selectbox("Select Project", df_builds['customer'])
        d = df_builds[df_builds['customer'] == target].iloc[0]
        
        def get_safe_w(sheet_name, part_name):
            if not part_name or part_name == "None" or str(part_name) == "nan": return 0.0
            try:
                df = get_worksheet_data(sheet_name)
                # Clean parenthetical data (e.g. from spoke lengths)
                clean = part_name.split(' (')[0] if '(' in str(part_name) else str(part_name)
                match = df[(df['brand'] + " " + df['model']) == clean]
                if not match.empty:
                    val = pd.to_numeric(match['weight'].values[0], errors='coerce')
                    return float(val) if not pd.isna(val) else 0.0
                return 0.0
            except: return 0.0

        # --- LEGACY RIM FALLBACK ---
        # If f_rim/r_rim are missing (None), check the old 'rim' column
        raw_f_rim = d.get('f_rim', d.get('rim', 'None'))
        raw_r_rim = d.get('r_rim', d.get('rim', 'None'))
        
        w_fr, w_rr = get_safe_w("rims", raw_f_rim), get_safe_w("rims", raw_r_rim)
        w_fh, w_rh = get_safe_w("hubs", d.get('f_hub', 'None')), get_safe_w("hubs", d.get('r_hub', 'None'))
        w_sp, w_ni = get_safe_w("spokes", d.get('spoke', 'None')), get_safe_w("nipples", d.get('nipple', 'None'))
        
        # --- ROBUST QTY CALCULATION ---
        # Prevents 'nan g' by forcing a numeric fallback
        qty_val = pd.to_numeric(d.get('spoke_count', 0), errors='coerce')
        qty = float(qty_val) if not pd.isna(qty_val) else 0.0
        
        total_w = w_fr + w_rr + w_fh + w_rh + (w_sp * qty) + (w_ni * qty)

        st.markdown(f"### Build Portfolio: **{target}**")
        st.divider()
        wc1, wc2, wc3 = st.columns(3)
        
        # Display Logic: Combine into Rim (x2) if they match and aren't None
        if raw_f_rim == raw_r_rim and raw_f_rim != "None":
            wc1.write(f"**Rim (x2):** {raw_f_rim} ({w_fr}g ea)")
        else:
            if raw_f_rim != "None": wc1.write(f"**Front Rim:** {raw_f_rim} ({w_fr}g)")
            if raw_r_rim != "None": wc1.write(f"**Rear Rim:** {raw_r_rim} ({w_rr}g)")

        if d.get('f_hub', 'None') != 'None': wc1.write(f"**Front Hub:** {d['f_hub']} ({w_fh}g)")
        if d.get('r_hub', 'None') != 'None': wc2.write(f"**Rear Hub:** {d['r_hub']} ({w_rh}g)")
        if d.get('spoke', 'None') != 'None': wc2.write(f"**Spokes (x{int(qty)}):** {d['spoke']} ({w_sp}g ea)")
        if d.get('nipple', 'None') != 'None': wc3.write(f"**Nipples (x{int(qty)}):** {d['nipple']} ({w_ni}g ea)")
        
        if not pd.isna(total_w):
            wc3.metric("Total Weight", f"{round(total_w, 1)} g")
        else:
            wc3.metric("Total Weight", "Data Incomplete")
        
        if d.get('invoice_url') and str(d['invoice_url']) != "nan":
            st.link_button("📄 Download invoice", d['invoice_url'])
        
        st.divider()
        if d.get('f_l', 0) > 0: st.info(f"**Front lengths:** L {d['f_l']} / R {d['f_r']} mm")
        if d.get('r_l', 0) > 0: st.success(f"**Rear lengths:** L {d['r_l']} / R {d['r_r']} mm")
