import streamlit as st
import pandas as pd
import math
from datetime import datetime
from pyairtable import Api

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Wheelbuilder Lab v14.8", layout="wide", page_icon="🚲")

# --- 2. AIRTABLE CONNECTION ---
try:
    AIRTABLE_API_KEY = st.secrets["airtable"]["api_key"]
    AIRTABLE_BASE_ID = st.secrets["airtable"]["base_id"]
    api = Api(AIRTABLE_API_KEY)
    base = api.base(AIRTABLE_BASE_ID)
except Exception as e:
    st.error(f"❌ Connection Error: {e}")
    st.stop()

@st.cache_data(ttl=60)
def get_table(table_name):
    """Fetches records and standardizes data for relational mapping."""
    try:
        table = base.table(table_name)
        records = table.all()
        if not records: return pd.DataFrame()
        
        data = [ {**rec['fields'], 'id': rec['id']} for rec in records ]
        df = pd.DataFrame(data)
        
        # Clean text columns and handle Airtable's list-format for linked records
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].apply(lambda x: x[0] if isinstance(x, list) else x)
                df[col] = df[col].fillna('').astype(str).str.strip()
        
        # LABEL LOGIC: We assume the first column in the Airtable table is the Primary Field
        # We find the name of the first column dynamically from the first record.
        if not df.empty:
            # We filter out 'id' to find the actual primary field name
            cols = list(records[0]['fields'].keys())
            primary_col = cols[0]
            df['label'] = df[primary_col].astype(str).str.strip()
            
        return df
    except Exception as e:
        st.warning(f"⚠️ Issue accessing table '{table_name}': {e}")
        return pd.DataFrame()

# --- 3. CORE HELPERS ---
def find_weight(df, search_term):
    """Looks for a match in the 'label' column and pulls from 'weight' or 'Weight'."""
    if df.empty or not search_term: return 0.0
    target = str(search_term).strip().lower()
    
    # Identify the weight column dynamically
    weight_col = next((c for c in df.columns if c.lower() == 'weight'), None)
    if not weight_col: return 0.0
    
    match = df[df['label'].str.lower() == target]
    if not match.empty:
        val = match.iloc[0][weight_col]
        try: return float(val)
        except: return 0.0
    return 0.0

def calculate_precision_spoke(erd, fd, os, holes, crosses, is_sp, sp_offset):
    """Math engine for spoke lengths."""
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
if 'editing_id' not in st.session_state:
    st.session_state.editing_id = None

# --- 5. MAIN UI ---
st.title("🚲 Wheelbuilder Lab")
st.caption("v14.8 | Full Suite & Diagnostic Mode")
st.markdown("---")

tabs = st.tabs(["📊 Dashboard", "🧮 Precision Calc", "📦 Library", "➕ Register Build", "📄 Spec Sheet"])

# --- TAB 1: DASHBOARD ---
with tabs[0]:
    st.subheader("🏁 Workshop Pipeline")
    df_builds = get_table("builds")
    if not df_builds.empty:
        for _, row in df_builds.sort_values('date', ascending=False).iterrows():
            with st.expander(f"🛠️ {row.get('customer', 'Unknown')} — {row.get('status', 'N/A')}"):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.write(f"**Front:** {row.get('f_l')} / {row.get('f_r')} mm")
                    st.write(f"**Rear:** {row.get('r_l')} / {row.get('r_r')} mm")
                with c2:
                    if st.button("✏️ Edit", key=f"ed_{row['id']}"):
                        st.session_state.editing_id = row['id']
                
                if st.session_state.editing_id == row['id']:
                    with st.form(f"edit_form_{row['id']}"):
                        new_stat = st.selectbox("Status", ["Order received", "Parts received", "Build in progress", "Complete"])
                        nl1 = st.number_input("F-L", value=float(row.get('f_l', 0)))
                        nr1 = st.number_input("F-R", value=float(row.get('f_r', 0)))
                        if st.form_submit_button("💾 Save"):
                            base.table("builds").update(row['id'], {"status": new_stat, "f_l": nl1, "f_r": nr1})
                            st.session_state.editing_id = None
                            st.cache_data.clear()
                            st.rerun()

# --- TAB 2: PRECISION CALC ---
with tabs[1]:
    st.header("🧮 Spoke Calculator")
    df_rims, df_hubs = get_table("rims"), get_table("hubs")
    if not df_rims.empty and not df_hubs.empty:
        ca, cb = st.columns(2)
        r_sel = ca.selectbox("Select Rim", df_rims['label'])
        h_sel = cb.selectbox("Select Hub", df_hubs['label'])
        rd = df_rims[df_rims['label'] == r_sel].iloc[0]
        hd = df_hubs[df_hubs['label'] == h_sel].iloc[0]
        
        is_sp = st.toggle("Straightpull?", value=True)
        res_l = calculate_precision_spoke(rd.get('erd', 0), hd.get('fd_l', 0), hd.get('os_l', 0), 28, 3, is_sp, hd.get('sp_off_l', 0))
        res_r = calculate_precision_spoke(rd.get('erd', 0), hd.get('fd_r', 0), hd.get('os_r', 0), 28, 3, is_sp, hd.get('sp_off_r', 0))
        
        st.metric("Left", f"{res_l}mm"); st.metric("Right", f"{res_r}mm")
        if st.button("Apply & Stage"):
            st.session_state.staged['f_l'], st.session_state.staged['f_r'] = res_l, res_r
            st.success("Staged for Register Build tab!")

# --- TAB 3: LIBRARY DIAGNOSTIC ---
with tabs[2]:
    st.header("📦 Library Diagnostic")
    choice = st.radio("Inspect Table:", ["rims", "hubs", "spokes", "nipples"], horizontal=True)
    inspect_df = get_table(choice)
    if not inspect_df.empty:
        st.write(f"✅ Found **{len(inspect_df)}** records.")
        st.dataframe(inspect_df)
        st.write("**Raw Columns Detected:**", list(inspect_df.columns))
    else:
        st.error(f"❌ Table '{choice}' is empty or not found in Airtable.")

# --- TAB 4: REGISTER NEW BUILD ---
with tabs[3]:
    st.header("📝 Register New Build")
    df_rims, df_hubs = get_table("rims"), get_table("hubs")
    if not df_rims.empty:
        with st.form("reg_v14_8"):
            cust = st.text_input("Customer Name")
            f_r = st.selectbox("Front Rim", df_rims['label'])
            f_h = st.selectbox("Front Hub", df_hubs['label'])
            # Pulling staged values from session state
            vfl = st.number_input("F-L Length", value=float(st.session_state.staged['f_l']))
            vfr = st.number_input("F-R Length", value=float(st.session_state.staged['f_r']))
            if st.form_submit_button("🚀 Finalize Build"):
                base.table("builds").create({
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "customer": cust, "f_rim": f_r, "f_hub": f_h,
                    "f_l": vfl, "f_r": vfr, "status": "Parts received"
                })
                st.cache_data.clear(); st.success("Registered!"); st.rerun()

# --- TAB 5: SPEC SHEET ---
with tabs[4]:
    st.header("📄 Spec Sheet")
    df_builds = get_table("builds")
    if not df_builds.empty:
        selected_project = st.selectbox("Select Build", df_builds['customer'].unique())
        b = df_builds[df_builds['customer'] == selected_project].iloc[0]
        
        # Pull weights
        df_r, df_h = get_table("rims"), get_table("hubs")
        w_rim = find_weight(df_r, b.get('f_rim'))
        w_hub = find_weight(df_h, b.get('f_hub'))
        
        st.write(f"### Project: {selected_project}")
        st.divider()
        st.write(f"**Rim:** {b.get('f_rim')} ({w_rim}g)")
        st.write(f"**Hub:** {b.get('f_hub')} ({w_hub}g)")
        st.metric("Total Weight (Half)", f"{w_rim + w_hub}g")
