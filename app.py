import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime

# --- 1. 設定網頁與樣式 ---
st.set_page_config(page_title="星巴克礁溪門市 | 營運報表", page_icon="☕", layout="wide")

st.markdown("""
<style>
    .stNumberInput input { padding: 0px 5px; }
    div[data-testid="stMetricValue"] { font-size: 1.2rem; }
    .big-font { font-size: 18px !important; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- 2. 定義 2026 國定假日表 ---
HOLIDAYS_2026 = {
    "2026-01-01": "🔴 元旦",
    "2026-02-16": "🔴 小年夜",
    "2026-02-17": "🔴 除夕",
    "2026-02-18": "🔴 春節",
    "2026-02-19": "🔴 春節",
    "2026-02-20": "🔴 春節",
    "2026-02-28": "🔴 228紀念日",
    "2026-04-03": "🔴 兒童節(補)",
    "2026-04-04": "🔴 兒童節",
    "2026-04-05": "🔴 清明節",
    "2026-04-06": "🔴 清明節(補)",
    "2026-05-01": "🔴 勞動節",
    "2026-06-19": "🔴 端午節",
    "2026-09-25": "🔴 中秋節",
    "2026-10-10": "🔴 國慶日",
}

def get_date_display(date_input):
    """轉換日期顯示格式 (含星期與假日)"""
    try:
        if isinstance(date_input, str):
            date_obj = pd.to_datetime(date_input).date()
        elif isinstance(date_input, pd.Timestamp):
            date_obj = date_input.date()
        else:
            date_obj = date_input

        date_str = str(date_obj)
        
        if date_str in HOLIDAYS_2026:
            week_str = ["(一)", "(二)", "(三)", "(四)", "(五)", "(六)", "(日)"][date_obj.weekday()]
            return f"{date_obj.strftime('%m/%d')} {week_str} {HOLIDAYS_2026[date_str]}"
        
        weekday = date_obj.weekday()
        week_str = ["(一)", "(二)", "(三)", "(四)", "(五)", "(六)", "(日)"][weekday]
        
        if weekday >= 5:
            return f"{date_obj.strftime('%m/%d')} {week_str} 🟠"
        else:
            return f"{date_obj.strftime('%m/%d')} {week_str}"
            
    except Exception:
        return str(date_input)

# --- 3. Google Sheet 連線設定 ---
def get_google_sheet_data():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    try:
        creds_dict = {}
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.
