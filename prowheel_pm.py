import streamlit as st
import pandas as pd
import math
from datetime import datetime
from pyairtable import Api

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Wheelbuilder Lab v13.5", layout="wide", page_icon="🚲")

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
    """Fetches records and cleans data for safe lookup across relational tables."""
    try:
        table = base.table(table_name)
        records = table.all()
        if not records: return pd.DataFrame()
        
        data = [ {**rec['fields'], 'id': rec['id']} for rec in records ]
        df = pd.DataFrame(data)
        
        text_cols = ['brand', 'model', 'customer', 'status', 'f_hub', 'r_hub', 
                     'f_rim', 'r_rim', 'spoke', 'nipple', 'notes', 'invoice_url']
        for col in text_cols:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: x[0] if isinstance(x, list) else x)
                df[col] = df[col].fillna('').astype(str).str.strip()
        
        if 'brand' in df.columns and 'model' in df.columns:
            df['label'] = df['brand'].str.cat(df['model'], sep=" ").str.strip()
            df = df[df['label'] != ""]
            
        return df
    except Exception as e:
        st.warning(f"⚠️ Access issue with table '{table_name}'. Error: {e}")
        return pd.DataFrame()

# --- 3. HELPERS ---
def get_weight(df, label):
    if df.empty or not label: return 0.0
    try:
        match = df[df['label'] == label]
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
st.caption("v13.5 | Variable Logic Anchor Active")
st.markdown("---")

tabs = st.tabs(["📊 Dashboard", "🧮 Precision Calc", "📦 Library", "➕ Register Build", "📄 Spec Sheet"])

# --- TAB 1: DASHBOARD ---
with tabs[0]:
    st.subheader("🏁 Workshop Pipeline")
    df_builds = get_table("builds")
    
    if not df_builds.empty:
        f1, f2 = st.columns([2, 1])
        search = f1.text_input("🔍 Search Customer")
        status_options = ["All"] + sorted(list(df_builds['status'].unique()))
        status_filter = f2.selectbox("Filter Status", status_options)
        
        filtered_df = df_builds.copy()
        if search:
            filtered_df = filtered_df[filtered_df['customer'].str.contains(search, case=False)]
        if status_filter != "All":
            filtered_df = filtered_df[filtered_df['status'] == status_filter]

        for _, row in filtered_df.sort_values('date', ascending=False).iterrows():
            with st.expander(f"🛠️ {row['customer']} — {row['status']}"):
                col_info, col_edit = st.columns([3, 1])
                with col_info:
                    st.write(f"**Front:** {row.get('f_l', 0)} / {row.get('f_r', 0)} mm")
                    st.write(f"**Rear:** {row.get('r_l', 0)} / {row.get('r_r', 0)} mm")
                with col_edit:
                    if st.button("✏️ Edit", key=f"edit_dash_{row['id']}"):
                        st.session_state.editing_id = row['id']
                
                if st.session_state.editing_id == row['id']:
                    st.markdown("---")
                    with st.form(f"edit_form_dash_{row['id']}"):
                        new_stat = st.selectbox("Update Status", ["Order received", "Parts received", "Build in progress", "Complete"], 
                                                index=["Order received", "Parts received", "Build in progress", "Complete"].index(row['status']) if row['status'] in ["Order received", "Parts received", "Build in progress", "Complete"] else 0)
                        c1, c2, c3, c4 = st.columns(4)
                        nl1 = c1.number_input("F-L", value=float(row.get('f_l', 0)))
                        nr1 = c2.number_input("F-R", value=float(row.get('f_r', 0)))
                        nl2 = c3.number_input("R-L", value=float(row.get('r_l', 0)))
                        nr2 = c4.number_input("R-R", value=float(row.get('r_r', 0)))
                        new_notes = st.text_area("Update Notes", value=str(row.get('notes', '')))
                        
                        if st.form_submit_button("💾 Save Changes"):
                            update_payload = {"status": str(new_stat), "f_l": float(nl1), "f_r": float(nr1), "r_l": float(nl2), "r_r": float(nr2), "notes": str(new_notes)}
                            base.table("builds").update(row['id'], update_payload)
                            st.session_state.editing_id = None
                            st.cache_data.clear()
                            st.success("Updated!")
                            st.rerun()
    else: st.info("Connect Airtable to see builds.")

# --- TAB 2: PRECISION CALC (FIXED LOGIC) ---
with tabs[1]:
    st.header("🧮 Spoke Calculator")
    df_rims, df_hubs = get_table("rims"), get_table("hubs")
    
    # Anchor check: Only run if data exists to prevent NameError
    if df_rims.empty or df_hubs.empty:
        st.warning("⚠️ Library is empty. Please add rims and hubs to Airtable first.")
    else:
        c1, c2 = st.columns(2)
        rim_sel = c1.selectbox("Select Rim", df_rims['label'])
        hub_sel = c2.selectbox("Select Hub", df_hubs['label'])
        
        # Now it is safe to define h_dat because hub_sel is guaranteed to exist
        r_dat = df_rims[df_rims['label'] == rim_sel].iloc[0]
        h_dat = df_hubs[df_hubs['label'] == hub_sel].iloc[0]
        
        st.divider()
        i1, i2, i3 = st.columns(3)
        holes = i1.number_input("Spoke Count", value=int(r_dat.get('holes', 28)), step=2)
        l_cross = i2.selectbox("L-Cross", [0,1,2,3,4], index=3)
        r_cross = i3.selectbox("R-Cross", [0,1,2,3,4], index=3)
        is_sp = st.toggle("Straightpull Hub?", value=True)
        
        res_l = calculate_precision_spoke(r_dat.get('erd', 0), h_dat.get('fd_l', 0), h_dat.get('os_l', 0), holes, l_cross, is_sp, h_dat.get('sp_off_l', 0))
        res_r = calculate_precision_spoke(r_dat.get('erd', 0), h_dat.get('fd_r', 0), h_dat.get('os_r', 0), holes, r_cross, is_sp, h_dat.get('sp_off_r', 0))
        
        st.metric("Left Length", f"{res_l} mm")
        st.metric("Right Length", f"{res_r} mm")
        
        target = st.radio("Stage result to:", ["Front", "Rear"], horizontal=True)
        if st.button("Apply and Stage"):
            if target == "Front":
                st.session_state.staged['f_l'], st.session_state.staged['f_r'] = res_l, res_r
            else:
                st.session_state.staged['r_l'], st.session_state.staged['r_r'] = res_l, res_r
            st.success(f"Staged to {target}!")

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
        with st.form("register_v13_5"):
            cust = st.text_input("Customer Name")
            f_r, r_r = st.selectbox("Front Rim", df_rims['label']), st.selectbox("Rear Rim", df_rims['label'])
            f_h, r_h = st.selectbox("Front Hub", df_hubs['label']), st.selectbox("Rear Hub", df_hubs['label'])
            s_mod, n_mod = st.selectbox("Spoke Model", df_spk['label']), st.selectbox("Nipple Model", df_nip['label'])
            s_count = st.number_input("Total Spoke Count", value=56, step=4)
            st.divider()
            cl1, cl2, cl3, cl4 = st.columns(4)
            vfl = cl1.number_input("F-L", value=float(st.session_state.staged['f_l']))
            vfr = cl2.number_input("F-R", value=float(st.session_state.staged['f_r']))
            vrl = cl3.number_input("R-L", value=float(st.session_state.staged['r_l']))
            vrr = cl4.number_input("R-R", value=float(st.session_state.staged['r_r']))
            stat = st.selectbox("Status", ["Order received", "Parts received", "Build in progress", "Complete"])
            url = st.text_input("Invoice URL")
            notes = st.text_area("Build Notes")
            if st.form_submit_button("🚀 Finalize Build"):
                base.table("builds").create({"date": datetime.now().strftime("%Y-%m-%d"), "customer": cust, "status": stat, "f_rim": f_r, "r_rim": r_r, "f_hub": f_h, "r_hub": r_h, "spoke": s_mod, "nipple": n_mod, "spoke_count": int(s_count), "f_l": vfl, "f_r": vfr, "r_l": vrl, "r_r": vrr, "invoice_url": url, "notes": notes})
                st.cache_data.clear(); st.success("Registered!"); st.rerun()

# --- TAB 5: SPEC SHEET ---
with tabs[4]:
    st.header("📄 Precision Spec Sheet")
    df_spec = get_table("builds")
    if not df_spec.empty:
        selected = st.selectbox("Select Project", df_spec['customer'])
        b = df_spec[df_spec['customer'] == selected].iloc[0]
        
        # Deep lookup for weights
        df_rim_lib, df_hub_lib = get_table("rims"), get_table("hubs")
        df_spk_lib, df_nip_lib = get_table("spokes"), get_table("nipples")
        w_fr = get_weight(df_rim_lib, b.get('f_rim'))
        w_rr = get_weight(df_rim_lib, b.get('r_rim'))
        w_fh = get_weight(df_hub_lib, b.get('f_hub'))
        w_rh = get_weight(df_hub_lib, b.get('r_hub'))
        total_w = w_fr + w_rr + w_fh + w_rh + (int(b.get('spoke_count', 0)) * (get_weight(df_spk_lib, b.get('spoke')) + get_weight(df_nip_lib, b.get('nipple'))))

        st.subheader(f"Portfolio Record: {selected}")
        if b.get('invoice_url'): st.link_button("📄 Download Invoice", b['invoice_url'])
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 🔘 Front Wheel")
            st.write(f"**Rim:** {b.get('f_rim')} ({w_fr}g)")
            st.write(f"**Hub:** {b.get('f_hub')} ({w_fh}g)")
            st.info(f"**Lengths:** L {b.get('f_l', 0)}mm / R {b.get('f_r', 0)}mm")
        with col2:
            st.markdown("### 🔘 Rear Wheel")
            st.write(f"**Rim:** {b.get('r_rim')} ({w_rr}g)")
            st.write(f"**Hub:** {b.get('r_hub')} ({w_rh}g)")
            st.success(f"**Lengths:** L {b.get('r_l', 0)}mm / R {b.get('r_r', 0)}mm")
        st.divider()
        st.metric("Est. Total Weight", f"{int(total_w)}g")
        if b.get('notes'): st.info(f"**Builder Notes:** {b.get('notes')}")
