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
            creds_dict = dict(st.secrets["gcp_service_account"])
        elif "private_key" in st.secrets:
            creds_dict = dict(st.secrets)
        else:
            st.error("❌ 連線失敗：Secrets 內容無法辨識。")
            st.stop()

        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open("Jiaoxi_2026_Data").sheet1
        return sheet
    except Exception as e:
        st.error(f"❌ 連線錯誤：{str(e)}")
        st.stop()

def initialize_sheet(sheet):
    """初始化結構"""
    date_range = pd.date_range(start="2026-01-01", end="2026-12-31", freq="D")
    cols = ['日期', '目標PSD', '實績PSD', 'PSD達成率', 'ADT', 'AT', '糕點PSD', '糕點USD', '糕點報廢USD', 'Retail', 'NCB', 'BAF', '節慶USD', '備註']
    df = pd.DataFrame(columns=cols)
    df['日期'] = date_range.astype(str)
    for c in cols:
        if c == '備註': df[c] = ""
        elif c != '日期': df[c] = 0
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.values.tolist())
    return df

@st.cache_data(ttl=60)
def load_data():
    try:
        sheet = get_google_sheet_data()
        data = sheet.get_all_records()
        
        if not data:
            df = initialize_sheet(sheet)
            df["日期"] = pd.to_datetime(df["日期"]).dt.date
            return df

        df = pd.DataFrame(data)
        required_cols = ['日期', '目標PSD', '實績PSD', 'NCB', 'BAF'] 
        if not all(col in df.columns for col in required_cols):
            st.error("偵測到舊格式，正在升級欄位...")
            df = initialize_sheet(sheet)
        
        # 強制轉日期格式
        df["日期"] = pd.to_datetime(df["日期"]).dt.date
        
        # 強制轉數值格式 (避免達成率變成文字無法顯示)
        numeric_cols = ['目標PSD', '實績PSD', 'PSD達成率', 'ADT', 'AT', '糕點PSD', '糕點USD', '糕點報廢USD', 'Retail', 'NCB', 'BAF', '節慶USD']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
        return df

    except Exception as e:
        st.error(f"讀取錯誤: {e}")
        return pd.DataFrame()

def save_data_to_sheet(df):
    try:
        sheet = get_google_sheet_data()
        save_cols = ['日期', '目標PSD', '實績PSD', 'PSD達成率', 'ADT', 'AT', '糕點PSD', '糕點USD', '糕點報廢USD', 'Retail', 'NCB', 'BAF', '節慶USD', '備註']
        save_df = df[save_cols].copy()
        save_df["日期"] = save_df["日期"].astype(str)
        save_df = save_df.fillna(0)
        sheet.clear()
        sheet.update([save_df.columns.values.tolist()] + save_df.values.tolist())
        st.toast("✅ 數據已更新！", icon="💾")
        st.cache_data.clear()
    except Exception as e:
        st.error(f"儲存失敗: {e}")

# --- 4. 主程式 ---

with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/zh/d/df/Starbucks_Corporation_Logo_2011.svg", width=100)
    st.title("營運控制台")
    if st.button("🔄 重新讀取資料"):
        st.cache_data.clear()
        st.rerun()
    st.markdown("""
    **日期標示說明：**
    * 🔴 **國定假日**
    * 🟠 **週末 (六/日)**
    * ⚪ **平日 (一~五)**
    """)

st.title("☕ 2026 礁溪門市營運報表")

if "df" not in st.session_state:
    st.session_state.df = load_data()

df = st.session_state.df
if df.empty: st.stop()

current_month = datetime.date.today().month
selected_month = st.selectbox("月份", range(1, 13), index=current_month-1)

df["Month"] = pd.to_datetime(df["日期"]).dt.month
current_month_df = df[df["Month"] == selected_month].copy()

if not current_month_df.empty:
    current_month_df["顯示日期"] = current_month_df["日期"].apply(get_date_display)
else:
    current_month_df["顯示日期"] = []

# 數據輸入區
st.subheader(f"📝 {selected_month} 月數據輸入")

tab1, tab2 = st.tabs(["📊 核心業績 (PSD/ADT/AT)", "🥐 商品與庫存 (Product/Waste)"])

with tab1:
    st.caption("輸入說明：請輸入「每日業績」與「來客數」，按下【確認更新】後，系統會自動算出達成率與客單價。")
    
    edited_kpi = st.data_editor(
        current_month_df[['顯示日期', '日期', '目標PSD', '實績PSD', 'PSD達成率', 'ADT', 'AT', '備註']],
        column_config={
            "顯示日期": st.column_config.TextColumn("日期 (星期)", disabled=True, width="medium"),
            "日期": None,
            
            "目標PSD": st.column_config.NumberColumn("每日業績目標 ($)", format="$%d", min_value=0),
            "實績PSD": st.column_config.NumberColumn("每日實績業績 ($)", format="$%d", min_value=0),
            
            # --- 設定達成率顯示格式 ---
            "PSD達成率": st.column_config.NumberColumn("達成率 %", disabled=True, format="%.1f%%"),
            
            "ADT": st.column_config.NumberColumn("每日來客數 (人)", format="%d", min_value=0),
            "AT": st.column_config.NumberColumn("客單價 AT (整數)", disabled=True, format="$%d"),
            "備註": st.column_config.TextColumn(width="medium"),
        },
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        key="editor_kpi"
    )

with tab2:
    st.caption("輸入說明：糕點、Retail、BAF、節慶")
    edited_prod = st.data_editor(
        current_month_df[['顯示日期', '日期', '糕點PSD', '糕點USD', '糕點報廢USD', 'Retail', 'NCB', 'BAF', '節慶USD']],
        column_config={
            "顯示日期": st.column_config.TextColumn("日期 (星期)", disabled=True, width="medium"),
            "日期": None,
            
            "糕點PSD": st.column_config.NumberColumn("糕點業績 PSD", format="$%d"),
            "糕點USD": st.column_config.NumberColumn("糕點銷量 USD", format="%d"),
            "糕點報廢USD": st.column_config.NumberColumn("糕點報廢 USD", format="%d"),
            "Retail": st.column_config.NumberColumn("Retail 商品", format="$%d"),
            "NCB": st.column_config.NumberColumn("NCB (杯)", format="%d"),
            "BAF": st.column_config.NumberColumn("BAF/SCHP (張)", format="%d"),
            "節慶USD": st.column_config.NumberColumn("節慶禮盒/蛋糕", format="%d"),
        },
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        key="editor_prod"
    )

# 儲存按鈕
if st.button("💾 確認更新 (並自動計算)", type="primary"):
    # Tab 1 更新
    for i, row in edited_kpi.iterrows():
        # 強制將 row["日期"] 轉為 date 物件，確保與 df["日期"] 格式一致
        row_date = pd.to_datetime(row["日期"]).date() if isinstance(row["日期"], (str, pd.Timestamp)) else row["日期"]
        
        mask = df["日期"] == row_date
        
        if mask.any(): # 確保有找到對應日期
            df.loc[mask, "目標PSD"] = row["目標PSD"]
            df.loc[mask, "實績PSD"] = row["實績PSD"]
            df.loc[mask, "ADT"] = row["ADT"]
            df.loc[mask, "備註"] = row["備註"]
            
            # --- 關鍵修正：確保計算結果是浮點數 ---
            # 實績 / 目標 * 100
            t_psd = float(row["目標PSD"]) if row["目標PSD"] > 0 else 1.0
            actual_psd = float(row["實績PSD"])
            
            # 計算並取小數點後1位
            achievement = round((actual_psd / t_psd) * 100, 1)
            df.loc[mask, "PSD達成率"] = achievement
            
            # 客單價運算
            cust = float(row["ADT"]) if row["ADT"] > 0 else 1.0
            at_val = actual_psd / cust if row["ADT"] > 0 else 0
            df.loc[mask, "AT"] = int(round(at_val, 0))

    # Tab 2 更新
    for i, row in edited_prod.iterrows():
        row_date = pd.to_datetime(row["日期"]).date() if isinstance(row["日期"], (str, pd.Timestamp)) else row["日期"]
        mask = df["日期"] == row_date
        cols = ['糕點PSD', '糕點USD', '糕點報廢USD', 'Retail', 'NCB', 'BAF', '節慶USD']
        for c in cols: df.loc[mask, c] = row[c]

    # 存檔與更新 Session
    save_data_to_sheet(df)
    st.session_state.df = df
    
    # --- 關鍵：強制重新載入頁面，讓計算結果立刻顯示 ---
    st.rerun()

# --- 儀表板 (新版：分為績效看板與關鍵指標) ---
st.markdown("---")

# 1. 基礎運算邏輯
# 找出「有效營業日」：只計算實績 PSD > 0 的天數，避免平均值被未來的空白日拉低
valid_days_df = current_month_df[current_month_df["實績PSD"] > 0]
days_count = valid_days_df.shape[0]

# 避免除以 0 的保護機制
if days_count == 0: 
    days_count = 1
    safe_valid_df = current_month_df  # 若完全無數據，暫時用全表避免報錯(雖然都是0)
else:
    safe_valid_df = valid_days_df

# --- 數據計算區 ---

# [Section 1] 績效看板數據
total_sales_actual = current_month_df["實績PSD"].sum()          # 累積 SALES
total_sales_target = current_month_df["目標PSD"].sum()
achieve_rate = (total_sales_actual / total_sales_target * 100) if total_sales_target > 0 else 0 # 達成率
avg_psd = total_sales_actual / days_count                       # 平均 PSD
avg_adt = safe_valid_df["ADT"].mean()                           # 平均 ADT (筆)
# 平均 AT = 總業績 / 總來客數 (這樣比每日AT平均更準確)
total_adt = current_month_df["ADT"].sum()
avg_at = total_sales_actual / total_adt if total_adt > 0 else 0 # 平均 AT

# [Section 2] 關鍵指標數據
avg_pastry_psd = safe_valid_df["糕點PSD"].mean()         # 平均糕點 PSD (元)
avg_pastry_usd = safe_valid_df["糕點USD"].mean()         # 平均糕點 USD (個)
avg_waste_usd = safe_valid_df["糕點報廢USD"].mean()      # 平均糕點報廢 USD (個)
avg_ncb = safe_valid_df["NCB"].mean()                    # 平均 NCB (杯)
avg_retail = safe_valid_df["Retail"].mean()              # 平均 Retail (元)

# --- 畫面呈現區 ---

# 1. 本月績效看板
st.subheader("🏆 本月績效看板")
m1, m2, m3, m4, m5 = st.columns(5)

m1.metric("累積 SALES", f"${total_sales_actual:,.0f}")
m2.metric("累積達成率", f"{achieve_rate:.1f}%", delta=f"${total_sales_actual - total_sales_target:,.0f}")
m3.metric("平均 PSD", f"${avg_psd:,.0f}")
m4.metric("平均 ADT", f"{avg_adt:,.0f} 筆")
m5.metric("平均 AT", f"${avg_at:,.0f}")

# 2. 關鍵指標
st.subheader("⚡ 關鍵指標 (Daily Average)")
k1, k2, k3, k4, k5 = st.columns(5)

k1.metric("平均糕點 PSD", f"${avg_pastry_psd:,.0f}")
k2.metric("平均糕點 USD", f"{avg_pastry_usd:,.1f} 個")
k3.metric("平均糕點報廢", f"{avg_waste_usd:,.1f} 個", delta_color="inverse") # 報廢顯示紅色(inverse)提醒
k4.metric("平均 NCB", f"{avg_ncb:,.1f} 杯")
k5.metric("平均 Retail", f"${avg_retail:,.0f}")
