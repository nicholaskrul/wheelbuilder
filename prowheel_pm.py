import streamlit as st
import pandas as pd
import math
from datetime import datetime
from pyairtable import Api

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Wheelbuilder Lab v12.8", layout="wide", page_icon="🚲")

# --- 2. AIRTABLE CONNECTION ---
try:
    AIRTABLE_API_KEY = st.secrets["airtable"]["api_key"]
    AIRTABLE_BASE_ID = st.secrets["airtable"]["base_id"]
    api = Api(AIRTABLE_API_KEY)
    base = api.base(AIRTABLE_BASE_ID)
except Exception as e:
    st.error("❌ Secrets Error: Check Streamlit Cloud Settings for [airtable] api_key and base_id.")
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
        
        # Fill NaN with empty strings to prevent concatenation errors
        for col in ['brand', 'model', 'customer', 'status']:
            if col in df.columns:
                df[col] = df[col].fillna('').astype(str).str.strip()
        
        # Create a safe display label (combines Brand + Model)
        if 'brand' in df.columns and 'model' in df.columns:
            df['label'] = df['brand'].str.cat(df['model'], sep=" ").str.strip()
            df = df[df['label'] != ""]
            
        return df
    except Exception as e:
        st.warning(f"⚠️ Table '{table_name}' issue: {e}")
        return pd.DataFrame()

# --- 3. REFINED CALCULATION ENGINE (v11.5) ---
def calculate_precision_spoke(erd, fd, os, holes, crosses, is_sp, sp_offset, round_mode="None"):
    if not erd or not fd or not holes: return 0.0
    r_rim, r_hub = float(erd) / 2, float(fd) / 2
    alpha_rad = math.radians((float(crosses) * 720.0) / float(holes))
    
    if not is_sp:
        # Standard J-Bend Geometry
        l_sq = (r_rim**2) + (r_hub**2) + (float(os)**2) - (2 * r_rim * r_hub * math.cos(alpha_rad))
        length = math.sqrt(max(0, l_sq)) - 1.2 
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
st.caption("v12.8 | Simplified Build Suite + Airtable")
st.markdown("---")

tab_list = ["📊 Dashboard", "🧮 Precision Calc", "📦 Library", "➕ Register Build", "📄 Spec Sheet"]
tabs = st.tabs(tab_list)

# --- TAB 1: DASHBOARD ---
with tabs[0]:
    st.subheader("🏁 Workshop Pipeline")
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    
    df_builds = get_table("builds")
    if not df_builds.empty:
        if 'date' in df_builds.columns:
            df_builds = df_builds.sort_values('date', ascending=False)
        
        for _, row in df_builds.iterrows():
            with st.expander(f"🛠️ {row.get('customer', 'Unknown')} — {row.get('status', 'N/A')}"):
                c1, c2 = st.columns(2)
                c1.write(f"**Date:** {row.get('date', 'N/A')}")
                c1.write(f"**Spoke Model:** {row.get('spoke', 'N/A')}")
                c2.write(f"**Front:** {row.get('f_l')} / {row.get('f_r')} mm")
                c2.write(f"**Rear:** {row.get('r_l')} / {row.get('r_r')} mm")
    else:
        st.info("Awaiting builds from Airtable...")

# --- TAB 2: PRECISION CALC ---
with tabs[1]:
    st.header("🧮 Spoke Calculator")
    df_rims, df_hubs = get_table("rims"), get_table("hubs")
    
    if not df_rims.empty and not df_hubs.empty:
        col1, col2 = st.columns(2)
        rim_sel = col1.selectbox("Select Rim", df_rims['label'])
        hub_sel = col2.selectbox("Select Hub", df_hubs['label'])
        
        r_dat = df_rims[df_rims['label'] == rim_sel].iloc[0]
        h_dat = df_hubs[df_hubs['label'] == hub_sel].iloc[0]
        
        st.divider()
        i1, i2, i3 = st.columns(3)
        holes = i1.number_input("Spoke Count", value=int(r_dat.get('holes', 28)), step=2)
        l_cross = i2.selectbox("L-Cross", [0,1,2,3,4], index=3)
        r_cross = i3.selectbox("R-Cross", [0,1,2,3,4], index=3)
        
        is_sp = st.toggle("Straightpull Hub?", value=True)
        r_mode = st.selectbox("Rounding", ["None", "Nearest Even", "Nearest Odd"])
        
        res_l = calculate_precision_spoke(r_dat.get('erd', 0), h_dat.get('fd_l', 0), h_dat.get('os_l', 0), holes, l_cross, is_sp, h_dat.get('sp_off_l', 0), r_mode)
        res_r = calculate_precision_spoke(r_dat.get('erd', 0), h_dat.get('fd_r', 0), h_dat.get('os_r', 0), holes, r_cross, is_sp, h_dat.get('sp_off_r', 0), r_mode)
        
        st.metric("Left Spoke Length", f"{res_l} mm")
        st.metric("Right Spoke Length", f"{res_r} mm")
        
        target = st.radio("Stage result to:", ["Front", "Rear"], horizontal=True)
        if st.button("Apply and Stage"):
            if target == "Front":
                st.session_state.staged['f_l'], st.session_state.staged['f_r'] = res_l, res_r
            else:
                st.session_state.staged['r_l'], st.session_state.staged['r_r'] = res_l, res_r
            st.success(f"Staged to {target}!")
    else:
        st.error("⚠️ Database Error: Check Airtable tables 'rims' and 'hubs'.")

# --- TAB 3: LIBRARY ---
with tabs[2]:
    st.header("📦 Component Library")
    lib_choice = st.radio("View Table:", ["rims", "hubs", "spokes", "nipples"], horizontal=True)
    st.dataframe(get_table(lib_choice), use_container_width=True)

# --- TAB 4: REGISTER BUILD ---
with tabs[3]:
    st.header("📝 Register New Build")
    df_rims, df_hubs, df_spk = get_table("rims"), get_table("hubs"), get_table("spokes")
    
    if not df_rims.empty:
        with st.form("classic_register_form"):
            cust = st.text_input("Customer Name")
            rim_sel = st.selectbox("Rim", df_rims['label'])
            hub_sel = st.selectbox("Hub", df_hubs['label'])
            spk_sel = st.selectbox("Spoke Model", df_spk['label'])
            
            st.divider()
            st.caption("Lengths from Calculator (Staged)")
            sc1, sc2, sc3, sc4 = st.columns(4)
            vfl = sc1.number_input("F-L", value=st.session_state.staged['f_l'])
            vfr = sc2.number_input("F-R", value=st.session_state.staged['f_r'])
            vrl = sc3.number_input("R-L", value=st.session_state.staged['r_l'])
            vrr = sc4.number_input("R-R", value=st.session_state.staged['r_r'])
            
            stat = st.selectbox("Status", ["Parts received", "Build in progress", "Complete"])
            inv = st.text_input("Invoice URL")
            
            if st.form_submit_button("🚀 Finalize Build"):
                base.table("builds").create({
                    "customer": cust, "f_rim": rim_sel, "f_hub": hub_sel, "spoke": spk_sel,
                    "f_l": vfl, "f_r": vfr, "r_l": vrl, "r_r": vrr,
                    "date": datetime.now().strftime("%Y-%m-%d"), "status": stat, "invoice_url": inv
                })
                st.cache_data.clear()
                st.success("Build registered successfully!")
                st.rerun()

# --- TAB 5: SPEC SHEET ---
with tabs[4]:
    st.header("📄 Portfolio Spec Sheet")
    df_spec = get_table("builds")
    if not df_spec.empty:
        selected_project = st.selectbox("Select Project", df_spec['customer'])
        b = df_spec[df_spec['customer'] == selected_project].iloc[0]
        
        st.subheader(f"Portfolio Record: {selected_project}")
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Front Wheel")
            st.write(f"**Rim/Hub:** {b.get('f_rim')} / {b.get('f_hub')}")
            st.info(f"Lengths: L {b.get('f_l')} / R {b.get('f_r')} mm")
        with col2:
            st.markdown("#### Rear Wheel")
            st.write(f"**Spoke Model:** {b.get('spoke')}")
            st.success(f"Rear Lengths: L {b.get('r_l')} / R {b.get('r_r')} mm")
