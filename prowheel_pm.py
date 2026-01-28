import streamlit as st
import pandas as pd
import math
from datetime import datetime
from pyairtable import Api

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Wheelbuilder Lab v13.3", layout="wide", page_icon="🚲")

# --- 2. AIRTABLE CONNECTION ---
try:
    AIRTABLE_API_KEY = st.secrets["airtable"]["api_key"]
    AIRTABLE_BASE_ID = st.secrets["airtable"]["base_id"]
    api = Api(AIRTABLE_API_KEY)
    base = api.base(AIRTABLE_BASE_ID)
except Exception as e:
    st.error("❌ Airtable Secrets Error: Check Streamlit Cloud Secrets.")
    st.stop()

@st.cache_data(ttl=300)
def fetch_data(table_name, label_col):
    """Fetches records and standardizes labels for relational mapping."""
    try:
        table = base.table(table_name)
        records = table.all()
        if not records: return pd.DataFrame()
        data = []
        for rec in records:
            fields = rec['fields']
            fields['id'] = rec['id']
            if label_col in fields:
                fields['label'] = str(fields[label_col]).strip()
            data.append(fields)
        df = pd.DataFrame(data)
        for col in df.columns:
            df[col] = df[col].apply(lambda x: x[0] if isinstance(x, list) else x)
        return df
    except:
        return pd.DataFrame()

# --- 3. ANALYTICS HELPERS ---
def get_comp_data(df, label):
    """Retrieves the full row for a specific component label."""
    if df.empty or not label: return {}
    match = df[df['label'] == label]
    return match.iloc[0].to_dict() if not match.empty else {}

def calculate_spoke(erd, fd, os, holes, crosses, is_sp=False, sp_off=0.0):
    if not erd or not fd or not holes: return 0.0
    r_rim, r_hub = float(erd) / 2, float(fd) / 2
    angle_rad = math.radians((float(crosses) * 720.0) / float(holes))
    if not is_sp:
        l_sq = (r_rim**2) + (r_hub**2) + (float(os)**2) - (2 * r_rim * r_hub * math.cos(angle_rad))
        return round(math.sqrt(max(0, l_sq)) - 1.2, 1)
    else:
        base_l_sq = (r_rim**2) + (r_hub**2) - (2 * r_rim * r_hub * math.cos(angle_rad))
        length = math.sqrt(max(0, base_l_sq + float(os)**2)) + float(sp_off)
        return round(length, 1)

# --- 4. SESSION STATE ---
if 'build_stage' not in st.session_state:
    st.session_state.build_stage = {
        'f_rim': '', 'f_hub': '', 'f_l': 0.0, 'f_r': 0.0,
        'r_rim': '', 'r_hub': '', 'r_l': 0.0, 'r_r': 0.0
    }

# --- 5. MAIN UI ---
st.title("🚲 Wheelbuilder Lab v13.3")
st.caption(f"Precision Analytics & Staging")

tabs = st.tabs(["📊 Dashboard", "🧮 Precision Calc", "➕ Register Build", "📄 Spec Sheet", "📦 Library"])

# --- TAB 1: DASHBOARD ---
with tabs[0]:
    st.subheader("🏁 Workshop Pipeline")
    df_builds = fetch_data("builds", "customer")
    if not df_builds.empty:
        search = st.text_input("🔍 Search Customer")
        f_df = df_builds[df_builds['label'].str.contains(search, case=False)] if search else df_builds
        for _, row in f_df.sort_values('id', ascending=False).iterrows():
            with st.expander(f"🛠️ {row.get('customer')} — {row.get('status')}"):
                c1, c2, c3 = st.columns(3)
                if row.get('f_rim'):
                    c1.write(f"**Front:** {row.get('f_rim')}\n{row.get('f_l')} / {row.get('f_r')} mm")
                if row.get('r_rim'):
                    c2.write(f"**Rear:** {row.get('r_rim')}\n{row.get('r_l')} / {row.get('r_r')} mm")
                new_stat = c3.selectbox("Status", ["Order Received", "Building", "Complete"], key=f"st_{row['id']}", 
                                        index=["Order Received", "Building", "Complete"].index(row['status']) if row['status'] in ["Order Received", "Building", "Complete"] else 0)
                if new_stat != row['status']:
                    base.table("builds").update(row['id'], {"status": new_stat})
                    st.rerun()
    else: st.info("Pipeline empty.")

# --- TAB 2: CALCULATOR ---
with tabs[1]:
    st.header("🧮 Spoke Length Engine")
    df_rims = fetch_data("rims", "rim")
    df_hubs = fetch_data("hubs", "hub")
    
    if not df_rims.empty and not df_hubs.empty:
        c1, c2 = st.columns(2)
        r_sel = c1.selectbox("Select Rim", df_rims['label'])
        h_sel = c2.selectbox("Select Hub", df_hubs['label'])
        rd = get_comp_data(df_rims, r_sel)
        hd = get_comp_data(df_hubs, h_sel)
        
        st.divider()
        col1, col2, col3 = st.columns(3)
        is_sp = col1.toggle("Straightpull?", value=True)
        holes = col2.number_input("Holes", value=int(rd.get('holes', 28)))
        cross = col3.selectbox("Crosses", [0,1,2,3,4], index=3)
        
        l_len = calculate_spoke(rd.get('erd',0), hd.get('fd_l',0), hd.get('os_l',0), holes, cross, is_sp, hd.get('sp_off_l',0))
        r_len = calculate_spoke(rd.get('erd',0), hd.get('fd_r',0), hd.get('os_r',0), holes, cross, is_sp, hd.get('sp_off_r',0))
        
        st.metric("Left Spoke", f"{l_len} mm"); st.metric("Right Spoke", f"{r_len} mm")
        
        st.divider()
        target = st.radio("Stage these results for:", ["Front Wheel", "Rear Wheel"], horizontal=True)
        if st.button("💾 Stage Component Data"):
            if target == "Front Wheel":
                st.session_state.build_stage.update({'f_rim': r_sel, 'f_hub': h_sel, 'f_l': l_len, 'f_r': r_len})
            else:
                st.session_state.build_stage.update({'r_rim': r_sel, 'r_hub': h_sel, 'r_l': l_len, 'r_r': r_len})
            st.success(f"Successfully staged {target} data!")

# --- TAB 3: REGISTER BUILD ---
with tabs[2]:
    st.header("📝 Register New Build")
    build_type = st.radio("Build Configuration:", ["Full Wheelset", "Front Only", "Rear Only"], horizontal=True)
    df_spk = fetch_data("spokes", "spoke")
    df_nip = fetch_data("nipples", "nipple")

    with st.form("final_build_registration_v13_3"):
        customer = st.text_input("Customer Name")
        payload = {"customer": customer, "date": datetime.now().strftime("%Y-%m-%d"), "status": "Order Received"}
        col_f, col_r = st.columns(2)
        if build_type in ["Full Wheelset", "Front Only"]:
            with col_f:
                st.subheader("Front Wheel")
                f_rim = st.text_input("Front Rim", value=st.session_state.build_stage['f_rim'])
                f_hub = st.text_input("Front Hub", value=st.session_state.build_stage['f_hub'])
                f_l = st.number_input("F L-Length", value=st.session_state.build_stage['f_l'])
                f_r = st.number_input("F R-Length", value=st.session_state.build_stage['f_r'])
                payload.update({"f_rim": f_rim, "f_hub": f_hub, "f_l": f_l, "f_r": f_r})
        if build_type in ["Full Wheelset", "Rear Only"]:
            with col_r:
                st.subheader("Rear Wheel")
                r_rim = st.text_input("Rear Rim", value=st.session_state.build_stage['r_rim'])
                r_hub = st.text_input("Rear Hub", value=st.session_state.build_stage['r_hub'])
                r_l = st.number_input("R L-Length", value=st.session_state.build_stage['r_l'])
                r_r = st.number_input("R R-Length", value=st.session_state.build_stage['r_r'])
                payload.update({"r_rim": r_rim, "r_hub": r_hub, "r_l": r_l, "r_r": r_r})
        st.divider()
        sc1, sc2 = st.columns(2)
        spoke_mod = sc1.selectbox("Spoke Type", df_spk['label'] if not df_spk.empty else ["Standard"])
        nip_mod = sc2.selectbox("Nipple Type", df_nip['label'] if not df_nip.empty else ["Standard"])
        payload.update({"spoke": spoke_mod, "nipple": nip_mod, "notes": st.text_area("Build Notes")})
        if st.form_submit_button("🚀 Finalize Build"):
            base.table("builds").create(payload)
            st.session_state.build_stage = {'f_rim': '', 'f_hub': '', 'f_l': 0.0, 'f_r': 0.0, 'r_rim': '', 'r_hub': '', 'r_l': 0.0, 'r_r': 0.0}
            st.cache_data.clear(); st.success("Build registered!"); st.rerun()

# --- TAB 4: SPEC SHEET ---
with tabs[3]:
    st.header("📄 Precision Spec Sheet")
    df_builds = fetch_data("builds", "customer")
    if not df_builds.empty:
        selected_cust = st.selectbox("Select Customer Build", df_builds['label'].unique())
        b = df_builds[df_builds['label'] == selected_cust].iloc[0]
        
        # Load Libraries for Deep Weight Lookup
        df_r_lib, df_h_lib = fetch_data("rims", "rim"), fetch_data("hubs", "hub")
        df_s_lib, df_n_lib = fetch_data("spokes", "spoke"), fetch_data("nipples", "nipple")
        
        st.divider()
        st.markdown(f"### Technical Build Proof: **{selected_cust}**")
        
        # BOM Weight Tracking
        total_weight = 0.0
        
        c1, c2 = st.columns(2)
        with c1:
            st.write("#### 🔘 Front Wheel")
            if b.get('f_rim'):
                rd = get_comp_data(df_r_lib, b.get('f_rim'))
                hd = get_comp_data(df_h_lib, b.get('f_hub'))
                w_fr, w_fh, h_count = float(rd.get('weight', 0)), float(hd.get('weight', 0)), int(rd.get('holes', 28))
                st.write(f"**Rim:** {b.get('f_rim')} ({w_fr}g)")
                st.write(f"**Hub:** {b.get('f_hub')} ({w_fh}g)")
                st.info(f"**Lengths:** L: {b.get('f_l')} / R: {b.get('f_r')} mm")
                total_weight += (w_fr + w_fh)
                # Spoke/Nipple calc for front
                ws, wn = float(get_comp_data(df_s_lib, b.get('spoke')).get('weight', 0)), float(get_comp_data(df_n_lib, b.get('nipple')).get('weight', 0))
                total_weight += (h_count * (ws + wn))
            else: st.write("No front wheel in this build.")
                
        with c2:
            st.write("#### 🔘 Rear Wheel")
            if b.get('r_rim'):
                rd = get_comp_data(df_r_lib, b.get('r_rim'))
                hd = get_comp_data(df_h_lib, b.get('r_hub'))
                w_rr, w_rh, h_count = float(rd.get('weight', 0)), float(hd.get('weight', 0)), int(rd.get('holes', 28))
                st.write(f"**Rim:** {b.get('r_rim')} ({w_rr}g)")
                st.write(f"**Hub:** {b.get('r_hub')} ({w_rh}g)")
                st.success(f"**Lengths:** L: {b.get('r_l')} / R: {b.get('r_r')} mm")
                total_weight += (w_rr + w_rh)
                # Spoke/Nipple calc for rear
                ws, wn = float(get_comp_data(df_s_lib, b.get('spoke')).get('weight', 0)), float(get_comp_data(df_n_lib, b.get('nipple')).get('weight', 0))
                total_weight += (h_count * (ws + wn))
            else: st.write("No rear wheel in this build.")

        st.divider()
        st.metric("Estimated Total Wheelset Weight", f"{int(total_weight)}g")
        st.caption(f"Includes {b.get('spoke')} spokes and {b.get('nipple')} nipples.")
    else: st.info("No builds available.")

# --- TAB 5: LIBRARY ---
with tabs[4]:
    choice = st.radio("View Library:", ["rims", "hubs", "spokes", "nipples"], horizontal=True)
    st.dataframe(fetch_data(choice, "id"), use_container_width=True)
