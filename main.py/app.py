import pandas as pd
from datetime import datetime
import streamlit as st
import matplotlib.pyplot as plt
import gspread
from google.oauth2.service_account import Credentials
import re

# -------------------------------------------------------------------
# 0. 跨平台字型與頁面基本設定
# -------------------------------------------------------------------
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'PingFang TC', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

st.set_page_config(
    page_title="水電倉管與資產追蹤系統 (權限分流版)",
    page_icon="🛠️",
    layout="wide"
)

# 隱藏 Streamlit 工具列與頂欄
hide_streamlit_style = """
    <style>
    .stAppToolbar, [data-testid="stToolbar"] { display: none !important; }
    #MainMenu, header, footer { visibility: hidden !important; display: none !important; }
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# -------------------------------------------------------------------
# 1. Google Sheets 雲端資料庫連線邏輯
# -------------------------------------------------------------------
@st.cache_resource
def get_gsheet_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    credentials_info = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(credentials_info, scopes=scope)
    return gspread.authorize(creds)

def load_data(worksheet_name):
    try:
        client = get_gsheet_client()
        sheet = client.open("水電倉管資料庫").worksheet(worksheet_name)
        data = sheet.get_all_records()
        return pd.DataFrame(data), sheet
    except Exception as e:
        st.error(f"❌ 無法連線至 Google Sheets 分頁 [{worksheet_name}]，錯誤資訊：{e}")
        return pd.DataFrame(), None

def save_data(sheet, df):
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.astype(str).values.tolist())

def add_log_gsheet(action_type, item_name, detail, note=""):
    df_logs, sheet_logs = load_data("logs")
    if sheet_logs is not None:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_log = {"時間": now_str, "類型": action_type, "項目名稱": item_name, "變動數量/借用人": detail, "備註": note}
        df_logs = pd.concat([df_logs, pd.DataFrame([new_log])], ignore_index=True)
        save_data(sheet_logs, df_logs)

def undo_last_log():
    df_logs, sheet_logs = load_data("logs")
    if df_logs.empty:
        return False, "目前沒有可撤銷的歷史紀錄！"
    
    last_log = df_logs.iloc[-1]
    action_type = str(last_log["類型"])
    item_name = str(last_log["項目名稱"])
    detail = str(last_log["變動數量/借用人"])
    note = str(last_log["備註"])
    
    if action_type in ["領料出庫", "進貨入庫"]:
        df_mat, sheet_mat = load_data("materials")
        if not df_mat.empty and item_name in df_mat["材料名稱"].astype(str).values:
            idx = df_mat[df_mat["材料名稱"].astype(str) == item_name].index[0]
            numbers = re.findall(r'\d+', detail)
            qty = int(numbers[0]) if numbers else 0
            if action_type == "領料出庫":
                df_mat.loc[idx, "目前庫存"] = pd.to_numeric(df_mat.loc[idx, "目前庫存"], errors='coerce') + qty
            else:
                df_mat.loc[idx, "目前庫存"] = max(0, pd.to_numeric(df_mat.loc[idx, "目前庫存"], errors='coerce') - qty)
            save_data(sheet_mat, df_mat)

    elif action_type == "新增品項":
        df_mat, sheet_mat = load_data("materials")
        if not df_mat.empty and item_name in df_mat["材料名稱"].astype(str).values:
            df_mat = df_mat[df_mat["材料名稱"].astype(str) != item_name].reset_index(drop=True)
            save_data(sheet_mat, df_mat)

    elif action_type in ["工具借出", "工具歸還", "工具送修", "維修完成"]:
        df_tools, sheet_tools = load_data("tools")
        if not df_tools.empty and item_name in df_tools["工具名稱"].astype(str).values:
            idx = df_tools[df_tools["工具名稱"].astype(str) == item_name].index[0]
            if action_type in ["工具借出", "維修完成"]:
                df_tools.loc[idx, "狀態"] = "在庫"
                df_tools.loc[idx, "當前借用人"] = "無"
                df_tools.loc[idx, "借出日期"] = "無"
            elif action_type == "工具歸還":
                df_tools.loc[idx, "狀態"] = "借出"
                df_tools.loc[idx, "當前借用人"] = detail
                df_tools.loc[idx, "借出日期"] = datetime.now().strftime("%Y-%m-%d")
            save_data(sheet_tools, df_tools)

    df_logs = df_logs.iloc[:-1].reset_index(drop=True)
    save_data(sheet_logs, df_logs)
    add_log_gsheet("撤銷操作", item_name, "反轉成功", f"已撤銷: {action_type} ({detail})")
    return True, f"✅ 已成功撤銷【{action_type} - {item_name}】！"

# -------------------------------------------------------------------
# 2. Session State 身分管理與側邊欄
# -------------------------------------------------------------------
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False

st.sidebar.title("🛠️ 水電倉管系統")

# 身分選擇器
role = st.sidebar.radio("👤 請選擇操作身分：", ["👷 一般員工 (現場師傅)", "🔑 倉管管理員"])

if role == "🔑 倉管管理員":
    if not st.session_state.is_admin:
        pwd = st.sidebar.text_input("🔑 請輸入管理員密碼", type="password")
        if pwd == "admin123":
            st.session_state.is_admin = True
            st.sidebar.success("🔓 管理員解鎖成功！")
            st.rerun()
        elif pwd != "":
            st.sidebar.error("❌ 密碼錯誤")
else:
    st.session_state.is_admin = False

st.sidebar.markdown("---")

# 根據身分顯示可選選單
if st.session_state.is_admin:
    st.sidebar.caption("🔑 權限狀態：全功能管理員")
    menu_options = [
        "📦 材料庫存管理", 
        "🔨 工具資產追蹤", 
        "📤 CSV 批次匯入", 
        "📊 數據分析儀表板", 
        "📜 歷史異動紀錄"
    ]
else:
    st.sidebar.caption("👷 權限狀態：一般員工模式")
    menu_options = [
        "📦 材料領用與進貨", 
        "🔨 工具借還與維修"
    ]

page = st.sidebar.radio("請選擇功能分頁：", menu_options)

# -------------------------------------------------------------------
# 分頁 A：📦 材料領用與進貨 (一般員工)
# -------------------------------------------------------------------
if page == "📦 材料領用與進貨":
    st.header("📦 材料領用與進貨登記 (現場專用)")
    df_mat, sheet_mat = load_data("materials")
    
    if not df_mat.empty:
        df_mat["目前庫存"] = pd.to_numeric(df_mat["目前庫存"], errors='coerce').fillna(0).astype(int)
        df_mat["安全庫存量"] = pd.to_numeric(df_mat["安全庫存量"], errors='coerce').fillna(0).astype(int)
        
        st.subheader("📋 當前材料庫存總覽")
        st.dataframe(df_mat[["材料編號", "材料名稱", "規格/尺寸", "分類", "目前庫存", "單位"]], use_container_width=True)
        st.markdown("---")
        
        tab1, tab2 = st.tabs(["📤 師傅領料登記", "📥 進貨入庫登記"])
        
        with tab1:
            with st.form("emp_borrow_form"):
                selected_mat = st.selectbox("選擇領料項目", df_mat["材料編號"].astype(str) + " - " + df_mat["材料名稱"])
                borrow_qty = st.number_input("領取數量", min_value=1, step=1)
                worker = st.text_input("領用師傅 / 工地名稱")
                submit_borrow = st.form_submit_button("確認領料出庫", type="primary")
                
                if submit_borrow:
                    mat_id = selected_mat.split(" - ")[0]
                    idx = df_mat[df_mat["材料編號"].astype(str) == mat_id].index[0]
                    mat_name = df_mat.loc[idx, "材料名稱"]
                    curr_qty = df_mat.loc[idx, "目前庫存"]
                    unit = df_mat.loc[idx, "單位"]
                    
                    if borrow_qty > curr_qty:
                        st.error(f"❌ 庫存不足！目前剩餘庫存為 {curr_qty} {unit}")
                    else:
                        df_mat.loc[idx, "目前庫存"] -= borrow_qty
                        save_data(sheet_mat, df_mat)
                        add_log_gsheet("領料出庫", mat_name, f"-{borrow_qty} {unit}", f"領用人/工程: {worker}")
                        st.success(f"✅ 成功領用 [{mat_name}] {borrow_qty} {unit}！已同步至雲端！")
                        st.rerun()

        with tab2:
            with st.form("emp_in_form"):
                selected_mat_in = st.selectbox("選擇進貨項目", df_mat["材料編號"].astype(str) + " - " + df_mat["材料名稱"], key="emp_in")
                in_qty = st.number_input("進貨數量", min_value=1, step=1, key="emp_in_q")
                vendor = st.text_input("來源廠商 / 備註")
                submit_in = st.form_submit_button("確認進貨入庫", type="primary")
                
                if submit_in:
                    mat_id = selected_mat_in.split(" - ")[0]
                    idx = df_mat[df_mat["材料編號"].astype(str) == mat_id].index[0]
                    mat_name = df_mat.loc[idx, "材料名稱"]
                    unit = df_mat.loc[idx, "單位"]
                    
                    df_mat.loc[idx, "目前庫存"] += in_qty
                    save_data(sheet_mat, df_mat)
                    add_log_gsheet("進貨入庫", mat_name, f"+{in_qty} {unit}", f"進貨廠商: {vendor}")
                    st.success(f"✅ 成功補貨 [{mat_name}] {in_qty} {unit}！已同步至雲端！")
                    st.rerun()

# -------------------------------------------------------------------
# 分頁 B：🔨 工具借還與維修 (一般員工)
# -------------------------------------------------------------------
elif page == "🔨 工具借還與維修":
    st.header("🔨 工具資產借還與報修 (現場專用)")
    df_tools, sheet_tools = load_data("tools")
    
    if not df_tools.empty:
        st.subheader("📋 所有工具清單與當前狀態")
        st.dataframe(df_tools, use_container_width=True)
        st.markdown("---")
        
        tab_tb, tab_tr, tab_maint = st.tabs(["📤 登記工具借出", "📥 登記工具歸還", "🔧 損壞報修 / 維修完成"])
        
        borrowed_df = df_tools[df_tools["狀態"] == "借出"]
        repairing_df = df_tools[df_tools["狀態"] == "維修中"]
        in_stock_tools = df_tools[df_tools["狀態"] == "在庫"]
        
        with tab_tb:
            if not in_stock_tools.empty:
                tool_to_borrow = st.selectbox("選擇要借出的工具", in_stock_tools["工具編號"].astype(str) + " - " + in_stock_tools["工具名稱"])
                borrower_name = st.text_input("借用師傅姓名", key="emp_b_name")
                if st.button("確認登記借出", type="primary"):
                    if borrower_name:
                        t_id = tool_to_borrow.split(" - ")[0]
                        idx = df_tools[df_tools["工具編號"].astype(str) == t_id].index[0]
                        today_str = datetime.now().strftime("%Y-%m-%d")
                        
                        df_tools.loc[idx, "狀態"] = "借出"
                        df_tools.loc[idx, "當前借用人"] = borrower_name
                        df_tools.loc[idx, "借出日期"] = today_str
                        
                        save_data(sheet_tools, df_tools)
                        add_log_gsheet("工具借出", df_tools.loc[idx, "工具名稱"], borrower_name, f"借出日期: {today_str}")
                        st.success(f"✅ [{df_tools.loc[idx, '工具名稱']}] 已順利借給【{borrower_name}】！")
                        st.rerun()
                    else:
                        st.warning("⚠️ 請輸入借用師傅姓名！")
            else:
                st.info("目前無在庫可借出工具。")

        with tab_tr:
            if not borrowed_df.empty:
                tool_to_return = st.selectbox("選擇要歸還的工具", borrowed_df["工具編號"].astype(str) + " - " + borrowed_df["工具名稱"])
                if st.button("確認登記歸還", type="primary"):
                    t_id = tool_to_return.split(" - ")[0]
                    idx = df_tools[df_tools["工具編號"].astype(str) == t_id].index[0]
                    b_name = df_tools.loc[idx, "當前借用人"]
                    
                    df_tools.loc[idx, "狀態"] = "在庫"
                    df_tools.loc[idx, "當前借用人"] = "無"
                    df_tools.loc[idx, "借出日期"] = "無"
                    
                    save_data(sheet_tools, df_tools)
                    add_log_gsheet("工具歸還", df_tools.loc[idx, "工具名稱"], b_name, "歸還入庫")
                    st.success(f"✅ [{df_tools.loc[idx, '工具名稱']}] 已歸還入庫！")
                    st.rerun()
            else:
                st.success("🎉 目前沒有外借中的工具！")

        with tab_maint:
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.subheader("🛠️ 登記工具送修")
                can_repair_tools = df_tools[df_tools["狀態"].isin(["在庫", "借出"])]
                if not can_repair_tools.empty:
                    tool_to_repair = st.selectbox("選擇要送修的工具", can_repair_tools["工具編號"].astype(str) + " - " + can_repair_tools["工具名稱"], key="emp_rep")
                    repair_reason = st.text_input("故障原因 / 保養項目")
                    repair_vendor = st.text_input("維修廠商 (選填)")
                    
                    if st.button("🔧 確認登記送修"):
                        if repair_reason:
                            t_id = tool_to_repair.split(" - ")[0]
                            idx = df_tools[df_tools["工具編號"].astype(str) == t_id].index[0]
                            t_name = df_tools.loc[idx, "工具名稱"]
                            
                            df_tools.loc[idx, "狀態"] = "維修中"
                            df_tools.loc[idx, "當前借用人"] = f"維修中 ({repair_vendor})" if repair_vendor else "維修中"
                            df_tools.loc[idx, "借出日期"] = datetime.now().strftime("%Y-%m-%d")
                            
                            save_data(sheet_tools, df_tools)
                            add_log_gsheet("工具送修", t_name, "轉維修中", f"原因: {repair_reason} | 廠商: {repair_vendor}")
                            st.success(f"✅ [{t_name}] 已登記為維修中！")
                            st.rerun()
                        else:
                            st.warning("⚠️ 請輸入故障原因！")
            
            with col_m2:
                st.subheader("✅ 登記維修完成入庫")
                if not repairing_df.empty:
                    tool_repaired = st.selectbox("選擇已修好的工具", repairing_df["工具編號"].astype(str) + " - " + repairing_df["工具名稱"], key="emp_repaired")
                    repair_note = st.text_input("修復備註 (選填)")
                    
                    if st.button("🎉 確認修復完工入庫"):
                        t_id = tool_repaired.split(" - ")[0]
                        idx = df_tools[df_tools["工具編號"].astype(str) == t_id].index[0]
                        t_name = df_tools.loc[idx, "工具名稱"]
                        
                        df_tools.loc[idx, "狀態"] = "在庫"
                        df_tools.loc[idx, "當前借用人"] = "無"
                        df_tools.loc[idx, "借出日期"] = "無"
                        
                        save_data(sheet_tools, df_tools)
                        add_log_gsheet("維修完成", t_name, "修復完工入庫", f"備註: {repair_note}")
                        st.success(f"✅ [{t_name}] 已恢復為【在庫】狀態！")
                        st.rerun()

# -------------------------------------------------------------------
# 分頁 C：📦 材料庫存管理 (管理員完整功能)
# -------------------------------------------------------------------
elif page == "📦 材料庫存管理" and st.session_state.is_admin:
    st.header("📦 材料庫存管理模組 (管理員全功能)")
    df_mat, sheet_mat = load_data("materials")
    
    if not df_mat.empty:
        df_mat["目前庫存"] = pd.to_numeric(df_mat["目前庫存"], errors='coerce').fillna(0).astype(int)
        df_mat["安全庫存量"] = pd.to_numeric(df_mat["安全庫存量"], errors='coerce').fillna(0).astype(int)
        low_stock_df = df_mat[df_mat["目前庫存"] <= df_mat["安全庫存量"]]
        
        col1, col2, col3 = st.columns(3)
        col1.metric("材料總品項", f"{len(df_mat)} 項")
        col2.metric("庫存正常項目", f"{len(df_mat) - len(low_stock_df)} 項")
        col3.metric("⚠️ 庫存警報項目", f"{len(low_stock_df)} 項", delta_color="inverse")
        
        st.markdown("---")
        
        if not low_stock_df.empty:
            st.error("⚠️ **【安全庫存警報】以下材料庫存已低於警戒線，請及時補貨！**")
            st.dataframe(low_stock_df[["材料編號", "材料名稱", "分類", "目前庫存", "安全庫存量", "單位"]], use_container_width=True)

        col_ex1, _ = st.columns([1, 4])
        with col_ex1:
            csv_data = df_mat.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 匯出完整材料庫存 CSV", data=csv_data, file_name=f"材料庫存總表_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")

        st.subheader("📋 當前材料庫存總覽")
        st.dataframe(df_mat, use_container_width=True)
        st.markdown("---")
        
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📤 師傅領料登記", "📥 進貨入庫登記", "➕ 新增材料品項", "✏️ 修改/編輯材料資料", "🗑️ 刪除材料品項"])
        
        with tab1:
            with st.form("adm_borrow_form"):
                selected_mat = st.selectbox("選擇領料項目", df_mat["材料編號"].astype(str) + " - " + df_mat["材料名稱"])
                borrow_qty = st.number_input("領取數量", min_value=1, step=1)
                worker = st.text_input("領用師傅 / 工地名稱")
                submit_borrow = st.form_submit_button("確認領料出庫")
                if submit_borrow:
                    mat_id = selected_mat.split(" - ")[0]
                    idx = df_mat[df_mat["材料編號"].astype(str) == mat_id].index[0]
                    mat_name, curr_qty, unit = df_mat.loc[idx, "材料名稱"], df_mat.loc[idx, "目前庫存"], df_mat.loc[idx, "單位"]
                    if borrow_qty > curr_qty: st.error(f"❌ 庫存不足！")
                    else:
                        df_mat.loc[idx, "目前庫存"] -= borrow_qty
                        save_data(sheet_mat, df_mat)
                        add_log_gsheet("領料出庫", mat_name, f"-{borrow_qty} {unit}", f"領用人/工程: {worker}")
                        st.success(f"✅ 成功領用 [{mat_name}]！"); st.rerun()

        with tab2:
            with st.form("adm_in_form"):
                selected_mat_in = st.selectbox("選擇進貨項目", df_mat["材料編號"].astype(str) + " - " + df_mat["材料名稱"], key="adm_in")
                in_qty = st.number_input("進貨數量", min_value=1, step=1, key="adm_in_q")
                vendor = st.text_input("來源廠商 / 備註")
                submit_in = st.form_submit_button("確認進貨入庫")
                if submit_in:
                    mat_id = selected_mat_in.split(" - ")[0]
                    idx = df_mat[df_mat["材料編號"].astype(str) == mat_id].index[0]
                    mat_name, unit = df_mat.loc[idx, "材料名稱"], df_mat.loc[idx, "單位"]
                    df_mat.loc[idx, "目前庫存"] += in_qty
                    save_data(sheet_mat, df_mat)
                    add_log_gsheet("進貨入庫", mat_name, f"+{in_qty} {unit}", f"進貨廠商: {vendor}")
                    st.success(f"✅ 成功補貨 [{mat_name}]！"); st.rerun()

        with tab3:
            with st.form("adm_new_form"):
                new_name = st.text_input("材料名稱")
                new_spec = st.text_input("規格/尺寸")
                new_cat = st.text_input("分類")
                init_qty = st.number_input("初始庫存數量", min_value=0, step=1)
                safe_qty = st.number_input("安全庫存門檻", min_value=1, step=1)
                unit_str = st.text_input("計算單位")
                if st.form_submit_button("確認新增建檔") and new_name:
                    new_id = f"M{len(df_mat) + 1:03d}"
                    new_row = {"材料編號": new_id, "材料名稱": new_name, "規格/尺寸": new_spec or "無", "分類": new_cat, "目前庫存": init_qty, "安全庫存量": safe_qty, "單位": unit_str}
                    df_mat = pd.concat([df_mat, pd.DataFrame([new_row])], ignore_index=True)
                    save_data(sheet_mat, df_mat)
                    add_log_gsheet("新增品項", new_name, f"+{init_qty}{unit_str}", f"規格:{new_spec}")
                    st.success(f"✅ 成功新增品項！"); st.rerun()

        with tab4:
            selected_edit = st.selectbox("選擇修改項目", df_mat["材料編號"].astype(str) + " - " + df_mat["材料名稱"], key="adm_edit_sel")
            if selected_edit:
                e_id = selected_edit.split(" - ")[0]
                m_idx = df_mat[df_mat["材料編號"].astype(str) == e_id].index[0]
                with st.form("adm_edit_form"):
                    e_name = st.text_input("材料名稱", value=df_mat.loc[m_idx, "材料名稱"])
                    e_cat = st.text_input("分類名稱", value=df_mat.loc[m_idx, "分類"])
                    e_unit = st.text_input("計算單位", value=df_mat.loc[m_idx, "單位"])
                    e_qty = st.number_input("目前庫存", value=int(df_mat.loc[m_idx, "目前庫存"]), min_value=0)
                    e_safe = st.number_input("安全庫存", value=int(df_mat.loc[m_idx, "安全庫存量"]), min_value=1)
                    if st.form_submit_button("💾 儲存修改"):
                        df_mat.loc[m_idx, ["材料名稱", "分類", "單位", "目前庫存", "安全庫存量"]] = [e_name, e_cat, e_unit, e_qty, e_safe]
                        save_data(sheet_mat, df_mat)
                        st.success(f"✅ 成功更新資料！"); st.rerun()

        with tab5:
            selected_del = st.selectbox("選擇要刪除的材料", df_mat["材料編號"].astype(str) + " - " + df_mat["材料名稱"], key="adm_del_sel")
            if selected_del:
                d_id = selected_del.split(" - ")[0]
                d_idx = df_mat[df_mat["材料編號"].astype(str) == d_id].index[0]
                d_name = df_mat.loc[d_idx, "材料名稱"]
                st.warning(f"⚠️ 確定刪除 [{d_name}] 嗎？")
                chk = st.checkbox(f"我確定要刪除 [{d_name}]")
                if st.button("🔥 確定刪除") and chk:
                    df_mat = df_mat.drop(d_idx).reset_index(drop=True)
                    save_data(sheet_mat, df_mat)
                    st.success(f"✅ 成功刪除 [{d_name}]！"); st.rerun()

# -------------------------------------------------------------------
# 分頁 D：🔨 工具資產追蹤 (管理員全功能)
# -------------------------------------------------------------------
elif page == "🔨 工具資產追蹤" and st.session_state.is_admin:
    st.header("🔨 固定資產與工具管理 (管理員全功能)")
    df_tools, sheet_tools = load_data("tools")
    if not df_tools.empty:
        st.dataframe(df_tools, use_container_width=True)
        st.markdown("---")
        tab_tb, tab_tr, tab_maint, tab_tn, tab_te, tab_td = st.tabs(["📤 借出", "📥 歸還", "🔧 維修", "➕ 新增工具", "✏️ 編輯工具", "🗑️ 報銷刪除"])
        
        with tab_tn:
            with st.form("adm_new_tool"):
                t_name = st.text_input("工具名稱")
                t_brand = st.text_input("品牌/廠牌")
                t_model = st.text_input("型號")
                t_cat = st.text_input("分類")
                if st.form_submit_button("確認新增工具建檔") and t_name:
                    new_t_id = f"T{len(df_tools) + 1:03d}"
                    new_tool = {"工具編號": new_t_id, "工具名稱": t_name, "品牌/廠牌": t_brand or "無", "型號": t_model or "無", "分類": t_cat or "通用", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"}
                    df_tools = pd.concat([df_tools, pd.DataFrame([new_tool])], ignore_index=True)
                    save_data(sheet_tools, df_tools)
                    st.success("✅ 成功建檔工具！"); st.rerun()

        with tab_td:
            selected_del_t = st.selectbox("選擇要報銷的工具", df_tools["工具編號"].astype(str) + " - " + df_tools["工具名稱"])
            if selected_del_t:
                dt_id = selected_del_t.split(" - ")[0]
                dt_idx = df_tools[df_tools["工具編號"].astype(str) == dt_id].index[0]
                dt_name = df_tools.loc[dt_idx, "工具名稱"]
                if st.button(f"🔥 確定報銷刪除 [{dt_name}]"):
                    df_tools = df_tools.drop(dt_idx).reset_index(drop=True)
                    save_data(sheet_tools, df_tools)
                    st.success("✅ 工具已報銷刪除！"); st.rerun()

# -------------------------------------------------------------------
# 分頁 E：📤 CSV 批次匯入 (管理員專屬)
# -------------------------------------------------------------------
elif page == "📤 CSV 批次匯入" and st.session_state.is_admin:
    st.header("📤 CSV 資料批次匯入中心")
    target_type = st.radio("📌 第一步：選擇資料種類", ["📦 材料耗材", "🔨 工具資產", "📜 歷史紀錄"], horizontal=True)
    uploaded_file = st.file_uploader("📂 第二步：上傳 CSV 檔案", type=["csv"])
    
    if uploaded_file is not None:
        try:
            import_df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
            st.dataframe(import_df.head(10), use_container_width=True)
            import_mode = st.radio("🔄 第三步：匯入模式", ["追加至現有資料庫底部", "完全覆蓋現有資料庫"])
            
            if st.button("🚀 確認執行匯入", type="primary"):
                if "材料" in target_type:
                    df_mat, sheet_mat = load_data("materials")
                    if "規格/尺寸" not in import_df.columns: import_df["規格/尺寸"] = "無"
                    final_df = import_df if "完全覆蓋" in import_mode else pd.concat([df_mat, import_df], ignore_index=True)
                    save_data(sheet_mat, final_df)
                    st.success("🎉 材料資料匯入成功！")
                elif "工具" in target_type:
                    df_tools, sheet_tools = load_data("tools")
                    final_df = import_df if "完全覆蓋" in import_mode else pd.concat([df_tools, import_df], ignore_index=True)
                    save_data(sheet_tools, final_df)
                    st.success("🎉 工具資料匯入成功！")
                else:
                    df_logs, sheet_logs = load_data("logs")
                    final_df = import_df if "完全覆蓋" in import_mode else pd.concat([df_logs, import_df], ignore_index=True)
                    save_data(sheet_logs, final_df)
                    st.success("🎉 歷史紀錄匯入成功！")
        except Exception as e:
            st.error(f"❌ 讀取失敗：{e}")

# -------------------------------------------------------------------
# 分頁 F：📊 數據分析儀表板 (管理員專屬)
# -------------------------------------------------------------------
elif page == "📊 數據分析儀表板" and st.session_state.is_admin:
    st.header("📊 後台數據分析與經營決策儀表板")
    df_logs, _ = load_data("logs")
    
    if not df_logs.empty:
        usage_logs = df_logs[df_logs["類型"] == "領料出庫"]
        repair_logs = df_logs[df_logs["類型"] == "工具送修"]
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🏗️ 各工程專案耗材領用頻率")
            if not usage_logs.empty:
                usage_logs["工程案"] = usage_logs["備註"].apply(lambda x: str(x).split("-")[0].strip() if "-" in str(x) else "未分類")
                st.bar_chart(usage_logs["工程案"].value_counts())
        with col2:
            st.subheader("🚨 高頻損壞 / 送修工具警報")
            if not repair_logs.empty:
                st.bar_chart(repair_logs["項目名稱"].value_counts())
            else:
                st.success("🎉 目前無工具維修紀錄！")

# -------------------------------------------------------------------
# 分頁 G：📜 歷史異動紀錄 (管理員專屬)
# -------------------------------------------------------------------
elif page == "📜 歷史異動紀錄" and st.session_state.is_admin:
    st.header("📜 系統完整流水帳歷程")
    df_logs, _ = load_data("logs")
    if not df_logs.empty:
        last_log = df_logs.iloc[-1]
        st.info(f"📌 最近一次操作：【{last_log['時間']}】 - 【{last_log['類型']}】 - {last_log['項目名稱']}")
        if st.button("↩️ 一鍵撤銷最後這筆操作", type="primary"):
            success, msg = undo_last_log()
            if success: st.success(msg); st.rerun()
            else: st.error(msg)
        st.markdown("---")
        st.dataframe(df_logs.sort_index(ascending=False), use_container_width=True)
