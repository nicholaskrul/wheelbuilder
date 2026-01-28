import streamlit as st
import pandas as pd
import math
from datetime import datetime
from pyairtable import Api

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Wheelbuilder Lab v14.5", layout="wide", page_icon="🚲")

# --- 2. AIRTABLE CONNECTION ---
try:
    AIRTABLE_API_KEY = st.secrets["airtable"]["api_key"]
    AIRTABLE_BASE_ID = st.secrets["airtable"]["base_id"]
    api = Api(AIRTABLE_API_KEY)
    base = api.base(AIRTABLE_BASE_ID)
except Exception as e:
    st.error("❌ Secrets Error: Please ensure Airtable API keys are set in Streamlit Cloud.")
    st.stop()

@st.cache_data(ttl=600)
def get_table(table_name):
    """Fetches records and uses the first column (Primary Field) as the unique label."""
    try:
        table = base.table(table_name)
        records = table.all()
        if not records: return pd.DataFrame()
        
        data = [ {**rec['fields'], 'id': rec['id']} for rec in records ]
        df = pd.DataFrame(data)
        
        # Clean text columns and handle Airtable's list-format for linked records
        text_cols = ['brand', 'model', 'customer', 'status', 'f_hub', 'r_hub', 'f_rim', 'r_rim', 'spoke', 'nipple', 'notes']
        for col in text_cols:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: x[0] if isinstance(x, list) else x)
                df[col] = df[col].fillna('').astype(str).str.strip()
        
        # LABEL LOGIC: Always use the Primary Column as the 'label' for UI and matching
        # In Airtable API results, the first key in 'fields' corresponds to the Primary Field.
        # We find the name of the first column dynamically.
        if not df.empty:
            primary_col_name = list(records[0]['fields'].keys())[0]
            df['label'] = df[primary_col_name].astype(str).str.strip()
            
        return df[df['label'] != ""]
    except Exception as e:
        st.warning(f"⚠️ Issue accessing table '{table_name}'.")
        return pd.DataFrame()

# --- 3. CORE LOGIC HELPERS ---
def get_weight(df, search_label):
    """Finds the weight for a specific component label."""
    if df.empty or not search_label: return 0.0
    try:
        match = df[df['label'].str.lower() == str(search_label).strip().lower()]
        if not match.empty and 'weight' in match.columns:
            val = match.iloc[0]['weight']
            return float(val) if val else 0.0
    except: pass
    return 0.0

def calculate_precision_spoke(erd, fd, os, holes, crosses, is_sp, sp_offset):
    """Spoke Math v11.5 Math Engine."""
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
st.caption("v14.5 | Primary Formula & Master Analytics")
st.markdown("---")

tabs = st.tabs(["📊 Dashboard", "🧮 Precision Calc", "📦 Library", "➕ Register Build", "📄 Spec Sheet"])

# --- TAB 1: DASHBOARD ---
with tabs[0]:
    st.subheader("🏁 Workshop Pipeline")
    df_builds = get_table("builds")
    if not df_builds.empty:
        c1, c2 = st.columns([2,1])
        q = c1.text_input("🔍 Search Customer")
        stat_filter = c2.selectbox("Filter Status", ["All"] + sorted(list(df_builds['status'].unique())))
        
        view_df = df_builds.copy()
        if q: view_df = view_df[view_df['customer'].str.contains(q, case=False)]
        if stat_filter != "All": view_df = view_df[view_df['status'] == stat_filter]

        for _, row in view_df.sort_values('date', ascending=False).iterrows():
            with st.expander(f"🛠️ {row['customer']} — {row['status']}"):
                col_i, col_e = st.columns([3, 1])
                with col_i:
                    st.write(f"**Front:** {row.get('f_l', 0)} / {row.get('f_r', 0)} mm")
                    st.write(f"**Rear:** {row.get('r_l', 0)} / {row.get('r_r', 0)} mm")
                with col_e:
                    if st.button("✏️ Edit", key=f"edit_v14_5_{row['id']}"):
                        st.session_state.editing_id = row['id']
                
                if st.session_state.editing_id == row['id']:
                    st.markdown("---")
                    with st.form(f"form_v14_5_{row['id']}"):
                        new_stat = st.selectbox("Status", ["Order received", "Parts received", "Build in progress", "Complete"], index=0)
                        l1, r1 = st.columns(2)
                        nl1 = l1.number_input("F-L", value=float(row.get('f_l', 0)))
                        nr1 = r1.number_input("F-R", value=float(row.get('f_r', 0)))
                        l2, r2 = st.columns(2)
                        nl2 = l2.number_input("R-L", value=float(row.get('r_l', 0)))
                        nr2 = r2.number_input("R-R", value=float(row.get('r_r', 0)))
                        new_notes = st.text_area("Update Notes", value=str(row.get('notes', '')))
                        
                        if st.form_submit_button("💾 Save Changes"):
                            base.table("builds").update(row['id'], {
                                "status": str(new_stat), "f_l": float(nl1), "f_r": float(nr1), 
                                "r_l": float(nl2), "r_r": float(nr2), "notes": str(new_notes)
                            })
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
        rd, hd = df_rims[df_rims['label']==r_sel].iloc[0], df_hubs[df_hubs['label']==h_sel].iloc[0]
        
        is_sp = st.toggle("Straightpull?", value=True)
        holes = st.number_input("Spoke Count", value=int(rd.get('holes', 28)))
        
        res_l = calculate_precision_spoke(rd.get('erd',0), hd.get('fd_l',0), hd.get('os_l',0), holes, 3, is_sp, hd.get('sp_off_l',0))
        res_r = calculate_precision_spoke(rd.get('erd',0), hd.get('fd_r',0), hd.get('os_r',0), holes, 3, is_sp, hd.get('sp_off_r',0))
        
        st.metric("Left Spoke", f"{res_l}mm")
        st.metric("Right Spoke", f"{res_r}mm")
        
        trg = st.radio("Stage result for registration:", ["Front", "Rear"], horizontal=True)
        if st.button("Apply and Stage"):
            k_l, k_r = ('f_l', 'f_r') if trg == "Front" else ('r_l', 'r_r')
            st.session_state.staged[k_l], st.session_state.staged[k_r] = res_l, res_r
            st.success(f"Successfully staged for {trg} wheel!")

# --- TAB 4: REGISTER NEW BUILD ---
with tabs[3]:
    st.header("📝 Register New Build")
    df_rims, df_hubs, df_spk, df_nip = get_table("rims"), get_table("hubs"), get_table("spokes"), get_table("nipples")
    if not df_rims.empty:
        with st.form("master_register_v14_5"):
            cust = st.text_input("Customer Name")
            f_rim, r_rim = st.selectbox("Front Rim", df_rims['label']), st.selectbox("Rear Rim", df_rims['label'])
            f_hub, r_hub = st.selectbox("Front Hub", df_hubs['label']), st.selectbox("Rear Hub", df_hubs['label'])
            spk_mod, nip_mod = st.selectbox("Spoke Model", df_spk['label']), st.selectbox("Nipple Model", df_nip['label'])
            s_count = st.number_input("Total Spoke Count", value=56, step=4)
            
            st.divider()
            cl1, cl2, cl3, cl4 = st.columns(4)
            vfl = cl1.number_input("F-L", value=float(st.session_state.staged['f_l']))
            vfr = cl2.number_input("F-R", value=float(st.session_state.staged['f_r']))
            vrl = cl3.number_input("R-L", value=float(st.session_state.staged['r_l']))
            vrr = cl4.number_input("R-R", value=float(st.session_state.staged['r_r']))
            
            stat = st.selectbox("Status", ["Order received", "Parts received", "Build in progress", "Complete"])
            notes = st.text_area("Initial Build Notes")
            
            if st.form_submit_button("🚀 Finalize Build"):
                base.table("builds").create({
                    "date": datetime.now().strftime("%Y-%m-%d"), "customer": cust, "status": stat,
                    "f_rim": f_rim, "r_rim": r_rim, "f_hub": f_hub, "r_hub": r_hub,
                    "spoke": spk_mod, "nipple": nip_mod, "spoke_count": int(s_count),
                    "f_l": vfl, "f_r": vfr, "r_l": vrl, "r_r": vrr, "notes": notes
                })
                st.cache_data.clear(); st.success("Build Registered Successfully!"); st.rerun()

# --- TAB 5: PORTFOLIO SPEC SHEET ---
with tabs[4]:
    st.header("📄 Portfolio Spec Sheet")
    df_spec = get_table("builds")
    df_r_lib, df_h_lib = get_table("rims"), get_table("hubs")
    df_s_lib, df_n_lib = get_table("spokes"), get_table("nipples")

    if not df_spec.empty:
        selected_build = st.selectbox("Select Project", df_spec['customer'])
        b = df_spec[df_spec['customer'] == selected_build].iloc[0]
        
        # Pulling weights for the final spec breakdown
        w_fr, w_rr = get_weight(df_r_lib, b.get('f_rim')), get_weight(df_r_lib, b.get('r_rim'))
        w_fh, w_rh = get_weight(df_h_lib, b.get('f_hub')), get_weight(df_h_lib, b.get('r_hub'))
        w_s, w_n = get_weight(df_s_lib, b.get('spoke')), get_weight(df_n_lib, b.get('nipple'))
        
        total_p = int(b.get('spoke_count', 0)) * (w_s + w_n)
        total_weight = w_fr + w_rr + w_fh + w_rh + total_p

        st.subheader(f"Project Portfolio: {selected_build}")
        st.divider()

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("### 🔘 Front Wheel")
            st.write(f"**Rim:** {b.get('f_rim')} ({w_fr}g)")
            st.write(f"**Hub:** {b.get('f_hub')} ({w_fh}g)")
            st.info(f"**Lengths:** L {b.get('f_l', 0)}mm / R {b.get('f_r', 0)}mm")
        with col_b:
            st.markdown("### 🔘 Rear Wheel")
            st.write(f"**Rim:** {b.get('r_rim')} ({w_rr}g)")
            st.write(f"**Hub:** {b.get('r_hub')} ({w_rh}g)")
            st.success(f"**Lengths:** L {b.get('r_l', 0)}mm / R {b.get('r_r', 0)}mm")
            
        st.divider()
        st.metric("Est. Total Wheelset Weight", f"{int(total_weight)}g")
        if b.get('notes'): st.info(f"**Builder Notes:** {b.get('notes')}")
