import streamlit as st
import pandas as pd
import math
from datetime import datetime
from pyairtable import Api

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Wheelbuilder Lab v12.12", layout="wide", page_icon="🚲")

# --- 2. AIRTABLE CONNECTION ---
try:
    AIRTABLE_API_KEY = st.secrets["airtable"]["api_key"]
    AIRTABLE_BASE_ID = st.secrets["airtable"]["base_id"]
    api = Api(AIRTABLE_API_KEY)
    base = api.base(AIRTABLE_BASE_ID)
except Exception as e:
    st.error("❌ Secrets Error: Please ensure [airtable] api_key and base_id are correctly entered in Streamlit Cloud Settings.")
    st.stop()

@st.cache_data(ttl=600)
def get_table(table_name):
    """Fetches records and cleans data using specific headers."""
    try:
        table = base.table(table_name)
        records = table.all()
        if not records: return pd.DataFrame()
        
        data = [ {**rec['fields'], 'id': rec['id']} for rec in records ]
        df = pd.DataFrame(data)
        
        # Shield against 'None' values in all text-based columns
        text_cols = ['brand', 'model', 'customer', 'status', 'f_hub', 'r_hub', 
                     'f_rim', 'r_rim', 'spoke', 'nipple', 'notes', 'invoice_url']
        for col in text_cols:
            if col in df.columns:
                # Handle potential list formats from Linked Records
                df[col] = df[col].apply(lambda x: x[0] if isinstance(x, list) else x)
                df[col] = df[col].fillna('').astype(str).str.strip()
        
        # Create a safe display label (combines Brand + Model)
        if 'brand' in df.columns and 'model' in df.columns:
            df['label'] = df['brand'].str.cat(df['model'], sep=" ").str.strip()
            df = df[df['label'] != ""]
            
        return df
    except Exception as e:
        st.warning(f"⚠️ Access issue with table '{table_name}'. Error: {e}")
        return pd.DataFrame()

# --- 3. REFINED CALCULATION ENGINE (v11.5 Math) ---
def calculate_precision_spoke(erd, fd, os, holes, crosses, is_sp, sp_offset):
    """Refined Engine for J-Bend and Straightpull pathing."""
    if not erd or not fd or not holes: return 0.0
    r_rim, r_hub = float(erd) / 2, float(fd) / 2
    alpha_rad = math.radians((float(crosses) * 720.0) / float(holes))
    
    if not is_sp:
        l_sq = (r_rim**2) + (r_hub**2) + (float(os)**2) - (2 * r_rim * r_hub * math.cos(alpha_rad))
        length = math.sqrt(max(0, l_sq)) - 1.2 
    else:
        base_l_sq = (r_rim**2) + (r_hub**2) - (2 * r_rim * r_hub * math.cos(alpha_rad))
        length = math.sqrt(max(0, base_l_sq + float(os)**2)) + float(sp_offset)
    return round(length, 1)

# --- 4. SESSION STATE ---
if 'staged' not in st.session_state:
    st.session_state.staged = {'f_l': 0.0, 'f_r': 0.0, 'r_l': 0.0, 'r_r': 0.0}

# --- 5. MAIN USER INTERFACE ---
st.title("🚲 Wheelbuilder Lab")
st.caption("v12.12 | Master Spec Suite (Linked Record Fix)")
st.markdown("---")

tab_list = ["📊 Dashboard", "🧮 Precision Calc", "📦 Library", "➕ Register Build", "📄 Spec Sheet"]
tabs = st.tabs(tab_list)

# --- TAB 1: DASHBOARD ---
with tabs[0]:
    st.subheader("🏁 Workshop Pipeline")
    if st.button("🔄 Force Data Refresh"):
        st.cache_data.clear()
        st.rerun()
        
    df_builds = get_table("builds")
    if not df_builds.empty:
        if 'date' in df_builds.columns:
            df_builds = df_builds.sort_values('date', ascending=False)
            
        for _, row in df_builds.iterrows():
            with st.container():
                c1, c2, c3 = st.columns([2, 2, 1])
                c1.write(f"**{row.get('customer', 'Unknown')}**")
                c2.write(f"Status: `{row.get('status', 'N/A')}`")
                c3.write(f"📅 {row.get('date', 'N/A')}")
                st.divider()
    else:
        st.info("Awaiting builds from Airtable...")

# --- TAB 2: PRECISION CALC ---
with tabs[1]:
    st.header("🧮 Spoke Calculator")
    df_rims, df_hubs = get_table("rims"), get_table("hubs")
    
    if not df_rims.empty and not df_hubs.empty:
        col1, col2 = st.columns(2)
        r_sel = col1.selectbox("Select Rim", df_rims['label'])
        hub_sel = col2.selectbox("Select Hub", df_hubs['label'])
        
        r_dat = df_rims[df_rims['label'] == r_sel].iloc[0]
        h_dat = df_hubs[df_hubs['label'] == hub_sel].iloc[0]
        
        st.divider()
        i1, i2, i3 = st.columns(3)
        holes = i1.number_input("Spoke Count", value=int(r_dat.get('holes', 28)), step=2)
        l_cross = i2.selectbox("L-Cross", [0,1,2,3,4], index=3)
        r_cross = i3.selectbox("R-Cross", [0,1,2,3,4], index=3)
        
        is_sp = st.toggle("Straightpull Hub?", value=True)
        
        res_l = calculate_precision_spoke(r_dat.get('erd', 0), h_dat.get('fd_l', 0), h_dat.get('os_l', 0), holes, l_cross, is_sp, h_dat.get('sp_off_l', 0))
        res_r = calculate_precision_spoke(r_dat.get('erd', 0), h_dat.get('fd_r', 0), h_dat.get('os_r', 0), holes, r_cross, is_sp, h_dat.get('sp_off_r', 0))
        
        st.metric("Left Spoke Length", f"{res_l} mm")
        st.metric("Right Spoke Length", f"{res_r} mm")
        
        target = st.radio("Stage result to:", ["Front", "Rear"], horizontal=True)
        if st.button("Apply and Stage"):
            if target == "Front":
                st.session_state.staged['f_l'], st.session_state.staged['f_r'] = res_l, res_r
            else:
                st.session_state.staged['r_l'], st.session_state.staged['r_r'] = res_l, res_r
            st.success(f"Successfully staged to {target}!")

# --- TAB 3: LIBRARY ---
with tabs[2]:
    st.header("📦 Component Library")
    lib = st.radio("View Table:", ["rims", "hubs", "spokes", "nipples"], horizontal=True)
    st.dataframe(get_table(lib), use_container_width=True)

# --- TAB 4: REGISTER BUILD ---
with tabs[3]:
    st.header("📝 Register New Build")
    df_rims, df_hubs, df_spk, df_nip = get_table("rims"), get_table("hubs"), get_table("spokes"), get_table("nipples")
    
    if not df_rims.empty:
        with st.form("master_build_form"):
            col_a, col_b = st.columns(2)
            cust = col_a.text_input("Customer Name")
            date_b = col_b.date_input("Build Date", datetime.now())
            
            f_rim = st.selectbox("Front Rim", df_rims['label'])
            r_rim = st.selectbox("Rear Rim", df_rims['label'])
            f_hub = st.selectbox("Front Hub", df_hubs['label'])
            r_hub = st.selectbox("Rear Hub", df_hubs['label'])
            
            c_spk, c_nip = st.columns(2)
            spk_sel = c_spk.selectbox("Spoke Model", df_spk['label'])
            nip_sel = c_nip.selectbox("Nipple Type", df_nip['label'])
            
            s_count = st.number_input("Total Spoke Count", value=int(df_rims[df_rims['label']==f_rim]['holes'].iloc[0]) * 2 if f_rim else 56)
            
            st.divider()
            cl1, cl2, cl3, cl4 = st.columns(4)
            vfl, vfr = cl1.number_input("F-L", value=st.session_state.staged['f_l']), cl2.number_input("F-R", value=st.session_state.staged['f_r'])
            vrl, vrr = cl3.number_input("R-L", value=st.session_state.staged['r_l']), cl4.number_input("R-R", value=st.session_state.staged['r_r'])
            
            stat = st.selectbox("Status", ["Order received", "Parts received", "Build in progress", "Complete"])
            url = st.text_input("Invoice URL")
            notes = st.text_area("Build Notes")
            
            if st.form_submit_button("🚀 Finalize & Save Build"):
                base.table("builds").create({
                    "date": str(date_b), "customer": cust, "status": stat,
                    "f_hub": f_hub, "r_hub": r_hub, "f_rim": f_rim, "r_rim": r_rim,
                    "spoke": spk_sel, "spoke_count": int(s_count), "nipple": nip_sel,
                    "f_l": vfl, "f_r": vfr, "r_l": vrl, "r_r": vrr,
                    "invoice_url": url, "notes": notes
                })
                st.cache_data.clear()
                st.success("Build registered successfully!")
                st.rerun()

# --- TAB 5: SPEC SHEET ---
with tabs[4]:
    st.header("📄 Portfolio Spec Sheet")
    df_spec = get_table("builds")
    if not df_spec.empty:
        selected = st.selectbox("Select Build to View", df_spec['customer'])
        b = df_spec[df_spec['customer'] == selected].iloc[0]
        
        st.subheader(f"Project Portfolio: {selected}")
        st.caption(f"Build Date: {b.get('date', 'N/A')}")
        
        if b.get('invoice_url'):
            st.link_button("📄 Download Invoice", b['invoice_url'])
        
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 🔘 Front Wheel")
            st.write(f"**Rim:** {b.get('f_rim')}")
            st.write(f"**Hub:** {b.get('f_hub')}")
            st.info(f"**Lengths:** L {b.get('f_l')}mm / R {b.get('f_r')}mm")
        with col2:
            st.markdown("### 🔘 Rear Wheel")
            st.write(f"**Rim:** {b.get('r_rim')}")
            st.write(f"**Hub:** {b.get('r_hub')}")
            st.success(f"**Lengths:** L {b.get('r_l')}mm / R {b.get('r_r')}mm")
            
        st.divider()
        st.markdown(f"### ⚙️ Build Specs")
        sc1, sc2, sc3 = st.columns(3)
        sc1.write(f"**Spoke Type:** {b.get('spoke')}")
        sc2.write(f"**Nipple Type:** {b.get('nipple')}")
        sc3.write(f"**Total Count:** {b.get('spoke_count')}")
        
        if b.get('notes'):
            st.info(f"**Builder Notes:** {b.get('notes')}")
