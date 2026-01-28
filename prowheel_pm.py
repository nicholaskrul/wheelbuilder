import streamlit as st
import pandas as pd
import math
from datetime import datetime
from pyairtable import Api

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Wheelbuilder Lab v12.1", layout="wide", page_icon="🚲")

# --- 2. AIRTABLE CONNECTION ---
# Accessing secrets from Streamlit Cloud / .streamlit/secrets.toml
try:
    AIRTABLE_API_KEY = st.secrets["airtable"]["api_key"]
    AIRTABLE_BASE_ID = st.secrets["airtable"]["base_id"]
    api = Api(AIRTABLE_API_KEY)
    base = api.base(AIRTABLE_BASE_ID)
except Exception as e:
    st.error("Missing Airtable Secrets. Ensure you've added [airtable] api_key and base_id to Streamlit Cloud Settings.")
    st.stop()

@st.cache_data(ttl=600)  # 10-minute cache to respect Airtable API limits
def get_table(table_name):
    """Fetches all records from an Airtable table and converts to a DataFrame."""
    try:
        table = base.table(table_name)
        records = table.all()
        # Flatten Airtable structure: Extract the 'fields' and include the Airtable 'id' for updates
        data = [ {**rec['fields'], 'id': rec['id']} for rec in records ]
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error fetching table '{table_name}': {e}")
        return pd.DataFrame()

# --- 3. PRECISION CALCULATION LOGIC (v11.5 Engine) ---
def calculate_precision_spoke(erd, fd, os, holes, crosses, is_sp, sp_offset, hole_diam=2.4, round_mode="None"):
    if 0 in [erd, fd, holes]: return 0.0
    # Ensure all inputs are float for math operations
    r_rim, r_hub = float(erd) / 2, float(fd) / 2
    alpha_rad = math.radians((float(crosses) * 720.0) / float(holes))
    
    if not is_sp:
        # Standard J-Bend Geometry
        l_sq = (r_rim**2) + (r_hub**2) + (float(os)**2) - (2 * r_rim * r_hub * math.cos(alpha_rad))
        length = math.sqrt(max(0, l_sq)) - (float(hole_diam) / 2)
    else:
        # Refined SP Logic v11.5
        base_l_sq = (r_rim**2) + (r_hub**2) - (2 * r_rim * r_hub * math.cos(alpha_rad))
        length = math.sqrt(max(0, base_l_sq + float(os)**2)) + float(sp_offset)
    
    if round_mode == "Nearest Even": return float(round(length / 2) * 2)
    elif round_mode == "Nearest Odd": return float(round((length - 1) / 2) * 2 + 1)
    return round(length, 1)

# --- 4. SESSION STATE & NAVIGATION ---
if 'active_tab' not in st.session_state: st.session_state.active_tab = "📊 Dashboard"
for key in ['f_l', 'f_r', 'r_l', 'r_r']:
    if key not in st.session_state: st.session_state[key] = 0.0

# --- 5. MAIN USER INTERFACE ---
st.title("🚲 Wheelbuilder Lab")
st.caption("Airtable Relational Engine | v12.1 Stable")
st.markdown("---")

tab_list = ["📊 Dashboard", "🧮 Precision Calc", "📦 Library", "📦 Inventory", "➕ Register Build", "📄 Spec Sheet"]
tabs = st.tabs(tab_list)

# --- TAB: DASHBOARD ---
with tabs[0]:
    st.subheader("🏁 Workshop Pipeline")
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    
    df_builds = get_table("builds")
    if not df_builds.empty:
        # Ensure date sorting if column exists
        if 'date' in df_builds.columns:
            df_builds = df_builds.sort_values('date', ascending=False)
        
        for _, row in df_builds.iterrows():
            with st.container():
                c1, c2, c3 = st.columns([2, 2, 1])
                c1.write(f"**{row.get('customer', 'Unknown')}**")
                c2.write(f"Status: `{row.get('status', 'N/A')}`")
                c3.write(f"📅 {row.get('date', 'N/A')}")
                st.divider()

# --- TAB: PRECISION CALC ---
with tabs[1]:
    st.header("🧮 Spoke Calculator")
    df_rims = get_table("rims")
    df_hubs = get_table("hubs")
    
    if not df_rims.empty and not df_hubs.empty:
        col1, col2 = st.columns(2)
        rim_sel = col1.selectbox("Select Rim", df_rims['brand'] + " " + df_rims['model'])
        hub_sel = col2.selectbox("Select Hub", df_hubs['brand'] + " " + df_hubs['model'])
        
        r_dat = df_rims[df_rims['brand'] + " " + df_rims['model'] == rim_sel].iloc[0]
        h_dat = df_hubs[df_hubs['brand'] + " " + df_hubs['model'] == hub_sel].iloc[0]
        
        st.divider()
        i1, i2, i3 = st.columns(3)
        holes = i1.number_input("Spoke Count", value=int(r_dat['holes']), step=2)
        l_cross = i2.selectbox("L-Cross", [0,1,2,3,4], index=3)
        r_cross = i3.selectbox("R-Cross", [0,1,2,3,4], index=3)
        
        is_sp = st.toggle("Straightpull Hub?", value=True)
        r_mode = st.selectbox("Rounding", ["None", "Nearest Even", "Nearest Odd"])
        
        res_l = calculate_precision_spoke(r_dat['erd'], h_dat['fd_l'], h_dat['os_l'], holes, l_cross, is_sp, h_dat.get('sp_off_l', 0), 2.4, r_mode)
        res_r = calculate_precision_spoke(r_dat['erd'], h_dat['fd_r'], h_dat['os_r'], holes, r_cross, is_sp, h_dat.get('sp_off_r', 0), 2.4, r_mode)
        
        st.metric("L Spoke Length", f"{res_l} mm")
        st.metric("R Spoke Length", f"{res_r} mm")
        
        if st.button("Apply and Stage"):
            st.session_state.f_l, st.session_state.f_r = res_l, res_r
            st.success("Lengths staged for build registration!")

# --- TAB: LIBRARY ---
with tabs[2]:
    st.header("📦 Component Library")
    lib_type = st.radio("View Table:", ["rims", "hubs", "spokes", "nipples"], horizontal=True)
    st.dataframe(get_table(lib_type), use_container_width=True)

# --- TAB: INVENTORY ---
with tabs[3]:
    st.header("📦 Spoke Inventory")
    df_inv = get_table("spoke_inventory")
    if not df_inv.empty:
        st.dataframe(df_inv[['brand', 'model', 'length', 'stock']], use_container_width=True)
        
        with st.form("inventory_update_v12"):
            st.subheader("📝 Update Stock Quantity")
            target = st.selectbox("Select Spoke", df_inv['id'], 
                                 format_func=lambda x: f"{df_inv[df_inv['id']==x]['brand'].values[0]} {df_inv[df_inv['id']==x]['model'].values[0]} ({df_inv[df_inv['id']==x]['length'].values[0]}mm)")
            new_qty = st.number_input("New Quantity", step=1)
            if st.form_submit_button("💾 Save to Airtable"):
                base.table("spoke_inventory").update(target, {"stock": int(new_qty)})
                st.cache_data.clear()
                st.success("Inventory Updated!")
                st.rerun()

# --- TAB: REGISTER BUILD ---
with tabs[4]:
    st.header("📝 Register Build")
    df_rims = get_table("rims")
    df_hubs = get_table("hubs")
    df_spk = get_table("spokes")
    
    with st.form("new_build_form"):
        cust = st.text_input("Customer Name")
        stat = st.selectbox("Status", ["Order received", "Parts received", "Build in progress", "Complete"])
        
        c1, c2 = st.columns(2)
        f_r = c1.selectbox("Front Rim", df_rims['brand'] + " " + df_rims['model'])
        r_r = c2.selectbox("Rear Rim", df_rims['brand'] + " " + df_rims['model'])
        
        c3, c4 = st.columns(2)
        f_h = c3.selectbox("Front Hub", df_hubs['brand'] + " " + df_hubs['model'])
        r_h = c4.selectbox("Rear Hub", df_hubs['brand'] + " " + df_hubs['model'])
        
        spk_mod = st.selectbox("Spoke Model", df_spk['brand'] + " " + df_spk['model'])
        inv_url = st.text_input("Invoice URL (Airtable/Zoho)")
        
        st.divider()
        st.caption("Length Verification (Edit if needed)")
        sc1, sc2, sc3, sc4 = st.columns(4)
        vfl = sc1.number_input("F-L", value=st.session_state.f_l)
        vfr = sc2.number_input("F-R", value=st.session_state.f_r)
        vrl = sc3.number_input("R-L", value=st.session_state.r_l)
        vrr = sc4.number_input("R-R", value=st.session_state.r_r)
        
        if st.form_submit_button("🚀 Finalize Build"):
            new_record = {
                "customer": cust, "status": stat, "invoice_url": inv_url,
                "f_rim": f_r, "r_rim": r_r, "f_hub": f_h, "r_hub": r_h,
                "spoke": spk_mod, "f_l": vfl, "f_r": vfr, "r_l": vrl, "r_r": vrr,
                "date": datetime.now().strftime("%Y-%m-%d")
            }
            base.table("builds").create(new_record)
            st.cache_data.clear()
            st.success("Build registered in Airtable!")

# --- TAB: SPEC SHEET ---
with tabs[5]:
    st.header("📄 Portfolio Spec Sheet")
    df_b = get_table("builds")
    if not df_b.empty:
        sel_cust = st.selectbox("Select Project", df_b['customer'])
        b = df_b[df_b['customer'] == sel_cust].iloc[0]
        
        st.markdown(f"### Build Portfolio: **{sel_cust}**")
        st.divider()
        
        col_f, col_r = st.columns(2)
        with col_f:
            st.subheader("Front Wheel")
            st.write(f"**Rim:** {b.get('f_rim')}")
            st.write(f"**Hub:** {b.get('f_hub')}")
            st.info(f"Lengths: L {b.get('f_l')} / R {b.get('f_r')} mm")
        
        with col_r:
            st.subheader("Rear Wheel")
            st.write(f"**Rim:** {b.get('r_rim')}")
            st.write(f"**Hub:** {b.get('r_hub')}")
            st.success(f"Lengths: L {b.get('r_l')} / R {b.get('r_r')} mm")
            
        st.divider()
        if b.get('invoice_url'):
            st.link_button("📄 Download invoice", b['invoice_url'])
