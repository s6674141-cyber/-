import os
import pandas as pd
from datetime import datetime
import streamlit as st
import matplotlib.pyplot as plt

# -------------------------------------------------------------------
# 1. 頁面基本設定 (標題、圖示、寬螢幕佈局)
# -------------------------------------------------------------------
st.set_page_config(
    page_title="水電倉管系統",
    page_icon="🛠️",
    layout="wide"
)

MATERIALS_FILE = "materials.csv"
TOOLS_FILE = "tools.csv"
LOGS_FILE = "logs.csv"

# -------------------------------------------------------------------
# 2. 資料庫初始化與讀寫
# -------------------------------------------------------------------
def init_databases():
    if not os.path.exists(MATERIALS_FILE):
        df_mat = pd.DataFrame([
            {"材料編號": "M001", "材料名稱": "2.0單芯電線(紅)", "分類": "電線類", "目前庫存": 5, "安全庫存量": 10, "單位": "捲"},
            {"材料編號": "M002", "材料名稱": "6分PVC水管", "分類": "管路類", "目前庫存": 20, "安全庫存量": 8, "單位": "支"},
            {"材料編號": "M003", "材料名稱": "單切開關面板", "分類": "開關類", "目前庫存": 3, "安全庫存量": 5, "單位": "個"},
        ])
        df_mat.to_csv(MATERIALS_FILE, index=False, encoding="utf-8-sig")

    if not os.path.exists(TOOLS_FILE):
        df_tools = pd.DataFrame([
            {"工具編號": "T001", "工具名稱": "充電動力壓接機", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "T002", "工具名稱": "牧田衝擊電鑽", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "T003", "工具名稱": "電動通管機", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
        ])
        df_tools.to_csv(TOOLS_FILE, index=False, encoding="utf-8-sig")

    if not os.path.exists(LOGS_FILE):
        df_logs = pd.DataFrame(columns=["時間", "類型", "項目名稱", "變動數量/借用人", "備註"])
        df_logs.to_csv(LOGS_FILE, index=False, encoding="utf-8-sig")

init_databases()

def add_log(action_type, item_name, detail, note=""):
    df_logs = pd.read_csv(LOGS_FILE, encoding="utf-8-sig")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_log = {"時間": now_str, "類型": action_type, "項目名稱": item_name, "變動數量/借用人": detail, "備註": note}
    df_logs = pd.concat([df_logs, pd.DataFrame([new_log])], ignore_index=True)
    df_logs.to_csv(LOGS_FILE, index=False, encoding="utf-8-sig")

# -------------------------------------------------------------------
# 3. 側邊欄與頁面切換
# -------------------------------------------------------------------
st.sidebar.title("🛠️ 水電倉管系統")
page = st.sidebar.radio(
    "請選擇功能模組：",
    ["📦 材料庫存管理", "🔨 工具資產追蹤", "📊 數據分析儀表板", "📜 歷史異動紀錄"]
)

# -------------------------------------------------------------------
# 頁面 1：材料庫存管理
# -------------------------------------------------------------------
if page == "📦 材料庫存管理":
    st.header("📦 材料耗材庫存管理")
    
    df_mat = pd.read_csv(MATERIALS_FILE, encoding="utf-8-sig")
    
    # 頂部關鍵指標 (KPI Cards)
    low_stock_df = df_mat[df_mat["目前庫存"] <= df_mat["安全庫存量"]]
    
    col1, col2, col3 = st.columns(3)
    col1.metric("總材料品項", f"{len(df_mat)} 項")
    col2.metric("庫存正常項目", f"{len(df_mat) - len(low_stock_df)} 項")
    col3.metric("⚠️ 庫存警戒項目", f"{len(low_stock_df)} 項", delta_color="inverse")
    
    # 安全庫存警報區塊
    if not low_stock_df.empty:
        st.error("⚠️ **【安全庫存警報】以下材料庫存不足，請盡速補貨！**")
        st.dataframe(low_stock_df[["材料編號", "材料名稱", "目前庫存", "安全庫存量", "單位"]], use_container_width=True)

    st.subheader("📋 當前材料庫存清單")
    st.dataframe(df_mat, use_container_width=True)
    
    st.divider()
    
    # 領料與進貨操作面板
    st.subheader("🔄 領料 / 進貨登記")
    tab1, tab2, tab3 = st.tabs(["📤 師傅領料 (出庫)", "📥 材料進貨 (入庫)", "➕ 新增材料品項"])
    
    with tab1:
        with st.form("borrow_material_form"):
            selected_mat = st.selectbox("選擇領料項目", df_mat["材料編號"] + " - " + df_mat["材料名稱"])
            borrow_qty = st.number_input("領取數量", min_value=1, step=1)
            worker = st.text_input("領用師傅姓名")
            submit_borrow = st.form_submit_button("確認領料出庫")
            
            if submit_borrow:
                mat_id = selected_mat.split(" - ")[0]
                idx = df_mat[df_mat["材料編號"] == mat_id].index[0]
                mat_name = df_mat.loc[idx, "材料名稱"]
                curr_qty = df_mat.loc[idx, "目前庫存"]
                unit = df_mat.loc[idx, "單位"]
                
                if borrow_qty > curr_qty:
                    st.error(f"❌ 庫存不足！目前僅剩 {curr_qty} {unit}")
                else:
                    df_mat.loc[idx, "目前庫存"] -= borrow_qty
                    df_mat.to_csv(MATERIALS_FILE, index=False, encoding="utf-8-sig")
                    add_log("領料出庫", mat_name, f"-{borrow_qty} {unit}", f"領用人: {worker}")
                    st.success(f"✅ 成功領用 [{mat_name}] {borrow_qty} {unit}！")
                    st.rerun()

    with tab2:
        with st.form("add_stock_form"):
            selected_mat_in = st.selectbox("選擇進貨項目", df_mat["材料編號"] + " - " + df_mat["材料名稱"], key="in")
            in_qty = st.number_input("進貨數量", min_value=1, step=1, key="in_q")
            vendor = st.text_input("來源廠商/進貨備註")
            submit_in = st.form_submit_button("確認進貨入庫")
            
            if submit_in:
                mat_id = selected_mat_in.split(" - ")[0]
                idx = df_mat[df_mat["材料編號"] == mat_id].index[0]
                mat_name = df_mat.loc[idx, "材料名稱"]
                unit = df_mat.loc[idx, "單位"]
                
                df_mat.loc[idx, "目前庫存"] += in_qty
                df_mat.to_csv(MATERIALS_FILE, index=False, encoding="utf-8-sig")
                add_log("進貨入庫", mat_name, f"+{in_qty} {unit}", f"廠商: {vendor}")
                st.success(f"✅ 成功補貨 [{mat_name}] {in_qty} {unit}！")
                st.rerun()

    with tab3:
        with st.form("new_material_form"):
            new_name = st.text_input("材料名稱 (例如: 3/4 PVC彎頭)")
            new_cat = st.text_input("分類 (例如: 管路類)")
            init_qty = st.number_input("初始庫存", min_value=0, step=1)
            safe_qty = st.number_input("安全庫存警戒量", min_value=1, step=1)
            unit_str = st.text_input("單位 (例如: 個/支)")
            submit_new = st.form_submit_button("新增品項建檔")
            
            if submit_new and new_name:
                new_id = f"M{len(df_mat) + 1:03d}"
                new_row = {"材料編號": new_id, "材料名稱": new_name, "分類": new_cat, "目前庫存": init_qty, "安全庫存量": safe_qty, "單位": unit_str}
                df_mat = pd.concat([df_mat, pd.DataFrame([new_row])], ignore_index=True)
                df_mat.to_csv(MATERIALS_FILE, index=False, encoding="utf-8-sig")
                add_log("新增品項", new_name, f"+{init_qty}{unit_str}", "新品建檔")
                st.success(f"✅ 成功新增品項：[{new_id}] {new_name}")
                st.rerun()

# -------------------------------------------------------------------
# 頁面 2：工具資產追蹤
# -------------------------------------------------------------------
elif page == "🔨 工具資產追蹤":
    st.header("🔨 固定資產與工具借還追蹤")
    
    df_tools = pd.read_csv(TOOLS_FILE, encoding="utf-8-sig")
    borrowed_df = df_tools[df_tools["狀態"] == "借出"]
    
    col1, col2 = st.columns(2)
    col1.metric("工具總數量", f"{len(df_tools)} 件")
    col2.metric("外借中工具", f"{len(borrowed_df)} 件")
    
    st.subheader("📋 所有工具資產狀態")
    st.dataframe(df_tools, use_container_width=True)
    
    st.divider()
    
    col_b, col_r = st.columns(2)
    
    with col_b:
        st.subheader("📤 登記工具借出")
        in_stock_tools = df_tools[df_tools["狀態"] == "在庫"]
        if not in_stock_tools.empty:
            tool_to_borrow = st.selectbox("選擇要借出的工具", in_stock_tools["工具編號"] + " - " + in_stock_tools["工具名稱"])
            borrower_name = st.text_input("借用師傅姓名", key="b_name")
            if st.button("確認借出"):
                if borrower_name:
                    t_id = tool_to_borrow.split(" - ")[0]
                    idx = df_tools[df_tools["工具編號"] == t_id].index[0]
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    
                    df_tools.loc[idx, "狀態"] = "借出"
                    df_tools.loc[idx, "當前借用人"] = borrower_name
                    df_tools.loc[idx, "借出日期"] = today_str
                    df_tools.to_csv(TOOLS_FILE, index=False, encoding="utf-8-sig")
                    
                    add_log("工具借出", df_tools.loc[idx, "工具名稱"], borrower_name, f"借出日期: {today_str}")
                    st.success(f"✅ [{df_tools.loc[idx, '工具名稱']}] 已登記借給 {borrower_name}")
                    st.rerun()
                else:
                    st.warning("⚠️ 請輸入借用人姓名！")
        else:
            st.info("目前所有工具皆外借中，無在庫工具。")

    with col_r:
        st.subheader("📥 登記工具歸還")
        if not borrowed_df.empty:
            tool_to_return = st.selectbox("選擇要歸還的工具", borrowed_df["工具編號"] + " - " + borrowed_df["工具名稱"])
            if st.button("確認歸還"):
                t_id = tool_to_return.split(" - ")[0]
                idx = df_tools[df_tools["工具編號"] == t_id].index[0]
                b_name = df_tools.loc[idx, "當前借用人"]
                
                df_tools.loc[idx, "狀態"] = "在庫"
                df_tools.loc[idx, "當前借用人"] = "無"
                df_tools.loc[idx, "借出日期"] = "無"
                df_tools.to_csv(TOOLS_FILE, index=False, encoding="utf-8-sig")
                
                add_log("工具歸還", df_tools.loc[idx, "工具名稱"], b_name, "歸還入庫")
                st.success(f"✅ [{df_tools.loc[idx, '工具名稱']}] 已順利歸還！")
                st.rerun()
        else:
            st.success("🎉 目前所有工具皆在庫，沒有外借中的工具！")

# -------------------------------------------------------------------
# 頁面 3：數據分析儀表板
# -------------------------------------------------------------------
elif page == "📊 數據分析儀表板":
    st.header("📊 後台數據分析與決策儀表板")
    
    df_logs = pd.read_csv(LOGS_FILE, encoding="utf-8-sig")
    
    if df_logs.empty:
        st.info("目前尚無足夠的歷史流水帳數據可供分析。")
    else:
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.subheader("🔥 熱門耗材領料排行榜")
            usage_logs = df_logs[df_logs["類型"] == "領料出庫"]
            if not usage_logs.empty:
                mat_counts = usage_logs["項目名稱"].value_counts()
                st.bar_chart(mat_counts)
            else:
                st.write("尚無領料數據。")
                
        with col_chart2:
            st.subheader("🔨 工具借用頻率分析")
            tool_logs = df_logs[df_logs["類型"] == "工具借出"]
            if not tool_logs.empty:
                tool_counts = tool_logs["項目名稱"].value_counts()
                st.bar_chart(tool_counts)
            else:
                st.write("尚無工具借出數據。")

# -------------------------------------------------------------------
# 頁面 4：歷史異動紀錄
# -------------------------------------------------------------------
elif page == "📜 歷史異動紀錄":
    st.header("📜 系統異動流水帳紀錄")
    df_logs = pd.read_csv(LOGS_FILE, encoding="utf-8-sig")
    st.dataframe(df_logs.sort_index(ascending=False), use_container_width=True)