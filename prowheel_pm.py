import streamlit as st
import pandas as pd
import math
from datetime import datetime
from pyairtable import Api

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Wheelbuilder Lab v14.0", layout="wide", page_icon="🚲")

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
    """Retrieves component data using a case-insensitive, whitespace-agnostic match."""
    if df.empty or not label: return {}
    target = str(label).strip().lower()
    df_norm = df.copy()
    df_norm['match_label'] = df_norm['label'].str.strip().str.lower()
    match = df_norm[df_norm['match_label'] == target]
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
st.title("🚲 Wheelbuilder Lab v14.0")
st.caption("Inventory Traceability | Serial Number Tracking")

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
                
                # Front Wheel View
                with c1:
                    if row.get('f_rim'):
                        st.write(f"**Front:** {row.get('f_rim')}")
                        st.caption(f"Ser: {row.get('f_rim_serial', '---')}")
                    else: st.write("No Front Wheel")
                
                # Rear Wheel View
                with c2:
                    if row.get('r_rim'):
                        st.write(f"**Rear:** {row.get('r_rim')}")
                        st.caption(f"Ser: {row.get('r_rim_serial', '---')}")
                    else: st.write("No Rear Wheel")
                
                # Status & Serial Updates
                with c3:
                    current_status = row.get('status', 'Order Received')
                    status_options = ["Order Received", "Parts Received", "Building", "Complete"]
                    new_stat = st.selectbox("Status", status_options, key=f"st_{row['id']}", 
                                            index=status_options.index(current_status) if current_status in status_options else 0)
                    
                    if new_stat != current_status:
                        base.table("builds").update(row['id'], {"status": new_stat})
                        st.rerun()

                    # Inline Serial Update Logic
                    if current_status in ["Parts Received", "Building", "Complete"]:
                        with st.popover("📝 Edit Serial Numbers"):
                            new_f_ser = st.text_input("Front Rim Serial", value=row.get('f_rim_serial', ''), key=f"fser_{row['id']}")
                            new_r_ser = st.text_input("Rear Rim Serial", value=row.get('r_rim_serial', ''), key=f"rser_{row['id']}")
                            if st.button("Save Serials", key=f"btn_ser_{row['id']}"):
                                base.table("builds").update(row['id'], {"f_rim_serial": new_f_ser, "r_rim_serial": new_r_ser})
                                st.success("Updated!")
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
        target = st.radio("Stage results for:", ["Front Wheel", "Rear Wheel"], horizontal=True)
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

    with st.form("build_registration_v14_0"):
        customer = st.text_input("Customer Name")
        inv_url = st.text_input("Invoice URL")
        payload = {"customer": customer, "date": datetime.now().strftime("%Y-%m-%d"), "status": "Order Received", "invoice_url": inv_url}
        
        col_f, col_r = st.columns(2)
        if build_type in ["Full Wheelset", "Front Only"]:
            with col_f:
                st.subheader("Front Wheel")
                f_rim = st.text_input("Front Rim", value=st.session_state.build_stage['f_rim'])
                f_hub = st.text_input("Front Hub", value=st.session_state.build_stage['f_hub'])
                f_l = st.number_input("F L-Length", value=st.session_state.build_stage['f_l'])
                f_r = st.number_input("F R-Length", value=st.session_state.build_stage['f_r'])
                f_ser = st.text_input("Front Rim Serial (Optional)")
                payload.update({"f_rim": f_rim, "f_hub": f_hub, "f_l": f_l, "f_r": f_r, "f_rim_serial": f_ser})
        
        if build_type in ["Full Wheelset", "Rear Only"]:
            with col_r:
                st.subheader("Rear Wheel")
                r_rim = st.text_input("Rear Rim", value=st.session_state.build_stage['r_rim'])
                r_hub = st.text_input("Rear Hub", value=st.session_state.build_stage['r_hub'])
                r_l = st.number_input("R L-Length", value=st.session_state.build_stage['r_l'])
                r_r = st.number_input("R R-Length", value=st.session_state.build_stage['r_r'])
                r_ser = st.text_input("Rear Rim Serial (Optional)")
                payload.update({"r_rim": r_rim, "r_hub": r_hub, "r_l": r_l, "r_r": r_r, "r_rim_serial": r_ser})
        
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
        
        df_r_lib, df_h_lib = fetch_data("rims", "rim"), fetch_data("hubs", "hub")
        df_s_lib, df_n_lib = fetch_data("spokes", "spoke"), fetch_data("nipples", "nipple")
        
        st.divider()
        col_header, col_invoice = st.columns([3, 1])
        with col_header:
            st.markdown(f"### Technical Build Proof: **{selected_cust}**")
        with col_invoice:
            if b.get('invoice_url'):
                st.link_button("📄 Download Invoice", b['invoice_url'], use_container_width=True)
        
        total_wheelset_weight = 0.0
        ws_data = get_comp_data(df_s_lib, b.get('spoke'))
        wn_data = get_comp_data(df_n_lib, b.get('nipple'))
        ws_weight = float(ws_data.get('weight', 0))
        wn_weight = float(wn_data.get('weight', 0))
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("#### 🔘 Front Wheel")
            if b.get('f_rim'):
                frd = get_comp_data(df_r_lib, b.get('f_rim'))
                fhd = get_comp_data(df_h_lib, b.get('f_hub'))
                rim_w, hub_w = float(frd.get('weight', 0)), float(fhd.get('weight', 0))
                h_count = int(frd.get('holes', 28))
                front_total = rim_w + hub_w + (h_count * (ws_weight + wn_weight))
                total_wheelset_weight += front_total
                st.write(f"**Rim:** {b.get('f_rim')} ({rim_w}g)")
                st.write(f"**Hub:** {b.get('f_hub')} ({hub_w}g)")
                st.write(f"**Serial:** `{b.get('f_rim_serial', 'N/A')}`")
                st.info(f"📏 L: {b.get('f_l')}mm / R: {b.get('f_r')}mm")
            else: st.write("N/A")
                
        with col2:
            st.write("#### 🔘 Rear Wheel")
            if b.get('r_rim'):
                rrd = get_comp_data(df_r_lib, b.get('r_rim'))
                rhd = get_comp_data(df_h_lib, b.get('r_hub'))
                rim_w, hub_w = float(rrd.get('weight', 0)), float(rhd.get('weight', 0))
                h_count = int(rrd.get('holes', 28))
                rear_total = rim_w + hub_w + (h_count * (ws_weight + wn_weight))
                total_wheelset_weight += rear_total
                st.write(f"**Rim:** {b.get('r_rim')} ({rim_w}g)")
                st.write(f"**Hub:** {b.get('r_hub')} ({hub_w}g)")
                st.write(f"**Serial:** `{b.get('r_rim_serial', 'N/A')}`")
                st.success(f"📏 L: {b.get('r_l')}mm / R: {b.get('r_r')}mm")
            else: st.write("N/A")

        st.divider()
        st.metric("Estimated Total Wheelset Weight", f"{int(total_wheelset_weight)}g")
    else: st.info("No builds available.")

# --- TAB 5: LIBRARY ---
with tabs[4]:
    choice = st.radio("View Library:", ["rims", "hubs", "spokes", "nipples"], horizontal=True)
    df_lib = fetch_data(choice, "id")
    if not df_lib.empty:
        view_df = df_lib.drop(columns=['id', 'label'], errors='ignore')
        st.dataframe(view_df, use_container_width=True)
