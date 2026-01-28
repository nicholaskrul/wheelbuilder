import streamlit as st
import pandas as pd
import math
from datetime import datetime
from pyairtable import Api

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Wheelbuilder Lab v13.11", layout="wide", page_icon="🚲")

# --- 2. AIRTABLE CONNECTION ---
try:
    AIRTABLE_API_KEY = st.secrets["airtable"]["api_key"]
    AIRTABLE_BASE_ID = st.secrets["airtable"]["base_id"]
    api = Api(AIRTABLE_API_KEY)
    base = api.base(AIRTABLE_BASE_ID)
except Exception as e:
    st.error("❌ Secrets Error: Check Streamlit Cloud Settings.")
    st.stop()

@st.cache_data(ttl=600)
def get_table(table_name):
    """Hardened fetcher that handles both split and combined brand/model fields."""
    try:
        table = base.table(table_name)
        records = table.all()
        if not records: return pd.DataFrame()
        
        data = [ {**rec['fields'], 'id': rec['id']} for rec in records ]
        df = pd.DataFrame(data)
        
        # Standardize Text
        text_cols = ['brand', 'model', 'customer', 'status', 'f_hub', 'r_hub', 'f_rim', 'r_rim', 'spoke', 'nipple']
        for col in text_cols:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: x[0] if isinstance(x, list) else x)
                df[col] = df[col].fillna('').astype(str).str.strip()
        
        # Logic: If brand and model exist, combine them. If only model exists, use that.
        if 'brand' in df.columns and 'model' in df.columns:
            df['label'] = (df['brand'] + " " + df['model']).str.strip()
        elif 'model' in df.columns:
            df['label'] = df['model']
        else:
            # Fallback for tables like 'builds' where the first column might be 'customer'
            df['label'] = df.iloc[:, 0].astype(str)
            
        return df[df['label'] != ""]
    except Exception as e:
        st.warning(f"⚠️ Table '{table_name}' issue: {e}")
        return pd.DataFrame()

# --- 3. HELPERS ---
def get_weight(df, search_string):
    """Reliable weight lookup regardless of how the label was created."""
    if df.empty or not search_string: return 0.0
    try:
        # We strip both sides of the match to be safe
        match = df[df['label'].str.lower() == str(search_string).strip().lower()]
        if not match.empty and 'weight' in match.columns:
            val = match.iloc[0]['weight']
            return float(val) if val else 0.0
    except: pass
    return 0.0

def calculate_precision_spoke(erd, fd, os, holes, crosses, is_sp, sp_offset):
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
st.caption("v13.11 | Atomic Data Guard Active")
st.markdown("---")

tabs = st.tabs(["📊 Dashboard", "🧮 Precision Calc", "📦 Library", "➕ Register Build", "📄 Spec Sheet"])

# --- TAB 1: DASHBOARD ---
with tabs[0]:
    st.subheader("🏁 Workshop Pipeline")
    df_builds = get_table("builds")
    if not df_builds.empty:
        # Search/Filter UI
        f1, f2 = st.columns([2,1])
        q = f1.text_input("🔍 Search Customer")
        stat = f2.selectbox("Status Filter", ["All"] + sorted(list(df_builds['status'].unique())))
        
        view_df = df_builds.copy()
        if q: view_df = view_df[view_df['customer'].str.contains(q, case=False)]
        if stat != "All": view_df = view_df[view_df['status'] == stat]

        for _, row in view_df.sort_values('date', ascending=False).iterrows():
            with st.expander(f"🛠️ {row['customer']} — {row['status']}"):
                c_inf, c_ed = st.columns([3, 1])
                with c_inf:
                    st.write(f"**Front:** {row.get('f_l', 0)} / {row.get('f_r', 0)} mm")
                    st.write(f"**Rear:** {row.get('r_l', 0)} / {row.get('r_r', 0)} mm")
                with c_ed:
                    if st.button("✏️ Edit", key=f"btn_ed_{row['id']}"):
                        st.session_state.editing_id = row['id']
                
                if st.session_state.editing_id == row['id']:
                    st.markdown("---")
                    with st.form(f"f_ed_v11_{row['id']}"):
                        ns = st.selectbox("Status", ["Order received", "Parts received", "Build in progress", "Complete"], index=0)
                        cl1, cl2, cl3, cl4 = st.columns(4)
                        nl1, nr1 = cl1.number_input("F-L", value=float(row.get('f_l', 0))), cl2.number_input("F-R", value=float(row.get('f_r', 0)))
                        nl2, nr2 = cl3.number_input("R-L", value=float(row.get('r_l', 0))), cl4.number_input("R-R", value=float(row.get('r_r', 0)))
                        nt = st.text_area("Notes", value=str(row.get('notes', '')))
                        if st.form_submit_button("💾 Save"):
                            base.table("builds").update(row['id'], {"status": str(ns), "f_l": float(nl1), "f_r": float(nr1), "r_l": float(nl2), "r_r": float(nr2), "notes": str(nt)})
                            st.session_state.editing_id = None
                            st.cache_data.clear()
                            st.rerun()

# --- TAB 2: PRECISION CALC ---
with tabs[1]:
    st.header("🧮 Spoke Calculator")
    df_rims, df_hubs = get_table("rims"), get_table("hubs")
    if not df_rims.empty and not df_hubs.empty:
        c1, c2 = st.columns(2)
        r_sel = c1.selectbox("Select Rim", df_rims['label'])
        h_sel = c2.selectbox("Select Hub", df_hubs['label'])
        rd, hd = df_rims[df_rims['label']==r_sel].iloc[0], df_hubs[df_hubs['label']==h_sel].iloc[0]
        res_l = calculate_precision_spoke(rd.get('erd',0), hd.get('fd_l',0), hd.get('os_l',0), 28, 3, True, hd.get('sp_off_l',0))
        res_r = calculate_precision_spoke(rd.get('erd',0), hd.get('fd_r',0), hd.get('os_r',0), 28, 3, True, hd.get('sp_off_r',0))
        st.metric("Left", f"{res_l}mm"); st.metric("Right", f"{res_r}mm")
        trg = st.radio("Stage to:", ["Front", "Rear"], horizontal=True)
        if st.button("Apply"):
            k_l, k_r = ('f_l', 'f_r') if trg == "Front" else ('r_l', 'r_r')
            st.session_state.staged[k_l], st.session_state.staged[k_r] = res_l, res_r
            st.success("Staged!")

# --- TAB 5: SPEC SHEET ---
with tabs[4]:
    st.header("📄 Precision Spec Sheet")
    df_spec = get_table("builds")
    df_r_lib, df_h_lib = get_table("rims"), get_table("hubs")
    df_s_lib, df_n_lib = get_table("spokes"), get_table("nipples")

    if not df_spec.empty:
        selected = st.selectbox("Select Project", df_spec['customer'])
        b = df_spec[df_spec['customer'] == selected].iloc[0]
        
        # Lookups are now case-insensitive and whitespace-trimmed
        w_fr, w_rr = get_weight(df_r_lib, b.get('f_rim')), get_weight(df_r_lib, b.get('r_rim'))
        w_fh, w_rh = get_weight(df_h_lib, b.get('f_hub')), get_weight(df_h_lib, b.get('r_hub'))
        w_s, w_n = get_weight(df_s_lib, b.get('spoke')), get_weight(df_n_lib, b.get('nipple'))
        
        total_parts = int(b.get('spoke_count', 0)) * (w_s + w_n)
        total_w = w_fr + w_rr + w_fh + w_rh + total_parts

        st.subheader(f"Project Portfolio: {selected}")
        if b.get('invoice_url'): st.link_button("📄 Download Invoice", b['invoice_url'])
        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 🔘 Front Wheel")
            st.write(f"**Rim:** {b.get('f_rim')} ({w_fr}g)")
            st.write(f"**Hub:** {b.get('f_hub')} ({w_fh}g)")
        with col2:
            st.markdown("### 🔘 Rear Wheel")
            st.write(f"**Rim:** {b.get('r_rim')} ({w_rr}g)")
            st.write(f"**Hub:** {b.get('r_hub')} ({w_rh}g)")
            
        st.divider()
        st.metric("Est. Total Weight", f"{int(total_w)}g")
        
        if b.get('notes'): st.info(f"**Builder Notes:** {b.get('notes')}")
