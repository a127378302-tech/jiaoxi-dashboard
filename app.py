import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime

# --- 設定網頁 ---
st.set_page_config(page_title="星巴克礁溪門市 | 雲端儀表板", page_icon="☕", layout="wide")

# --- 1. 連線設定 (這是魔法的關鍵) ---
# 這裡會去讀取您在 Streamlit Cloud 設定的 "Secrets"
def get_google_sheet_data():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    # 從 Secrets 讀取憑證資訊
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    # 開啟您的試算表 (請確保名稱完全一致)
    sheet = client.open("Jiaoxi_2026_Data").sheet1
    return sheet

# --- 2. 讀取資料函式 ---
@st.cache_data(ttl=60) # 每 60 秒快取過期，確保資料新鮮
def load_data():
    try:
        sheet = get_google_sheet_data()
        data = sheet.get_all_records()
        if not data:
            # 如果是空的，建立 2026 空白資料
            return create_empty_data(sheet)
        df = pd.DataFrame(data)
        # 確保日期格式
        df["日期"] = pd.to_datetime(df["日期"]).dt.date
        return df
    except Exception as e:
        st.error(f"連線失敗，請檢查 Google Sheet 設定: {e}")
        return pd.DataFrame()

def create_empty_data(sheet):
    # 初始化 2026 全年資料並寫入 Sheet
    date_range = pd.date_range(start="2026-01-01", end="2026-12-31", freq="D")
    df = pd.DataFrame({
        "日期": date_range.astype(str),
        "目標": [0] * len(date_range),
        "實績": [0] * len(date_range),
        "備註": [""] * len(date_range)
    })
    # 寫入標題與內容
    sheet.update([df.columns.values.tolist()] + df.values.tolist())
    return df

# --- 3. 儲存資料函式 ---
def save_data_to_sheet(df):
    try:
        sheet = get_google_sheet_data()
        # 為了避免格式跑掉，我們把日期轉字串
        save_df = df.copy()
        save_df["日期"] = save_df["日期"].astype(str)
        sheet.update([save_df.columns.values.tolist()] + save_df.values.tolist())
        st.toast("✅ 雲端同步完成！", icon="☁️") # 跳出可愛的提示
        st.cache_data.clear() # 清除快取，強制下次讀取最新
    except Exception as e:
        st.error(f"儲存失敗: {e}")

# --- 主程式 ---
# 登入檢查 (簡化版，沿用之前的邏輯)
USERS = {"SM": "sm2026", "SS": "coffee123"}
if "authenticated" not in st.session_state: st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 登入")
    u = st.text_input("User")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        if u in USERS and USERS[u] == p:
            st.session_state.authenticated = True
            st.session_state.role = "SM" if u == "SM" else "SS"
            st.rerun()
else:
    # 登入成功後
    with st.sidebar:
        st.success(f"Hi, {st.session_state.role}")
        if st.button("重新讀取資料"):
            st.cache_data.clear()
            st.rerun()
        
        st.info("💡 資料會自動同步到 Google Sheet，無需手動下載。")

    st.title("☕ 2026 雲端營運儀表板")
    
    # 讀取資料 (自動從雲端抓)
    if "df" not in st.session_state:
        st.session_state.df = load_data()
    
    df = st.session_state.df
    
    # 選擇月份
    selected_month = st.selectbox("月份", range(1, 13))
    
    # 篩選與編輯
    df["Month"] = pd.to_datetime(df["日期"]).dt.month
    current_month_df = df[df["Month"] == selected_month].copy()
    
    # 顯示編輯器
    disabled = ["日期"] if st.session_state.role == "SM" else ["日期", "目標"]
    
    edited_df = st.data_editor(
        current_month_df[["日期", "目標", "實績", "備註"]],
        column_config={
            "日期": st.column_config.DateColumn(disabled=True),
            "目標": st.column_config.NumberColumn(disabled="目標" in disabled),
        },
        use_container_width=True,
        hide_index=True,
        num_rows="fixed"
    )

    # 儲存按鈕
    if st.button("💾 更新並同步到雲端"):
        # 更新本地 DataFrame
        for index, row in edited_df.iterrows():
            mask = df["日期"] == row["日期"]
            df.loc[mask, "目標"] = row["目標"]
            df.loc[mask, "實績"] = row["實績"]
            df.loc[mask, "備註"] = row["備註"]
        
        # 呼叫儲存函式
        save_data_to_sheet(df)
        st.session_state.df = df # 更新記憶體
        st.success("資料已安全儲存到 Google Sheet！")
