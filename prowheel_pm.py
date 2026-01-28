import streamlit as st
import pandas as pd
import math
from datetime import datetime
from pyairtable import Api

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Wheelbuilder Lab v12.5", layout="wide", page_icon="🚲")

# --- 2. AIRTABLE CONNECTION ---
# Accessing secrets from Streamlit Cloud / .streamlit/secrets.toml
try:
    AIRTABLE_API_KEY = st.secrets["airtable"]["api_key"]
    AIRTABLE_BASE_ID = st.secrets["airtable"]["base_id"]
    api = Api(AIRTABLE_API_KEY)
    base = api.base(AIRTABLE_BASE_ID)
except Exception as e:
    st.error("❌ Secrets Error: Please check your Streamlit Cloud Settings for [airtable] api_key and base_id.")
    st.stop()

@st.cache_data(ttl=600)
def get_table(table_name):
    """Fetches records and cleans missing data to prevent concatenation crashes."""
    try:
        table = base.table(table_name)
        records = table.all()
        if not records:
            return pd.DataFrame()
        
        # Flatten structure and include Airtable ID for updates
        data = [ {**rec['fields'], 'id': rec['id']} for rec in records ]
        df = pd.DataFrame(data)
        
        # Drop rows that are completely empty (helps with accidental '+' clicks in Airtable)
        df = df.dropna(how='all', subset=[c for c in df.columns if c != 'id'])
        
        # Shield against 'None' values by filling them with empty strings
        return df.fillna('')
    except Exception as e:
        st.warning(f"⚠️ Connection issue with table '{table_name}'. Error: {e}")
        return pd.DataFrame()

# --- 3. PRECISION CALCULATION ENGINE ---
def calculate_precision_spoke(erd, fd, os, holes, crosses, is_sp, sp_offset, round_mode="None"):
    """Refined Engine for J-Bend and Straightpull pathing."""
    if not erd or not fd or not holes: return 0.0
    r_rim, r_hub = float(erd) / 2, float(fd) / 2
    alpha_rad = math.radians((float(crosses) * 720.0) / float(holes))
    
    if not is_sp:
        # Standard J-Bend Geometry
        l_sq = (r_rim**2) + (r_hub**2) + (float(os)**2) - (2 * r_rim * r_hub * math.cos(alpha_rad))
        length = math.sqrt(max(0, l_sq)) - 1.2 # Standard hole diameter correction
    else:
        # Refined Straightpull Logic
        base_l_sq = (r_rim**2) + (r_hub**2) - (2 * r_rim * r_hub * math.cos(alpha_rad))
        length = math.sqrt(max(0, base_l_sq + float(os)**2)) + float(sp_offset)
    
    if round_mode == "Nearest Even": return float(round(length / 2) * 2)
    elif round_mode == "Nearest Odd": return float(round((length - 1) / 2) * 2 + 1)
    return round(length, 1)

# --- 4. SESSION STATE ---
if 'staged' not in st.session_state:
    st.session_state.staged = {'f_l': 0.0, 'f_r': 0.0, 'r_l': 0.0, 'r_r': 0.0}

# --- 5. MAIN USER INTERFACE ---
st.title("🚲 Wheelbuilder Lab")
st.caption("v12.5 | Airtable Relational Backend (Stable)")
st.markdown("---")

tabs = st.tabs(["📊 Dashboard", "🧮 Precision Calc", "📦 Library", "📦 Inventory", "➕ Register Build", "📄 Spec Sheet"])

# --- TAB 1: DASHBOARD ---
with tabs[0]:
    st.subheader("🏁 Workshop Pipeline")
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    
    df_builds = get_table("builds")
    if not df_builds.empty:
        # Sorting handling
        if 'date' in df_builds.columns:
            df_builds = df_builds.sort_values('date', ascending=False)
        
        for _, row in df_builds.iterrows():
            with st.expander(f"🛠️ {row.get('customer', 'Unknown')} - {row.get('status', 'N/A')}"):
                c1, c2 = st.columns(2)
                c1.write(f"**Date:** {row.get('date', 'N/A')}")
                c1.write(f"**Spoke Type:** {row.get('spoke', 'N/A')}")
                c2.write(f"**Front Specs:** {row.get('f_l')} / {row.get('f_r')} mm")
                c2.write(f"**Rear Specs:** {row.get('r_l')} / {row.get('r_r')} mm")
                if row.get('invoice_url'):
                    st.link_button("📄 View Invoice", row['invoice_url'])
    else:
        st.info("No builds found. Connect your Airtable base to begin.")

# --- TAB 2: CALCULATOR ---
with tabs[1]:
    st.header("🧮 Spoke Calculator")
    df_rims, df_hubs = get_table("rims"), get_table("hubs")
    
    if not df_rims.empty and not df_hubs.empty:
        col1, col2 = st.columns(2)
        
        # Safe concatenation ensures no crashes on empty rows in the dropdown
        rim_options = df_rims['brand'].astype(str) + " " + df_rims['model'].astype(str)
        hub_options = df_hubs['brand'].astype(str) + " " + df_hubs['model'].astype(str)
        
        rim_sel = col1.selectbox("Select Rim", rim_options)
        hub_sel = col2.selectbox("Select Hub", hub_options)
        
        r_dat = df_rims[rim_options == rim_sel].iloc[0]
        h_dat = df_hubs[hub_options == hub_sel].iloc[0]
        
        st.divider()
        i1, i2, i3 = st.columns(3)
        holes = i1.number_input("Spoke Count", value=int(r_dat.get('holes', 28)) if r_dat.get('holes') else 28, step=2)
        l_cross = i2.selectbox("L-Cross", [0,1,2,3,4], index=3)
        r_cross = i3.selectbox("R-Cross", [0,1,2,3,4], index=3)
        
        is_sp = st.toggle("Straightpull Hub?", value=True)
        r_mode = st.selectbox("Rounding", ["None", "Nearest Even", "Nearest Odd"])
        
        res_l = calculate_precision_spoke(r_dat.get('erd', 0), h_dat.get('fd_l', 0), h_dat.get('os_l', 0), holes, l_cross, is_sp, h_dat.get('sp_off_l', 0), r_mode)
        res_r = calculate_precision_spoke(r_dat.get('erd', 0), h_dat.get('fd_r', 0), h_dat.get('os_r', 0), holes, r_cross, is_sp, h_dat.get('sp_off_r', 0), r_mode)
        
        st.metric("Left Spoke Length", f"{res_l} mm")
        st.metric("Right Spoke Length", f"{res_r} mm")
        
        side = st.radio("Stage result to:", ["Front", "Rear"], horizontal=True)
        if st.button("Apply and Stage"):
            if side == "Front":
                st.session_state.staged['f_l'], st.session_state.staged['f_r'] = res_l, res_r
            else:
                st.session_state.staged['r_l'], st.session_state.staged['r_r'] = res_l, res_r
            st.success(f"{side} wheel lengths staged!")

# --- TAB 3: LIBRARY ---
with tabs[2]:
    st.header("📦 Component Library")
    lib_choice = st.radio("View Table:", ["rims", "hubs", "spokes", "nipples"], horizontal=True)
    st.dataframe(get_table(lib_choice), use_container_width=True)

# --- TAB 4: INVENTORY ---
with tabs[3]:
    st.header("📦 Spoke Inventory")
    df_inv = get_table("spoke_inventory")
    if not df_inv.empty:
        st.dataframe(df_inv[['brand', 'model', 'length', 'stock']], use_container_width=True)
        
        with st.form("inventory_update"):
            st.subheader("📝 Update Stock Quantity")
            target = st.selectbox("Select Spoke", df_inv['id'], 
                                 format_func=lambda x: f"{df_inv[df_inv['id']==x]['brand'].values[0]} {df_inv[df_inv['id']==x]['model'].values[0]} ({df_inv[df_inv['id']==x]['length'].values[0]}mm)")
            new_qty = st.number_input("New Quantity", step=1)
            if st.form_submit_button("💾 Save to Airtable"):
                base.table("spoke_inventory").update(target, {"stock": int(new_qty)})
                st.cache_data.clear()
                st.success("Inventory updated!")
                st.rerun()

# --- TAB 5: REGISTER BUILD ---
with tabs[4]:
    st.header("📝 Register New Build")
    df_rims, df_hubs, df_spk = get_table("rims"), get_table("hubs"), get_table("spokes")
    
    if not df_rims.empty:
        with st.form("new_build_registration"):
            cust = st.text_input("Customer Name")
            rim_sel = st.selectbox("Rim Used", df_rims['brand'].astype(str) + " " + df_rims['model'].astype(str))
            hub_sel = st.selectbox("Hub Used", df_hubs['brand'].astype(str) + " " + df_hubs['model'].astype(str))
            spk_sel = st.selectbox("Spoke Model", df_spk['brand'].astype(str) + " " + df_spk['model'].astype(str))
            
            st.divider()
            st.caption("Review staged lengths (from Calculator)")
            sc1, sc2, sc3, sc4 = st.columns(4)
            vfl = sc1.number_input("F-L", value=st.session_state.staged['f_l'])
            vfr = sc2.number_input("F-R", value=st.session_state.staged['f_r'])
            vrl = sc3.number_input("R-L", value=st.session_state.staged['r_l'])
            vrr = sc4.number_input("R-R", value=st.session_state.staged['r_r'])
            
            inv_url = st.text_input("Invoice Link")
            stat = st.selectbox("Status", ["Parts received", "Build in progress", "Complete"])
            
            if st.form_submit_button("🚀 Finalize & Save Build"):
                base.table("builds").create({
                    "customer": cust, "f_rim": rim_sel, "f_hub": hub_sel, "spoke": spk_sel,
                    "f_l": vfl, "f_r": vfr, "r_l": vrl, "r_r": vrr,
                    "date": datetime.now().strftime("%Y-%m-%d"), "status": stat, "invoice_url": inv_url
                })
                st.cache_data.clear()
                st.success("Build registered successfully!")
                st.rerun()

# --- TAB 6: SPEC SHEET ---
with tabs[5]:
    st.header("📄 Build Spec Sheet")
    df_spec = get_table("builds")
    if not df_spec.empty:
        selected_project = st.selectbox("Select Build", df_spec['customer'])
        b = df_spec[df_spec['customer'] == selected_project].iloc[0]
        
        st.subheader(f"Portfolio Record: {selected_project}")
        st.write(f"**Date Built:** {b.get('date')}")
        st.divider()
        col1, col2 = st.columns(2)
        col1.write("### Front Wheel")
        col1.write(f"**L/R Lengths:** {b.get('f_l')} / {b.get('f_r')} mm")
        col2.write("### Rear Wheel")
        col2.write(f"**L/R Lengths:** {b.get('r_l')} / {b.get('r_r')} mm")
