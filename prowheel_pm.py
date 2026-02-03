import streamlit as st
import pandas as pd
import math
from datetime import datetime
from pyairtable import Api

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Wheelbuilder Lab v15.6", layout="wide", page_icon="🚲")

# --- 2. AIRTABLE CONNECTION ---
try:
    AIRTABLE_API_KEY = st.secrets["airtable"]["api_key"]
    AIRTABLE_BASE_ID = st.secrets["airtable"]["base_id"]
    api = Api(AIRTABLE_API_KEY)
    base = api.base(AIRTABLE_BASE_ID)
except Exception as e:
    st.error("❌ Airtable Secrets Error: Ensure secrets are configured.")
    st.stop()

@st.cache_data(ttl=300)
def fetch_data(table_name, label_col):
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
st.title("🚲 Wheelbuilder Lab v15.6")
st.caption("Live Workshop Management | Synchronized Weight Anatomy")

tabs = st.tabs(["🏁 Workshop", "🧮 Precision Calc", "➕ Register Build", "📦 Library"])

# --- TAB 1: UNIFIED WORKSHOP ---
with tabs[0]:
    st.subheader("🏁 Workshop Pipeline")
    
    df_builds = fetch_data("builds", "customer")
    df_rims = fetch_data("rims", "rim")
    df_hubs = fetch_data("hubs", "hub")
    df_spokes = fetch_data("spokes", "spoke")
    df_nipples = fetch_data("nipples", "nipple")
    
    if not df_builds.empty:
        search = st.text_input("🔍 Search Customer", key="main_search")
        f_df = df_builds[df_builds['label'].str.contains(search, case=False, na=False)] if search else df_builds
        
        for _, row in f_df.sort_values('id', ascending=False).iterrows():
            # --- WEIGHT ENGINE ---
            s_data = get_comp_data(df_spokes, row.get('spoke'))
            n_data = get_comp_data(df_nipples, row.get('nipple'))
            sw = float(s_data.get('weight', 0))
            nw = float(n_data.get('weight', 0))
            
            # Front Calc
            f_calc = {"total": 0.0, "exists": False, "rim_w": 0.0, "hub_w": 0.0, "spoke_total": 0.0, "nipple_total": 0.0}
            if row.get('f_rim') and str(row.get('f_rim')).lower() not in ['nan', '', 'none']:
                fr_d = get_comp_data(df_rims, row.get('f_rim'))
                fh_d = get_comp_data(df_hubs, row.get('f_hub'))
                if fr_d:
                    f_calc["exists"] = True
                    f_calc["rim_w"] = float(fr_d.get('weight', 0))
                    f_calc["hub_w"] = float(fh_d.get('weight', 0))
                    f_holes = int(fr_d.get('holes', 0))
                    f_calc["spoke_total"] = f_holes * sw
                    f_calc["nipple_total"] = f_holes * nw
                    f_calc["total"] = f_calc["rim_w"] + f_calc["hub_w"] + f_calc["spoke_total"] + f_calc["nipple_total"]

            # Rear Calc
            r_calc = {"total": 0.0, "exists": False, "rim_w": 0.0, "hub_w": 0.0, "spoke_total": 0.0, "nipple_total": 0.0}
            if row.get('r_rim') and str(row.get('r_rim')).lower() not in ['nan', '', 'none']:
                rr_d = get_comp_data(df_rims, row.get('r_rim'))
                rh_d = get_comp_data(df_hubs, row.get('r_hub'))
                if rr_d:
                    r_calc["exists"] = True
                    r_calc["rim_w"] = float(rr_d.get('weight', 0))
                    r_calc["hub_w"] = float(rh_d.get('weight', 0))
                    r_holes = int(rr_d.get('holes', 0))
                    r_calc["spoke_total"] = r_holes * sw
                    r_calc["nipple_total"] = r_holes * nw
                    r_calc["total"] = r_calc["rim_w"] + r_calc["hub_w"] + r_calc["spoke_total"] + r_calc["nipple_total"]

            with st.expander(f"🛠️ {row.get('customer')} — {row.get('status')} ({row.get('date', '---')})"):
                current_status = row.get('status', 'Order Received')
                new_stat = st.selectbox("Update Status", ["Order Received", "Parts Received", "Building", "Complete"], 
                                        key=f"st_{row['id']}", 
                                        index=["Order Received", "Parts Received", "Building", "Complete"].index(current_status))
                if new_stat != current_status:
                    base.table("builds").update(row['id'], {"status": new_stat})
                    st.cache_data.clear()
                    st.rerun()
                
                st.divider()
                c1, c2, c3 = st.columns(3)
                
                with c1:
                    st.markdown("**🔘 FRONT WHEEL**")
                    if f_calc["exists"]:
                        st.write(f"**Rim:** {row.get('f_rim')}")
                        st.write(f"**Hub:** {row.get('f_hub')}")
                        st.write(f"**Serial:** `{row.get('f_rim_serial', 'NONE')}`")
                        st.info(f"📏 **Lengths**\nL: {row.get('f_l')}mm / R: {row.get('f_r')}mm")
                        with st.container(border=True):
                            st.caption("Weight Breakdown")
                            st.write(f"Rim: {int(f_calc['rim_w'])}g | Hub: {int(f_calc['hub_w'])}g")
                            st.write(f"Spokes: {int(f_calc['spoke_total'])}g | Nipples: {int(f_calc['nipple_total'])}g")
                            st.metric("Front Total", f"{int(f_calc['total'])}g")
                    else: st.write("N/A")

                with c2:
                    st.markdown("**🔘 REAR WHEEL**")
                    if r_calc["exists"]:
                        st.write(f"**Rim:** {row.get('r_rim')}")
                        st.write(f"**Hub:** {row.get('r_hub')}")
                        st.write(f"**Serial:** `{row.get('r_rim_serial', 'NONE')}`")
                        st.info(f"📏 **Lengths**\nL: {row.get('r_l')}mm / R: {row.get('r_r')}mm")
                        with st.container(border=True):
                            st.caption("Weight Breakdown")
                            st.write(f"Rim: {int(r_calc['rim_w'])}g | Hub: {int(r_calc['hub_w'])}g")
                            st.write(f"Spokes: {int(r_calc['spoke_total'])}g | Nipples: {int(r_calc['nipple_total'])}g")
                            st.metric("Rear Total", f"{int(r_calc['total'])}g")
                    else: st.write("N/A")

                with c3:
                    st.markdown("**⚙️ LOGISTICS**")
                    st.write(f"**Spoke:** {row.get('spoke', 'N/A')}")
                    st.write(f"**Nipple:** {row.get('nipple', 'N/A')}")
                    st.divider()
                    st.metric("📦 WHEELSET WEIGHT", f"{int(f_calc['total'] + r_calc['total'])}g")
                    st.divider()
                    if row.get('invoice_url'):
                        st.link_button("📄 Invoice", row['invoice_url'], use_container_width=True)

                    with st.popover("📝 Edit Build Details"):
                        st.markdown("### Update Build Records")
                        fs = st.text_input("Front Serial", value=row.get('f_rim_serial', ''), key=f"fs_{row['id']}")
                        rs = st.text_input("Rear Serial", value=row.get('r_rim_serial', ''), key=f"rs_{row['id']}")
                        new_notes = st.text_area("Build Journal / Notes", value=row.get('notes', ''), key=f"nt_{row['id']}")
                        
                        if st.button("Update Record", key=f"btn_{row['id']}", use_container_width=True):
                            base.table("builds").update(row['id'], {
                                "f_rim_serial": fs, 
                                "r_rim_serial": rs,
                                "notes": new_notes
                            })
                            st.rerun()
                    
                    if row.get('notes'):
                        st.markdown("**📋 Build Journal:**")
                        st.caption(row.get('notes'))

    else: st.info("Pipeline empty.")

# --- TAB 2, 3, 4 remain identical to v15.4 for stability ---
# [Truncated for brevity - no changes made to Calc, Register, or Library logic]
