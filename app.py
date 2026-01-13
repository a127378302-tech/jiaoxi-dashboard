import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime

# --- 1. 設定網頁與樣式 (必須放在最前面) ---
st.set_page_config(page_title="星巴克礁溪門市 | 營運戰情室", page_icon="☕", layout="wide")

st.markdown("""
<style>
    .stNumberInput input { padding: 0px 5px; }
    div[data-testid="stMetricValue"] { font-size: 1.2rem; }
    .big-font { font-size: 18px !important; font-weight: bold; }
    .activity-box { 
        padding: 15px; 
        background-color: #f0f2f6; 
        border-radius: 10px; 
        border-left: 5px solid #00704A; 
        margin-bottom: 20px;
    }
    .activity-title { font-weight: bold; color: #00704A; font-size: 1.1em; }
</style>
""", unsafe_allow_html=True)

# --- 2. 資料定義 ---
HOLIDAYS_2026 = {
    "2026-01-01": "🔴 元旦", "2026-02-16": "🔴 小年夜", "2026-02-17": "🔴 除夕",
    "2026-02-18": "🔴 春節", "2026-02-19": "🔴 春節", "2026-02-20": "🔴 春節",
    "2026-02-28": "🔴 228紀念日", "2026-04-03": "🔴 兒童節(補)", "2026-04-04": "🔴 兒童節",
    "2026-04-05": "🔴 清明節", "2026-04-06": "🔴 清明節(補)", "2026-05-01": "🔴 勞動節",
    "2026-06-19": "🔴 端午節", "2026-09-25": "🔴 中秋節", "2026-10-10": "🔴 國慶日",
}

MARKETING_CALENDAR = {
    "2026-01-01": "🎁 買飲料券送紅包袋開始",
    "2026-01-02": "☕ 新年好友分享日(BAF)",
    "2026-01-03": "⭐ 週末好星情(滿800贈8星)",
    "2026-01-04": "⭐ 週末好星情(滿800贈8星)",
    "2026-01-07": "🎫 金星好友分享(券)",
    "2026-01-08": "🎫 金星好友分享(券)",
    "2026-01-09": "🎫 金星好友分享(券)",
    "2026-01-10": "⭐ 週末好星情(滿800贈8星)",
    "2026-01-11": "⭐ 週末好星情(滿800贈8星)",
    "2026-01-12": "☕ 指定飲料好友分享",
    "2026-01-13": "🌟 金星雙倍贈星 | ☕ 指定BAF",
    "2026-01-14": "🧸 夾娃娃機加購開賣",
    "2026-01-15": "🐼 外送考生應援BAF",
    "2026-01-16": "☕ 學測應援BAF | ⭐ 滿888贈8星",
    "2026-01-17": "⭐ 滿888贈8星",
    "2026-01-18": "⭐ 滿888贈8星",
    "2026-01-19": "⭐ 滿888贈8星",
    "2026-01-20": "☕ 擁抱溫暖BAF | ⭐ 滿888贈8星",
    "2026-01-21": "☕ 擁抱溫暖BAF | ⭐ 喜迎新年(滿千贈15星)",
    "2026-01-22": "⭐ 喜迎新年(滿千贈15星)",
    "2026-01-23": "⭐ 喜迎新年(滿千贈15星)",
    "2026-01-24": "⭐ 週末好星情(滿800贈8星)",
    "2026-01-25": "⭐ 週末好星情(滿800贈8星)",
    "2026-01-26": "☕ 星享成雙BAF(買二送二)",
    "2026-01-27": "☕ 星享成雙BAF(買二送二)",
    "2026-01-28": "☕ 星享成雙BAF(買二送二)",
    "2026-01-29": "🍰 歡樂食光(飲+糕贈8星)",
    "2026-01-30": "🍰 歡樂食光(飲+糕贈8星)",
    "2026-01-31": "⭐ 週末好星情(滿800贈8星)",
    "2026-02-01": "⭐ 週末好星情(滿800贈8星)",
    "2026-02-02": "☕ 尾牙BAF",
    "2026-02-03": "☕ 尾牙BAF",
    "2026-02-04": "🌟 金星雙倍贈星",
}

def get_date_display(date_input):
    try:
        if isinstance(date_input, str):
            date_obj = pd.to_datetime(date_input).date()
        else:
            date_obj = date_input
        date_str = str(date_obj)
        week_str = ["(一)", "(二)", "(三)", "(四)", "(五)", "(六)", "(日)"][date_obj.weekday()]
        if date_str in HOLIDAYS_2026:
            return f"{date_obj.strftime('%m/%d')} {week_str} {HOLIDAYS_2026[date_str]}"
        if date_obj.weekday() >= 5:
            return f"{date_obj.strftime('%m/%d')} {week_str} 🟠"
        return f"{date_obj.strftime('%m/%d')} {week_str}"
    except:
        return str(date_input)

def get_event_info(date_input):
    d_str = str(date_input)
    return MARKETING_CALENDAR.get(d_str, "")

# --- 3. Google Sheet 連線與資料處理 (Robust Version) ---
def get_gspread_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    try:
        creds_dict = dict(st.secrets["gcp_service_account"]) if "gcp_service_account" in st.secrets else dict(st.secrets)
        if "private_key" in creds_dict: creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"❌ 連線認證錯誤：{str(e)}")
        st.stop()

def initialize_sheet(sheet):
    date_range = pd.date_range(start="2026-01-01", end="2026-12-31", freq="D")
    cols = ['日期', '目標PSD', '實績PSD', 'PSD達成率', 'ADT', 'AT', '糕點PSD', '糕點USD', '糕點報廢USD', 'Retail', 'NCB', 'BAF', '節慶USD', '備註']
    df = pd.DataFrame(columns=cols)
    df['日期'] = date_range.astype(str)
    df = df.fillna(0)
    df['備註'] = ""
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.values.tolist())
    return df

@st.cache_data(ttl=60)
def load_kpi_data():
    """讀取核心業績"""
    try:
        client = get_gspread_client()
        spreadsheet = client.open("Jiaoxi_2026_Data")
        sheet = spreadsheet.sheet1 
        data = sheet.get_all_records()
        
        if not data: return initialize_sheet(sheet)
        
        df = pd.DataFrame(data)
        required = ['日期', '目標PSD', '實績PSD']
        if not all(c in df.columns for c in required): return initialize_sheet(sheet)
        
        df["日期"] = pd.to_datetime(df["日期"]).dt.date
        numeric_cols = ['目標PSD', '實績PSD', 'PSD達成率', 'ADT', 'AT', '糕點PSD', '糕點USD', '糕點報廢USD', 'Retail', 'NCB', 'BAF', '節慶USD']
        for col in numeric_cols:
            if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        df["當日活動"] = df["日期"].apply(lambda x: get_event_info(x))
        return df
    except Exception as e:
        st.error(f"⚠️ 核心業績資料讀取失敗 (請檢查網路或 Sheet): {e}")
        return pd.DataFrame()

@st.cache_data(ttl=60)
def load_festival_data():
    """讀取節慶禮盒"""
    try:
        client = get_gspread_client()
        spreadsheet = client.open("Jiaoxi_2026_Data")
        try:
            sheet = spreadsheet.worksheet("Festival_Control")
            data = sheet.get_all_records()
            # 若無資料，回傳空表結構
            cols = ['檔期', '品項名稱', '目標控量(總量)', '已訂貨(入庫)', '調入(+)', '調出(-)', '目前庫存(估)', '備註']
            if not data: return pd.DataFrame(columns=cols)
            
            df = pd.DataFrame(data)
            num_cols = ['目標控量(總量)', '已訂貨(入庫)', '調入(+)', '調出(-)']
            for c in num_cols:
                 if c in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
            
        except gspread.WorksheetNotFound:
            return None # 標記為未建立
            
    except Exception as e:
        # 回傳空表避免當機
        return pd.DataFrame()

def save_data(df, target="kpi"):
    try:
        client = get_gspread_client()
        spreadsheet = client.open("Jiaoxi_2026_Data")
        
        if target == "kpi":
            sheet = spreadsheet.sheet1
            save_cols = ['日期', '目標PSD', '實績PSD', 'PSD達成率', 'ADT', 'AT', '糕點PSD', '糕點USD', '糕點報廢USD', 'Retail', 'NCB', 'BAF', '節慶USD', '備註']
            # [重要修正] 強制填滿空值，避免 NaN 導致存檔失敗
            save_df = df[save_cols].copy().fillna(0)
            save_df["備註"] = save_df["備註"].astype(str).replace("0", "") # 備註不填0
            save_df["日期"] = save_df["日期"].astype(str)
            
            sheet.clear()
            sheet.update([save_df.columns.values.tolist()] + save_df.values.tolist())
            
        elif target == "festival":
            try:
                sheet = spreadsheet.worksheet("Festival_Control")
            except gspread.WorksheetNotFound:
                sheet = spreadsheet.add_worksheet(title="Festival_Control", rows="100", cols="20")
            
            # [重要修正] 強制填滿空值
            save_cols = ['檔期', '品項名稱', '目標控量(總量)', '已訂貨(入庫)', '調入(+)', '調出(-)', '目前庫存(估)', '備註']
            save_df = df[save_cols].copy()
            
            # 數值欄位填 0
            num_cols = ['目標控量(總量)', '已訂貨(入庫)', '調入(+)', '調出(-)', '目前庫存(估)']
            for c in num_cols:
                if c in save_df.columns: save_df[c] = pd.to_numeric(save_df[c], errors='coerce').fillna(0)
            
            # 文字欄位填空字串
            str_cols = ['檔期', '品項名稱', '備註']
            for c in str_cols:
                if c in save_df.columns: save_df[c] = save_df[c].fillna("").astype(str)

            sheet.clear()
            sheet.update([save_df.columns.values.tolist()] + save_df.values.tolist())
            
        st.toast("✅ 數據已更新！", icon="💾")
        st.cache_data.clear()
    except Exception as e:
        st.error(f"儲存失敗 (詳細錯誤): {e}")

# --- 4. 主程式 ---

with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/zh/d/df/Starbucks_Corporation_Logo_2011.svg", width=100)
    st.title("營運控制台")
    if st.button("🔄 重新讀取資料"):
        st.cache_data.clear()
        st.rerun()
    st.markdown("""
    **符號說明：**
    * 🔴 **國定假日**
    * 🟠 **週末**
    * ⭐ **星禮程/會員活動**
    * ☕ **好友分享/BAF**
    """)

# --- 頂部活動大布告欄 ---
tw_tz = datetime.timezone(datetime.timedelta(hours=8))
today = datetime.datetime.now(tw_tz).date()

today_event = get_event_info(today)
if not today_event: today_event = "無特別活動，回歸基本面銷售。"

upcoming_text = []
for i in range(1, 4):
    future_date = today + datetime.timedelta(days=i)
    evt = get_event_info(future_date)
    if evt:
        d_str = future_date.strftime('%m/%d')
        upcoming_text.append(f"<b>{d_str}</b>: {evt}")

st.title("☕ 2026 礁溪門市營運戰情室")

st.markdown(f"""
<div class="activity-box">
    <div class="activity-title">📢 門市活動快訊 (Today: {today.strftime('%m/%d')})</div>
    <div style="font-size: 1.5em; color: #333; margin: 10px 0;">👉 今日重點：{today_event}</div>
    <hr style="border-top: 1px dashed #ccc;">
    <div style="color: #666;">
        <b>🔜 未來預告：</b> {' &nbsp;|&nbsp; '.join(upcoming_text) if upcoming_text else "近期無大型檔期"}
    </div>
</div>
""", unsafe
