import streamlit as st
import pandas as pd
import time
import secrets
import string
import requests
from datetime import datetime
from pyairtable import Api

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Wheelbuilder Lab v18.12", layout="wide", page_icon="🚲")

# --- 2. AIRTABLE CONNECTION ---
try:
    API_KEY = st.secrets["airtable"]["api_key"]
    BASE_ID = st.secrets["airtable"]["base_id"]
    api = Api(API_KEY)
    base = api.base(BASE_ID)
except Exception:
    st.error("❌ Airtable Connection Error: Check your Streamlit Secrets.")
    st.stop()

# --- 3. THE OPTIMIZED DATA ENGINE (API SAVER) ---
@st.cache_data(ttl=3600, show_spinner="Fetching Workshop Data...")
def fetch_master_bundle():
    tables = {
        "builds": "customer", 
        "rims": "rim", 
        "hubs": "hub", 
        "spokes": "spoke", 
        "nipples": "nipple", 
        "spoke_db": "combo_id"
    }
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
                if label_col in fields: 
                    fields['label'] = str(fields[label_col]).strip()
                data.append(fields)
            df = pd.DataFrame(data)
            for col in df.columns:
                df[col] = df[col].apply(lambda x: x[0] if isinstance(x, list) else x)
            bundle[table_name] = df
            time.sleep(0.2)
        except Exception:
            bundle[table_name] = pd.DataFrame()
    return bundle

# --- 4. STATE & SYNC MANAGEMENT ---
if 'data' not in st.session_state:
    st.session_state.data = fetch_master_bundle()

def refresh_api():
    st.cache_data.clear()
    st.session_state.data = fetch_master_bundle()

def update_local_record(table_name, record_id, updates):
    df = st.session_state.data[table_name]
    if not df.empty and record_id in df['id'].values:
        for key, val in updates.items():
            df.loc[df['id'] == record_id, key] = val
        st.session_state.data[table_name] = df

# --- 5. AUTOMATION & ANALYTICS HELPERS ---
def get_comp_data(table_key, label):
    if not label or label == "None": return {}
    df = st.session_state.data.get(table_key, pd.DataFrame())
    if df.empty: return {}
    match = df[df['label'].str.lower() == str(label).lower().strip()]
    return match.iloc[0].to_dict() if not match.empty else {}

def create_protected_wp_page(row, f_res, r_res):
    """
    Production Version: Generates a premium, password-protected build page 
    on WordPress matching the exact visual identity of wheelbuilder.co.za
    """
    try:
        if "wordpress" not in st.secrets:
            st.error("❌ 'wordpress' section is missing from your Streamlit secrets!")
            return None, None
            
        wp_secrets = st.secrets["wordpress"]
        gateway_url = f"{wp_secrets['site_url'].rstrip('/')}/wb-gate.php"
        
        # Generate clean customer access password
        alphabet = string.ascii_uppercase + string.digits
        password = "WS-" + "".join(secrets.choice(alphabet) for _ in range(6))
        
        cust_name = row.get('customer', 'Valued Client')
        spoke_model = row.get('spoke', 'N/A')
        nipple_model = row.get('nipple', 'N/A')
        tracking_link = str(row.get('tracking_link', '')).strip()
        invoice_url = str(row.get('invoice_url', '')).strip()
        
        # --- PREVENT CRASHES: Safe parsing of float spoke lengths ---
        def format_len(val):
            try:
                return f"{float(val):.1f}" if val and float(val) > 0 else "N/A"
            except (ValueError, TypeError):
                return "N/A"

        # --- PREMIUM HTML MARKUP TUNED TO WHEELBUILDER.CO.ZA BRANDING ---
        html_content = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 680px; margin: 0 auto; padding: 30px 15px; color: #222; background-color: #ffffff; line-height: 1.7;">
            
            <h1 style="font-size: 26px; font-weight: 700; color: #111; margin-bottom: 20px; letter-spacing: -0.5px; text-transform: uppercase; border-bottom: 3px solid #111; padding-bottom: 12px; margin-top: 0;">
                Your custom wheelset build sheet
            </h1>
            
            <p style="font-size: 15px; margin-bottom: 18px; color: #333;">
                Thank you for choosing Wheelbuilder for your custom wheel build! Your wheelset is complete and ready for the road. Below you will find the verified specs, weights, invoice and logistics tracking information.
            </p>
            
            <div style="background-color: #f8f9fa; border-left: 4px solid #111; padding: 16px; margin-bottom: 30px; border-radius: 0 4px 4px 0;">
                <p style="font-size: 14.5px; margin: 0; font-style: italic; color: #444; font-weight: 500;">
                    Your wheels come with a lifetime warranty on the workmanship and spokes. If you ever need any support or advice, please get in touch directly.
                </p>
            </div>
        """
        
        # Front Wheel Table Block
        if f_res["exists"]:
            html_content += f"""
            <div style="border: 1px solid #eaeaea; border-radius: 6px; padding: 20px; margin-bottom: 24px; background-color: #ffffff; box-shadow: 0 2px 4px rgba(0,0,0,0.01);">
                <h2 style="font-size: 16px; font-weight: 700; color: #111; margin-top: 0; margin-bottom: 14px; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #eaeaea; padding-bottom: 8px;">
                    🔘 Front Wheel Configuration
                </h2>
                <table style="width: 100%; border-collapse: collapse; font-size: 14.5px;">
                    <tr><td style="padding: 6px 0; color: #666; width: 35%;">Rim</td><td style="padding: 6px 0; font-weight: 600; color: #111;">{row.get('f_rim')}</td></tr>
                    <tr><td style="padding: 6px 0; color: #666;">Hub</td><td style="padding: 6px 0; font-weight: 600; color: #111;">{row.get('f_hub')}</td></tr>
                    <tr><td style="padding: 6px 0; color: #666;">Spokes</td><td style="padding: 6px 0; font-weight: 600; color: #111;">{spoke_model} <span style="color:#666; font-weight: normal; font-size:13.5px; margin-left: 6px;">(L: {format_len(row.get('f_l'))}mm / R: {format_len(row.get('f_r'))}mm)</span></td></tr>
                    <tr><td style="padding: 6px 0; color: #666;">Nipples</td><td style="padding: 6px 0; font-weight: 600; color: #111;">{nipple_model}</td></tr>
                    <tr><td style="padding: 10px 0 0 0; color: #111; font-weight: 700; border-top: 1px dashed #eaeaea; margin-top: 6px;">Wheel Weight</td><td style="padding: 10px 0 0 0; font-weight: 700; color: #111; border-top: 1px dashed #eaeaea; font-size: 15px;">{int(f_res['total'])}g</td></tr>
                </table>
            </div>
            """
            
        # Rear Wheel Table Block
        if r_res["exists"]:
            html_content += f"""
            <div style="border: 1px solid #eaeaea; border-radius: 6px; padding: 20px; margin-bottom: 24px; background-color: #ffffff; box-shadow: 0 2px 4px rgba(0,0,0,0.01);">
                <h2 style="font-size: 16px; font-weight: 700; color: #111; margin-top: 0; margin-bottom: 14px; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #eaeaea; padding-bottom: 8px;">
                    🔘 Rear Wheel Configuration
                </h2>
                <table style="width: 100%; border-collapse: collapse; font-size: 14.5px;">
                    <tr><td style="padding: 6px 0; color: #666; width: 35%;">Rim</td><td style="padding: 6px 0; font-weight: 600; color: #111;">{row.get('r_rim')}</td></tr>
                    <tr><td style="padding: 6px 0; color: #666;">Hub</td><td style="padding: 6px 0; font-weight: 600; color: #111;">{row.get('r_hub')}</td></tr>
                    <tr><td style="padding: 6px 0; color: #666;">Spokes</td><td style="padding: 6px 0; font-weight: 600; color: #111;">{spoke_model} <span style="color:#666; font-weight: normal; font-size:13.5px; margin-left: 6px;">(L: {format_len(row.get('r_l'))}mm / R: {format_len(row.get('r_r'))}mm)</span></td></tr>
                    <tr><td style="padding: 6px 0; color: #666;">Nipples</td><td style="padding: 6px 0; font-weight: 600; color: #111;">{nipple_model}</td></tr>
                    <tr><td style="padding: 10px 0 0 0; color: #111; font-weight: 700; border-top: 1px dashed #eaeaea; margin-top: 6px;">Wheel Weight</td><td style="padding: 10px 0 0 0; font-weight: 700; color: #111; border-top: 1px dashed #eaeaea; font-size: 15px;">{int(r_res['total'])}g</td></tr>
                </table>
            </div>
            """
            
        # Total Summary Weight Box
        html_content += f"""
        <div style="background-color: #111111; color: #ffffff; padding: 18px 20px; border-radius: 6px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: center;">
            <span style="font-size: 14px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: #999;">Wheelset Weight Total</span>
            <span style="font-size: 22px; font-weight: 700; color: #ffffff;">{int(f_res['total'] + r_res['total'])}g</span>
        </div>
        """
        
        # Logistics Actions Buttons
        html_content += "<div style='margin-bottom: 35px; margin-top: 10px;'>"
        if invoice_url and invoice_url.lower() not in ["none", "nan"]:
            html_content += f'<a href="{invoice_url}" target="_blank" style="display: inline-block; padding: 11px 18px; margin-right: 12px; margin-bottom: 10px; border: 2px solid #111; color: #111; background-color: #fff; text-decoration: none; border-radius: 4px; font-weight: 700; font-size: 13.5px; text-transform: uppercase; letter-spacing: 0.5px;">📄 View Invoice</a>'
        if tracking_link and tracking_link.lower() not in ["none", "nan"]:
            html_content += f'<a href="{tracking_link}" target="_blank" style="display: inline-block; padding: 11px 18px; margin-bottom: 10px; background-color: #111; color: #fff; text-decoration: none; border-radius: 4px; font-weight: 700; font-size: 13.5px; text-transform: uppercase; letter-spacing: 0.5px;">🚚 Track Shipment</a>'
        html_content += "</div>"
        
        # Static Clean Content Gallery Placeholder
        html_content += """
            <div style="border-top: 1px solid #eaeaea; padding-top: 25px; margin-top: 25px;">
                <h3 style="font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px; color: #111;">📸 Build Gallery</h3>
                <p style="color: #666; font-style: italic; font-size: 13.5px; margin: 0;">High-resolution configuration imagery layout and tension profiles will update here shortly.</p>
            </div>
        </div>
        """
        
        payload = {"title": f"Build Sheet — {cust_name}", "password": password, "content": html_content}
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "X-WB-Token": wp_secrets.get("gateway_token", ""),
            "Content-Type": "application/json"
        }
        
        response = requests.post(gateway_url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json().get("link"), password
        else:
            return None, None
            
    except Exception:
        return None, None

# --- 6. MAIN UI ---
st.title("🚲 Wheelbuilder Lab v18.12")
st.caption("Workshop Command Center | Cloudflare Integration Cleaned")

tabs = st.tabs(["🏁 Workshop", "📜 Proven Recipes", "➕ Register Build", "📦 Library"])

# --- TAB 1: WORKSHOP (PIPELINE) ---
with tabs[0]:
    c_head, c_sync = st.columns([5, 1])
    with c_head: st.subheader("🏁 Workshop Pipeline")
    with c_sync:
        if st.button("🔄 Force Sync", use_container_width=True):
            refresh_api(); st.rerun()

    df_builds = st.session_state.data["builds"]
    
    if df_builds.empty:
        st.info("No active builds found.")
    else:
        active_mask = df_builds['status'].fillna("Order Received") != "Complete"
        
        # Case-insensitive alphabetical sorting by customer first name
        active_builds = df_builds[active_mask].sort_values(by='customer', key=lambda col: col.str.lower())
        completed_builds = df_builds[~active_mask].sort_values(by='customer', key=lambda col: col.str.lower())

        st.write(f"### 🛠️ Active Builds ({len(active_builds)})")
        for _, row in active_builds.iterrows():
            spk_data = get_comp_data("spokes", row.get('spoke'))
            nip_data = get_comp_data("nipples", row.get('nipple'))
            u_spk = float(spk_data.get('weight', 0))
            u_nip = float(nip_data.get('weight', 0))

            f_res = {"total": 0.0, "exists": False}
            if row.get('f_rim') and row.get('f_rim') != "None":
                frd = get_comp_data("rims", row.get('f_rim'))
                fhd = get_comp_data("hubs", row.get('f_hub'))
                h = int(frd.get('holes', 0))
                f_res.update({"exists": True, "rim_w": float(frd.get('weight', 0)), "hub_w": float(fhd.get('weight', 0))})
                f_res["total"] = f_res["rim_w"] + f_res["hub_w"] + (h * (u_spk + u_nip))

            r_res = {"total": 0.0, "exists": False}
            if row.get('r_rim') and row.get('r_rim') != "None":
                rrd = get_comp_data("rims", row.get('r_rim'))
                rhd = get_comp_data("hubs", row.get('r_hub'))
                h = int(rrd.get('holes', 0))
                r_res.update({"exists": True, "rim_w": float(rrd.get('weight', 0)), "hub_w": float(rhd.get('weight', 0))})
                r_res["total"] = r_res["rim_w"] + r_res["hub_w"] + (h * (u_spk + u_nip))

            addr_val = row.get('delivery_address')
            track_val = row.get('tracking_link')

            has_addr = isinstance(addr_val, str) and bool(addr_val.strip()) and addr_val.lower() not in ["none", "nan"]
            has_tracking = isinstance(track_val, str) and bool(track_val.strip()) and track_val.lower() not in ["none", "nan"]
            addr_flag = " 📮" if (has_addr or has_tracking) else ""

            with st.expander(f"🛠️ {row.get('customer')} — {row.get('status')}{addr_flag}"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown("**🔘 FRONT**")
                    if f_res["exists"]:
                        st.markdown(f"**{row.get('f_rim')}**")
                        st.caption(f"{row.get('f_hub')}")
                        st.info(f"📏 L: {row.get('f_l')} / R: {row.get('f_r')} mm")
                        st.metric("Weight", f"{int(f_res['total'])}g")
                    else:
                        st.write("---")
                with c2:
                    st.markdown("**🔘 REAR**")
                    if r_res["exists"]:
                        st.markdown(f"**{row.get('r_rim')}**")
                        st.caption(f"{row.get('r_hub')}")
                        st.success(f"📏 L: {row.get('r_l')} / R: {row.get('r_r')} mm")
                        st.metric("Weight", f"{int(r_res['total'])}g")
                    else:
                        st.write("---")
                with c3:
                    if f_res["exists"] or r_res["exists"]:
                        st.metric("📦 SET", f"{int(f_res['total'] + r_res['total'])}g")
                    
                    cur = row.get('status', 'Order Received')
                    opts = ["Order Received", "Parts Received", "Building", "Complete"]
                    new_s = st.selectbox("Status", opts, index=opts.index(cur) if cur in opts else 0, key=f"s_{row['id']}")
                    
                    if new_s != cur:
                        if new_s == "Complete" and not row.get('wp_page_url'):
                            with st.spinner(f"Creating protected build page for {row.get('customer')} on WordPress..."):
                                wp_link, wp_pass = create_protected_wp_page(row, f_res, r_res)
                                if wp_link:
                                    updates = {"status": new_s, "wp_page_url": wp_link, "wp_page_password": wp_pass}
                                    base.table("builds").update(row['id'], updates)
                                    update_local_record("builds", row['id'], updates)
                                    st.toast("🎉 WP Protected Page Created successfully!"); st.rerun()
                                else:
                                    st.error("Failed to write to WordPress gateway script. Check tokens.")
                        else:
                            base.table("builds").update(row['id'], {"status": new_s})
                            update_local_record("builds", row['id'], {"status": new_s})
                            st.toast(f"Status changed to {new_s}"); st.rerun()
                    
                    c_btn1, c_btn2, c_btn3 = st.columns(3)
                    with c_btn1:
                        with st.popover("📝 Details"):
                            fs = st.text_input("Front Serial", value=row.get('f_rim_serial', ''), key=f"fs_{row['id']}")
                            rs = st.text_input("Rear Serial", value=row.get('r_rim_serial', ''), key=f"rs_{row['id']}")
                            nt = st.text_area("Notes", value=row.get('notes', ''), key=f"nt_{row['id']}")
                            if st.button("Save Changes", key=f"btn_{row['id']}", use_container_width=True):
                                base.table("builds").update(row['id'], {"f_rim_serial": fs, "r_rim_serial": rs, "notes": nt})
                                update_local_record("builds", row['id'], {"f_rim_serial": fs, "r_rim_serial": rs, "notes": nt})
                                st.toast("Record updated."); st.rerun()

                    with c_btn2:
                        with st.popover(f"📮 Delivery{' ✅' if (has_addr or has_tracking) else ''}"):
                            st.caption("Delivery address for this build")
                            new_addr_input = st.text_area(
                                "Delivery Address",
                                value=str(addr_val).strip() if has_addr else "",
                                placeholder="e.g.\n123 Example Street\nGeorge, Western Cape\n6529\nSouth Africa",
                                height=120,
                                key=f"addr_{row['id']}"
                            )
                            new_track_input = st.text_input(
                                "Courier Tracking Link",
                                value=str(track_val).strip() if has_tracking else "",
                                placeholder="https://...",
                                key=f"track_{row['id']}"
                            )
                            if has_tracking:
                                st.link_button("🔗 Open Tracking Link", str(track_val).strip(), use_container_width=True)
                                
                            if st.button("Save Delivery Info", key=f"addr_btn_{row['id']}", use_container_width=True):
                                base.table("builds").update(row['id'], {"delivery_address": new_addr_input, "tracking_link": new_track_input})
                                update_local_record("builds", row['id'], {"delivery_address": new_addr_input, "tracking_link": new_track_input})
                                st.toast("Delivery info saved."); st.rerun()
                    
                    with c_btn3:
                        with st.popover("🖨️ Parts Sheet"):
                            txt = f"🚲 WHEELBUILDER LAB SPEC SHEET\n"
                            txt += f"====================================\n"
                            txt += f"CUSTOMER  : {row.get('customer')}\n"
                            txt += f"DATE      : {row.get('date', datetime.now().strftime('%Y-%m-%d'))}\n"
                            txt += f"SPOKE     : {row.get('spoke', 'None')}\n"
                            txt += f"NIPPLE    : {row.get('nipple', 'None')}\n"
                            txt += f"====================================\n\n"
                            
                            if row.get('f_rim') and row.get('f_rim') != "None":
                                txt += f"🔘 FRONT WHEEL CONFIGURATION\n"
                                txt += f"  - Rim: {row.get('f_rim')}\n"
                                txt += f"  - Hub: {row.get('f_hub')}\n"
                                txt += f"  - Left Spokes  : {row.get('f_l')} mm\n"
                                txt += f"  - Right Spokes : {row.get('f_r')} mm\n\n"
                                
                            if row.get('r_rim') and row.get('r_rim') != "None":
                                txt += f"🔘 REAR WHEEL CONFIGURATION\n"
                                txt += f"  - Rim: {row.get('r_rim')}\n"
                                txt += f"  - Hub: {row.get('r_hub')}\n"
                                txt += f"  - Left Spokes  : {row.get('r_l')} mm\n"
                                txt += f"  - Right Spokes : {row.get('r_r')} mm\n"

                            if has_addr:
                                txt += f"\n====================================\n"
                                txt += f"📮 DELIVERY ADDRESS\n"
                                txt += f"{str(addr_val).strip()}\n"

                            if has_tracking:
                                if not has_addr:
                                    txt += f"\n====================================\n"
                                txt += f"🔗 TRACKING LINK\n"
                                txt += f"{str(track_val).strip()}\n"

                            txt += f"===================================="
                            
                            st.code(txt, language="text")
                            st.download_button("📥 Download Text File", data=txt, file_name=f"parts_sheet_{str(row.get('customer')).replace(' ', '_')}.txt", mime="text/plain", use_container_width=True)

                if row.get('wp_page_url'):
                    st.markdown("---")
                    st.markdown("### 📱 Client Handover Kit")
                    client_msg = (
                        f"Hi {row.get('customer')}! 👋 Your custom wheelset build is officially finalized and packed! "
                        f"I've created a secure digital build sheet profile for your records.\n\n"
                        f"🔗 Link: {row.get('wp_page_url')}\n"
                        f"🔑 Password: {row.get('wp_page_password')}\n\n"
                        f"This page includes your verified weights, components breakdown sheet, digital invoice copy, and shipping courier tracking records."
                    )
                    st.code(client_msg, language="text")

        st.divider()
        
        # --- COMPLETED ARCHIVE EXPANSER ECOSYSTEM ---
        with st.expander(f"📁 Completed Archive ({len(completed_builds)})"):
            if not completed_builds.empty:
                for _, row in completed_builds.iterrows():
                    with st.expander(f"✅ {row.get('customer')} — {row.get('date')} — {row.get('f_rim')} | {row.get('r_rim')}"):
                        c_arch1, c_arch2 = st.columns([3, 1])
                        
                        with c_arch1:
                            if row.get('wp_page_url'):
                                st.markdown("**📱 Client Handover Kit**")
                                client_msg = (
                                    f"Hi {row.get('customer')}! 👋 Your custom wheelset build is officially finalized and packed! "
                                    f"I've created a secure digital build sheet profile for your records.\n\n"
                                    f"🔗 Link: {row.get('wp_page_url')}\n"
                                    f"🔑 Password: {row.get('wp_page_password')}\n\n"
                                    f"This page includes your verified weights, components breakdown sheet, digital invoice copy, and shipping courier tracking records."
                                )
                                st.code(client_msg, language="text")
                            else:
                                st.info("No WordPress page found for this completed build row.")
                        
                        with c_arch2:
                            st.markdown("**⚙️ Configuration**")
                            if st.button("Re-open Build", key=f"re_{row['id']}", use_container_width=True):
                                base.table("builds").update(row['id'], {"status": "Building", "wp_page_url": "", "wp_page_password": ""})
                                refresh_api(); st.success("Build reassigned to pipeline!"); st.rerun()

# --- TAB 2: PROVEN RECIPES ---
with tabs[1]:
    st.header("📜 Proven Recipe Archive")
    df_rec_tab = st.session_state.data["spoke_db"]
    if not df_rec_tab.empty:
        r_search = st.text_input("🔍 Search Recipes", key="recipe_search")
        if r_search: 
            df_rec_tab = df_rec_tab[df_rec_tab['label'].str.contains(r_search, case=False, na=False)]
        st.dataframe(df_rec_tab[['label', 'len_l', 'len_r', 'build_count']].sort_values('label'), use_container_width=True, hide_index=True)

# --- TAB 3: REGISTER BUILD ---
with tabs[2]:
    st.header("📝 Register New Build")
    st.link_button("⚙️ Open DT Swiss Spoke Calculator", "https://spokes-calculator.dtswiss.com/en/calculator", use_container_width=True)
    st.divider()
    
    rim_opts = ["None"] + sorted(st.session_state.data["rims"]['label'].tolist(), key=str.lower)
    hub_opts = ["None"] + sorted(st.session_state.data["hubs"]['label'].tolist(), key=str.lower)
    spoke_opts = ["None"] + sorted(st.session_state.data["spokes"]['label'].tolist(), key=str.lower)
    nipple_opts = ["None"] + sorted(st.session_state.data["nipples"]['label'].tolist(), key=str.lower)

    with st.form("reg_form_v18_10"):
        cust = st.text_input("Customer Name")
        inv = st.text_input("Invoice URL")
        c_f, c_r = st.columns(2)
        with c_f:
            st.subheader("Front Wheel")
            fr_rim = st.selectbox("Rim", rim_opts, key="reg_fr")
            fr_hub = st.selectbox("Hub", hub_opts, key="reg_fh")
            fl_len, fr_len = st.number_input("Left (mm)", step=0.1), st.number_input("Right (mm)", step=0.1)
        with c_r:
            st.subheader("Rear Wheel")
            rr_rim = st.selectbox("Rim ", rim_opts, key="reg_rr")
            rr_hub = st.selectbox("Hub ", hub_opts, key="reg_rh")
            rl_len, rr_len = st.number_input("Left (mm) ", step=0.1), st.number_input("Right (mm) ", step=0.1)
        
        spk = st.selectbox("Spoke Model", spoke_opts)
        nip = st.selectbox("Nipple Model", nipple_opts)
        notes = st.text_area("Build Notes")
        
        if st.form_submit_button("🚀 Finalize & Register Build"):
            if cust:
                payload = {"customer": cust, "date": datetime.now().strftime("%Y-%m-%d"), "status": "Order Received", "invoice_url": inv,
                           "f_rim": fr_rim, "f_hub": fr_hub, "f_l": fl_len, "f_r": fr_len, "r_rim": rr_rim, "r_hub": rr_hub, "r_l": rl_len, "r_r": rr_len,
                           "spoke": spk, "nipple": nip, "notes": notes}
                base.table("builds").create(payload)

                db_table = base.table("spoke_db")
                df_rims = st.session_state.data["rims"]
                df_hubs = st.session_state.data["hubs"]

                for r, h, l, rr in [(fr_rim, fr_hub, fl_len, fr_len), (rr_rim, rr_hub, rl_len, rr_len)]:
                    if r != "None" and h != "None" and l > 0:
                        rd_id = df_rims[df_rims['label'] == r]['id'].values[0]
                        hd_id = df_hubs[df_hubs['label'] == h]['id'].values[0]
                        fp = f"{r} | {h}".replace("'", "\\'")
                        exist = db_table.all(formula=f"{{combo_id}}='{fp}'")
                        if exist:
                            db_table.update(exist[0]['id'], {"build_count": exist[0]['fields'].get('build_count', 1) + 1, "len_l": l, "len_r": rr})
                        else:
                            db_table.create({"rim": [rd_id], "hub": [hd_id], "len_l": l, "len_r": rr, "build_count": 1})
                
                refresh_api(); st.success("Registered!"); st.rerun()

# --- TAB 4: LIBRARY ---
with tabs[3]:
    st.header("📦 Library Management")
    with st.expander("➕ Add New Component"):
        cat = st.radio("Category", ["Rim", "Hub", "Spoke", "Nipple"], horizontal=True)
        with st.form("quick_add_v18_10"):
            name = st.text_input("Name")
            c1, c2 = st.columns(2)
            p = {}
            if cat == "Rim": p = {"rim": name, "erd": c1.number_input("ERD"), "holes": c2.number_input("Holes", value=28), "weight": st.number_input("Weight")}
            elif cat == "Hub": p = {"hub": name, "fd_l": c1.number_input("FD-L"), "fd_r": c2.number_input("FD-R"), "os_l": c1.number_input("OS-L"), "os_r": c2.number_input("OS-R"), "weight": st.number_input("Weight")}
            else: p = {cat.lower(): name, "weight": st.number_input("Weight (g)", format="%.3f")}
            if st.form_submit_button("Save to Database"):
                if name: 
                    base.table(f"{cat.lower()}s").create(p)
                    refresh_api(); st.success("Added!"); st.rerun()
    
    v_cat = st.radio("View Inventory:", ["rims", "hubs", "spokes", "nipples"], horizontal=True)
    df_lib = st.session_state.data[v_cat]
    if not df_lib.empty:
        st.dataframe(df_lib.drop(columns=['id', 'label'], errors='ignore').sort_values(df_lib.columns[0]), use_container_width=True, hide_index=True)
