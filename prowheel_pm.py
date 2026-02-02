import streamlit as st
import pandas as pd
import math
from datetime import datetime
from pyairtable import Api

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Wheelbuilder Lab v14.2", layout="wide", page_icon="🚲")

# --- 2. AIRTABLE CONNECTION ---
try:
    AIRTABLE_API_KEY = st.secrets["airtable"]["api_key"]
    AIRTABLE_BASE_ID = st.secrets["airtable"]["base_id"]
    api = Api(AIRTABLE_API_KEY)
    base = api.base(AIRTABLE_BASE_ID)
except Exception as e:
    st.error("❌ Airtable Secrets Error: Ensure [airtable] api_key and base_id are in Streamlit Secrets.")
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
                # Normalizing labels for a clean character-for-character handshake
                fields['label'] = str(fields[label_col]).strip()
            data.append(fields)
        df = pd.DataFrame(data)
        # Handle linked record lists often returned by Airtable
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
    """Precision math for J-Bend and Straightpull based on v10.4 logic."""
    if not erd or not fd or not holes: return 0.0
    r_rim, r_hub = float(erd) / 2, float(fd) / 2
    angle_rad = math.radians((float(crosses) * 720.0) / float(holes))
    if not is_sp:
        # Standard J-Bend Geometry (Law of Cosines)
        l_sq = (r_rim**2) + (r_hub**2) + (float(os)**2) - (2 * r_rim * r_hub * math.cos(angle_rad))
        return round(math.sqrt(max(0, l_sq)) - 1.2, 1) # 1.2mm deduction for stretch
    else:
        # Straightpull Geometry
        base_l_sq = (r_rim**2) + (r_hub**2) - (2 * r_rim * r_hub * math.cos(angle_rad))
        length = math.sqrt(max(0, base_l_sq + float(os)**2)) + float(sp_off)
        return round(length, 1)

# --- 4. SESSION STATE FOR STAGING ---
if 'build_stage' not in st.session_state:
    st.session_state.build_stage = {
        'f_rim': '', 'f_hub': '', 'f_l': 0.0, 'f_r': 0.0,
        'r_rim': '', 'r_hub': '', 'r_l': 0.0, 'r_r': 0.0
    }

# --- 5. MAIN UI ---
st.title("🚲 Wheelbuilder Lab v14.2")
st.caption(f"Full Workshop Cockpit | Connected to Base: {AIRTABLE_BASE_ID}")

tabs = st.tabs(["📊 Dashboard", "🧮 Precision Calc", "➕ Register Build", "📄 Spec Sheet", "📦 Library"])

# --- TAB 1: DASHBOARD ---
with tabs[0]:
    st.subheader("🏁 Workshop Pipeline")
    df_builds = fetch_data("builds", "customer")
    if not df_builds.empty:
        search = st.text_input("🔍 Search Customer")
        f_df = df_builds[df_builds['label'].str.contains(search, case=False)] if search else df_builds
        
        # Display builds sorted by ID (most recent first)
        for _, row in f_df.sort_values('id', ascending=False).iterrows():
            with st.expander(f"🛠️ {row.get('customer')} — {row.get('status')} ({row.get('date', 'No Date')})"):
                c1, c2, c3 = st.columns(3)
                
                with c1:
                    st.markdown("**🔘 FRONT WHEEL**")
                    if row.get('f_rim'):
                        st.write(f"**Rim:** {row.get('f_rim')}")
                        st.write(f"**Hub:** {row.get('f_hub', 'N/A')}")
                        st.write(f"**SN:** `{row.get('f_rim_serial', 'PENDING')}`")
                        st.info(f"📏 L: {row.get('f_l', 0)} / R: {row.get('f_r', 0)} mm")
                    else: st.write("*N/A*")
                
                with c2:
                    st.markdown("**🔘 REAR WHEEL**")
                    if row.get('r_rim'):
                        st.write(f"**Rim:** {row.get('r_rim')}")
                        st.write(f"**Hub:** {row.get('r_hub', 'N/A')}")
                        st.write(f"**SN:** `{row.get('r_rim_serial', 'PENDING')}`")
                        st.success(f"📏 L: {row.get('r_l', 0)} / R: {row.get('r_r', 0)} mm")
                    else: st.write("*N/A*")
                
                with c3:
                    st.markdown("**📦 PARTS**")
                    st.write(f"**Spoke:** {row.get('spoke')}")
                    st.write(f"**Nipple:** {row.get('nipple')}")
                    
                    st.divider()
                    current_status = row.get('status', 'Order Received')
                    status_options = ["Order Received", "Parts Received", "Building", "Complete"]
                    new_stat = st.selectbox("Update Status", status_options, key=f"st_{row['id']}", 
                                            index=status_options.index(current_status) if current_status in status_options else 0)
                    
                    if new_stat != current_status:
                        base.table("builds").update(row['id'], {"status": new_stat})
                        st.rerun()

                    if current_status in ["Parts Received", "Building", "Complete"]:
                        with st.popover("📝 Edit Rim Serials"):
                            f_ser = st.text_input("Front Serial", value=row.get('f_rim_serial', ''), key=f"fs_{row['id']}")
                            r_ser = st.text_input("Rear Serial", value=row.get('r_rim_serial', ''), key=f"rs_{row['id']}")
                            if st.button("Save", key=f"btn_{row['id']}"):
                                base.table("builds").update(row['id'], {"f_rim_serial": f_ser, "r_rim_serial": r_ser})
                                st.rerun()
                
                if row.get('notes'): st.caption(f"**Notes:** {row['notes']}")
    else: st.info("Pipeline empty.")

# --- TAB 2: PRECISION CALC ---
with tabs[1]:
    st.header("🧮 Spoke Length Engine")
    df_rims, df_hubs = fetch_data("rims", "rim"), fetch_data("hubs", "hub")
    
    if not df_rims.empty and not df_hubs.empty:
        c_r, c_h = st.columns(2)
        r_sel = c_r.selectbox("Select Rim", df_rims['label'])
        h_sel = c_h.selectbox("Select Hub", df_hubs['label'])
        rd, hd = get_comp_data(df_rims, r_sel), get_comp_data(df_hubs, h_sel)
        
        st.divider()
        col1, col2, col3 = st.columns(3)
        is_sp = col1.toggle("Straightpull?", value=True)
        holes = col2.number_input("Hole Count", value=int(rd.get('holes', 28)))
        cross = col3.selectbox("Crosses", [0,1,2,3,4], index=3)
        
        l_len = calculate_spoke(rd.get('erd',0), hd.get('fd_l',0), hd.get('os_l',0), holes, cross, is_sp, hd.get('sp_off_l',0))
        r_len = calculate_spoke(rd.get('erd',0), hd.get('fd_r',0), hd.get('os_r',0), holes, cross, is_sp, hd.get('sp_off_r',0))
        
        m1, m2 = st.columns(2)
        m1.metric("Left Spoke", f"{l_len} mm")
        m2.metric("Right Spoke", f"{r_len} mm")
        
        target = st.radio("Stage these lengths for:", ["Front Wheel", "Rear Wheel"], horizontal=True)
        if st.button("💾 Stage Component Data"):
            if target == "Front Wheel":
                st.session_state.build_stage.update({'f_rim': r_sel, 'f_hub': h_sel, 'f_l': l_len, 'f_r': r_len})
            else:
                st.session_state.build_stage.update({'r_rim': r_sel, 'r_hub': h_sel, 'r_l': l_len, 'r_r': r_len})
            st.success(f"Staged {target}!")

# --- TAB 3: REGISTER BUILD ---
with tabs[2]:
    st.header("📝 Register New Build")
    df_spk, df_nip = fetch_data("spokes", "spoke"), fetch_data("nipples", "nipple")
    build_type = st.radio("Config:", ["Full Wheelset", "Front Only", "Rear Only"], horizontal=True)

    with st.form("build_reg_v14_2"):
        customer = st.text_input("Customer Name")
        inv_url = st.text_input("Invoice URL")
        payload = {"customer": customer, "date": datetime.now().strftime("%Y-%m-%d"), "status": "Order Received", "invoice_url": inv_url}
        
        cf, cr = st.columns(2)
        if build_type in ["Full Wheelset", "Front Only"]:
            with cf:
                st.subheader("Front Wheel")
                fr, fh = st.text_input("F Rim", value=st.session_state.build_stage['f_rim']), st.text_input("F Hub", value=st.session_state.build_stage['f_hub'])
                fl, frr = st.number_input("F L-Len", value=st.session_state.build_stage['f_l']), st.number_input("F R-Len", value=st.session_state.build_stage['f_r'])
                fs = st.text_input("F Serial")
                payload.update({"f_rim": fr, "f_hub": fh, "f_l": fl, "f_r": frr, "f_rim_serial": fs})
        
        if build_type in ["Full Wheelset", "Rear Only"]:
            with cr:
                st.subheader("Rear Wheel")
                rr, rh = st.text_input("R Rim", value=st.session_state.build_stage['r_rim']), st.text_input("R Hub", value=st.session_state.build_stage['r_hub'])
                rl, rrr = st.number_input("R L-Len", value=st.session_state.build_stage['r_l']), st.number_input("R R-Len", value=st.session_state.build_stage['r_r'])
                rs = st.text_input("R Serial")
                payload.update({"r_rim": rr, "r_hub": rh, "r_l": rl, "r_r": rrr, "r_rim_serial": rs})
        
        sc1, sc2 = st.columns(2)
        spk = sc1.selectbox("Spoke", df_spk['label'] if not df_spk.empty else ["Standard"])
        nip = sc2.selectbox("Nipple", df_nip['label'] if not df_nip.empty else ["Standard"])
        payload.update({"spoke": spk, "nipple": nip, "notes": st.text_area("Notes")})
        
        if st.form_submit_button("🚀 Finalize Build"):
            base.table("builds").create(payload)
            st.session_state.build_stage = {'f_rim': '', 'f_hub': '', 'f_l': 0.0, 'f_r': 0.0, 'r_rim': '', 'r_hub': '', 'r_l': 0.0, 'r_r': 0.0}
            st.cache_data.clear(); st.success("Registered!"); st.rerun()

# --- TAB 4: SPEC SHEET ---
with tabs[3]:
    st.header("📄 Technical Spec Sheet")
    df_builds = fetch_data("builds", "customer")
    if not df_builds.empty:
        sel = st.selectbox("Select Build", df_builds['label'].unique())
        b = df_builds[df_builds['label'] == sel].iloc[0]
        df_rl, df_hl, df_sl, df_nl = fetch_data("rims", "rim"), fetch_data("hubs", "hub"), fetch_data("spokes", "spoke"), fetch_data("nipples", "nipple")
        
        st.divider()
        ch, ci = st.columns([3, 1])
        ch.markdown(f"### technical Build Proof: **{sel}**")
        if b.get('invoice_url'): ci.link_button("📄 Open Invoice", b['invoice_url'], use_container_width=True)
        
        tw, sw, nw = 0.0, float(get_comp_data(df_sl, b.get('spoke')).get('weight',0)), float(get_comp_data(df_nl, b.get('nipple')).get('weight',0))
        cs1, cs2 = st.columns(2)
        with cs1:
            if b.get('f_rim'):
                frd, fhd = get_comp_data(df_rl, b.get('f_rim')), get_comp_data(df_hl, b.get('f_hub'))
                rw, hw, hc = float(frd.get('weight',0)), float(fhd.get('weight',0)), int(frd.get('holes',28))
                f_t = rw + hw + (hc * (sw + nw))
                tw += f_t
                st.write(f"#### 🔘 Front ({int(f_t)}g)")
                st.write(f"**Rim:** {b.get('f_rim')} | **SN:** `{b.get('f_rim_serial', 'N/A')}`")
                st.info(f"📏 L: {b.get('f_l')}mm / R: {b.get('f_r')}mm")
        with cs2:
            if b.get('r_rim'):
                rrd, rhd = get_comp_data(df_rl, b.get('r_rim')), get_comp_data(df_hl, b.get('r_hub'))
                rw, hw, hc = float(rrd.get('weight',0)), float(rhd.get('weight',0)), int(rrd.get('holes',28))
                r_t = rw + hw + (hc * (sw + nw))
                tw += r_t
                st.write(f"#### 🔘 Rear ({int(r_t)}g)")
                st.write(f"**Rim:** {b.get('r_rim')} | **SN:** `{b.get('r_rim_serial', 'N/A')}`")
                st.success(f"📏 L: {b.get('r_l')}mm / R: {b.get('r_r')}mm")
        st.divider(); st.metric("Total Wheelset Weight", f"{int(tw)}g")

# --- TAB 5: LIBRARY ---
with tabs[4]:
    lib = st.radio("View Library:", ["rims", "hubs", "spokes", "nipples"], horizontal=True)
    df_l = fetch_data(lib, "id")
    if not df_l.empty: st.dataframe(df_l.drop(columns=['id', 'label'], errors='ignore'), use_container_width=True)
