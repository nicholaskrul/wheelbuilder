import streamlit as st
import pandas as pd
import time
from datetime import datetime
from pyairtable import Api

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Wheelbuilder Lab v18.9", layout="wide", page_icon="🚲")

# --- 2. AIRTABLE CONNECTION ---
try:
    API_KEY = st.secrets["airtable"]["api_key"]
    BASE_ID = st.secrets["airtable"]["base_id"]
    api = Api(API_KEY)
    base = api.base(BASE_ID)
except Exception:
    st.error("❌ Airtable Connection Error: Check your Streamlit Secrets.")
    st.stop()

# --- 3. THE OPTIMIZED DATA ENGINE ---
@st.cache_data(ttl=3600, show_spinner="Fetching Workshop Data...") # 1-hour TTL
def fetch_master_bundle():
    """
    Fetches all tables once. We only clear this manually 
    or when the 1-hour timer expires.
    """
    tables = {"builds": "customer", "rims": "rim", "hubs": "hub", 
              "spokes": "spoke", "nipples": "nipple", "spoke_db": "combo_id"}
    bundle = {}
    for table_name, label_col in tables.items():
        try:
            records = base.table(table_name).all()
            if not records:
                bundle[table_name] = pd.DataFrame()
                continue
            data = []
            for rec in records:
                fields = rec['fields']
                fields['id'] = rec['id']
                if label_col in fields: fields['label'] = str(fields[label_col]).strip()
                data.append(fields)
            df = pd.DataFrame(data)
            for col in df.columns:
                df[col] = df[col].apply(lambda x: x[0] if isinstance(x, list) else x)
            bundle[table_name] = df
            time.sleep(0.2) # Rate-limit safety
        except Exception:
            bundle[table_name] = pd.DataFrame()
    return bundle

# --- 4. SESSION STATE INITIALIZATION ---
if 'data' not in st.session_state:
    st.session_state.data = fetch_master_bundle()

def refresh_api():
    """Manual trigger to bypass the cache."""
    st.cache_data.clear()
    st.session_state.data = fetch_master_bundle()

def update_local_record(table_name, record_id, updates):
    """
    Updates the local session state so the UI reflects 
    changes instantly without a fresh API fetch.
    """
    df = st.session_state.data[table_name]
    if not df.empty and record_id in df['id'].values:
        for key, val in updates.items():
            df.loc[df['id'] == record_id, key] = val
        st.session_state.data[table_name] = df

# --- 5. ANALYTICS HELPERS ---
def get_comp_data(table_key, label):
    df = st.session_state.data.get(table_key, pd.DataFrame())
    if df.empty or not label: return {}
    match = df[df['label'].str.lower() == str(label).lower().strip()]
    return match.iloc[0].to_dict() if not match.empty else {}

# --- 6. MAIN UI ---
st.title("🚲 Wheelbuilder Lab v18.9")
st.caption("Workshop Command Center | API Conservation Mode (v18.9)")

tabs = st.tabs(["🏁 Workshop", "📜 Proven Recipes", "➕ Register Build", "📦 Library"])

# --- TAB 1: WORKSHOP ---
with tabs[0]:
    c_head, c_sync = st.columns([5, 1])
    with c_head: st.subheader("🏁 Workshop Pipeline")
    with c_sync:
        if st.button("🔄 Force Sync", use_container_width=True): refresh_api(); st.rerun()

    df_builds = st.session_state.data["builds"]
    if df_builds.empty:
        st.info("No active builds found.")
    else:
        active = df_builds[df_builds['status'].fillna("Order Received") != "Complete"].sort_values('id', ascending=False)
        archived = df_builds[df_builds['status'] == "Complete"].sort_values('id', ascending=False)

        for _, row in active.iterrows():
            with st.expander(f"🛠️ {row.get('customer')} — {row.get('status')}"):
                c1, c2, c3 = st.columns(3)
                # (Visual layout logic for Front/Rear weights omitted for brevity, same as v18.8)
                
                with c3:
                    cur_stat = row.get('status', 'Order Received')
                    opts = ["Order Received", "Parts Received", "Building", "Complete"]
                    new_stat = st.selectbox("Status", opts, index=opts.index(cur_stat) if cur_stat in opts else 0, key=f"s_{row['id']}")
                    
                    if new_stat != cur_stat:
                        # 1. Update Airtable (The single API call)
                        base.table("builds").update(row['id'], {"status": new_stat})
                        # 2. Update Local State (Zero API calls)
                        update_local_record("builds", row['id'], {"status": new_stat})
                        st.toast(f"Status updated to {new_stat}"); st.rerun()

                    with st.popover("📝 Details"):
                        fs = st.text_input("Serial", value=row.get('f_rim_serial', ''), key=f"fs_{row['id']}")
                        if st.button("Save", key=f"b_{row['id']}"):
                            base.table("builds").update(row['id'], {"f_rim_serial": fs})
                            update_local_record("builds", row['id'], {"f_rim_serial": fs})
                            st.toast("Saved!"); st.rerun()

# --- TAB 3: REGISTER ---
with tabs[2]:
    st.header("📝 Register New Build")
    with st.form("reg_v18_9"):
        cust = st.text_input("Customer Name")
        # ... (Form inputs same as v18.8)
        if st.form_submit_button("🚀 Register Build"):
            if cust:
                payload = {"customer": cust, "date": datetime.now().strftime("%Y-%m-%d"), "status": "Order Received"}
                # Create record in Airtable
                new_rec = base.table("builds").create(payload)
                # Instead of clearing cache, we just trigger a refresh once
                refresh_api(); st.success("Build Registered!"); st.rerun()

# --- TAB 4: LIBRARY ---
with tabs[3]:
    st.header("📦 Library Management")
    # Library logic remains similar, but use refresh_api() sparingly.
