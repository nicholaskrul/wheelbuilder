import streamlit as st
import pandas as pd
import math
from datetime import datetime
from pyairtable import Api

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Wheelbuilder Lab v12.6", layout="wide", page_icon="🚲")

# --- 2. AIRTABLE CONNECTION ---
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
    """Fetches records and cleans data to prevent crashes on empty cells."""
    try:
        table = base.table(table_name)
        records = table.all()
        if not records: return pd.DataFrame()
        
        data = [ {**rec['fields'], 'id': rec['id']} for rec in records ]
        df = pd.DataFrame(data)
        
        # Mandatory columns for labeling
        for col in ['brand', 'model']:
            if col in df.columns:
                df[col] = df[col].fillna('').astype(str).str.strip()
        
        # Only keep rows that have at least some component data
        if 'brand' in df.columns and 'model' in df.columns:
            df = df[~((df['brand'] == '') & (df['model'] == ''))]
            
        return df
    except Exception as e:
        st.warning(f"⚠️ Table '{table_name}' issue: {e}")
        return pd.DataFrame()

# --- 3. PRECISION CALCULATION ENGINE ---
def calculate_precision_spoke(erd, fd, os, holes, crosses, is_sp, sp_offset, round_mode="None"):
    if not erd or not fd or not holes: return 0.0
    r_rim, r_hub = float(erd) / 2, float(fd) / 2
    alpha_rad = math.radians((float(crosses) * 720.0) / float(holes))
    
    if not is_sp:
        l_sq = (r_rim**2) + (r_hub**2) + (float(os)**2) - (2 * r_rim * r_hub * math.cos(alpha_rad))
        length = math.sqrt(max(0, l_sq)) - 1.2
    else:
        # Refined SP Logic v11.5
        base_l_sq = (r_rim**2) + (r_hub**2) - (2 * r_rim * r_hub * math.cos(alpha_rad))
        length = math.sqrt(max(0, base_l_sq + float(os)**2)) + float(sp_offset)
    
    if round_mode == "Nearest Even": return float(round(length / 2) * 2)
    elif round_mode == "Nearest Odd": return float(round((length - 1) / 2) * 2 + 1)
    return round(length, 1)

# --- 4. SESSION STATE ---
if 'staged' not in st.session_state:
    st.session_state.staged = {'f_l': 0.0, 'f_r': 0.0, 'r_l': 0.0, 'r_r': 0.0}

# --- 5. MAIN UI ---
st.title("🚲 Wheelbuilder Lab")
st.caption("v12.6 | Bulletproof Airtable Engine")
st.markdown("---")

tabs = st.tabs(["📊 Dashboard", "🧮 Precision Calc", "📦 Library", "📦 Inventory", "➕ Register Build", "📄 Spec Sheet"])

# --- DASHBOARD ---
with tabs[0]:
    st.subheader("🏁 Workshop Pipeline")
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    df_builds = get_table("builds")
    if not df_builds.empty:
        for _, row in df_builds.iterrows():
            with st.expander(f"🛠️ {row.get('customer', 'Build')} - {row.get('status', 'N/A')}"):
                st.write(f"Date: {row.get('date', 'N/A')}")
                st.write(f"Front: {row.get('f_l', 0)} / {row.get('f_r', 0)} mm")
                st.write(f"Rear: {row.get('r_l', 0)} / {row.get('r_r', 0)} mm")

# --- CALCULATOR ---
with tabs[1]:
    st.header("🧮 Spoke Calculator")
    df_rims, df_hubs = get_table("rims"), get_table("hubs")
    if not df_rims.empty and not df_hubs.empty:
        c1, c2 = st.columns(2)
        # Safe Labeling Method
        df_rims['label'] = df_rims['brand'].str.cat(df_rims['model'], sep=" ").str.strip()
        df_hubs['label'] = df_hubs['brand'].str.cat(df_hubs['model'], sep=" ").str.strip()
        
        rim_sel = c1.selectbox("Select Rim", df_rims['label'])
        hub_sel = c2.selectbox("Select Hub", df_hubs['label'])
        
        r_dat = df_rims[df_rims['label'] == rim_sel].iloc[0]
        h_dat = df_hubs[df_hubs['label'] == hub_sel].iloc[0]
        
        i1, i2, i3 = st.columns(3)
        holes = i1.number_input("Spoke Count", value=int(r_dat.get('holes', 28)), step=2)
        l_cross = i2.selectbox("L-Cross", [0,1,2,3,4], index=3)
        r_cross = i3.selectbox("R-Cross", [0,1,2,3,4], index=3)
        is_sp = st.toggle("Straightpull?", value=True)
        
        res_l = calculate_precision_spoke(r_dat.get('erd', 0), h_dat.get('fd_l', 0), h_dat.get('os_l', 0), holes, l_cross, is_sp, h_dat.get('sp_off_l', 0))
        res_r = calculate_precision_spoke(r_dat.get('erd', 0), h_dat.get('fd_r', 0), h_dat.get('os_r', 0), holes, r_cross, is_sp, h_dat.get('sp_off_r', 0))
        
        st.metric("L Length", f"{res_l} mm"); st.metric("R Length", f"{res_r} mm")
        side = st.radio("Stage to:", ["Front", "Rear"], horizontal=True)
        if st.button("Apply and Stage"):
            if side == "Front": st.session_state.staged['f_l'], st.session_state.staged['f_r'] = res_l, res_r
            else: st.session_state.staged['r_l'], st.session_state.staged['r_r'] = res_l, res_r
            st.success(f"{side} staged!")

# --- INVENTORY ---
with tabs[3]:
    st.header("📦 Spoke Inventory")
    df_inv = get_table("spoke_inventory")
    if not df_inv.empty:
        st.dataframe(df_inv[['brand', 'model', 'length', 'stock']], use_container_width=True)

# --- REGISTER BUILD ---
with tabs[4]:
    st.header("📝 Register Build")
    df_rims, df_hubs, df_spk = get_table("rims"), get_table("hubs"), get_table("spokes")
    if not df_rims.empty:
        with st.form("new_build_form"):
            cust = st.text_input("Customer Name")
            # Re-applying safe labeling here
            rim_sel = st.selectbox("Rim", df_rims['brand'].str.cat(df_rims['model'], sep=" "))
            hub_sel = st.selectbox("Hub", df_hubs['brand'].str.cat(df_hubs['model'], sep=" "))
            spk_sel = st.selectbox("Spoke", df_spk['brand'].str.cat(df_spk['model'], sep=" "))
            
            st.divider()
            cl1, cl2, cl3, cl4 = st.columns(4)
            vfl, vfr = cl1.number_input("F-L", value=st.session_state.staged['f_l']), cl2.number_input("F-R", value=st.session_state.staged['f_r'])
            vrl, vrr = cl3.number_input("R-L", value=st.session_state.staged['r_l']), cl4.number_input("R-R", value=st.session_state.staged['r_r'])
            
            if st.form_submit_button("🚀 Finalize Build"):
                base.table("builds").create({
                    "customer": cust, "f_rim": rim_sel, "f_hub": hub_sel, "spoke": spk_sel,
                    "f_l": vfl, "f_r": vfr, "r_l": vrl, "r_r": vrr,
                    "date": datetime.now().strftime("%Y-%m-%d"), "status": "Complete"
                })
                st.cache_data.clear(); st.success("Build registered!"); st.rerun()

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

