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
            "糕點報廢USD": st.column_config.NumberColumn("糕點報廢 USD (個)", format="%d"),
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
        row_date = pd.to_datetime(row["日期"]).date() if isinstance(row["日期"], (str, pd.Timestamp)) else row["日期"]
        
        mask = df["日期"] == row_date
        
        if mask.any():
            df.loc[mask, "目標PSD"] = row["目標PSD"]
            df.loc[mask, "實績PSD"] = row["實績PSD"]
            df.loc[mask, "ADT"] = row["ADT"]
            df.loc[mask, "備註"] = row["備註"]
            
            t_psd = float(row["目標PSD"]) if row["目標PSD"] > 0 else 1.0
            actual_psd = float(row["實績PSD"])
            
            achievement = round((actual_psd / t_psd) * 100, 1)
            df.loc[mask, "PSD達成率"] = achievement
            
            cust = float(row["ADT"]) if row["ADT"] > 0 else 1.0
            at_val = actual_psd / cust if row["ADT"] > 0 else 0
            df.loc[mask, "AT"] = int(round(at_val, 0))

    # Tab 2 更新
    for i, row in edited_prod.iterrows():
        row_date = pd.to_datetime(row["日期"]).date() if isinstance(row["日期"], (str, pd.Timestamp)) else row["日期"]
        mask = df["日期"] == row_date
        cols = ['糕點PSD', '糕點USD', '糕點報廢USD', 'Retail', 'NCB', 'BAF', '節慶USD']
        for c in cols: df.loc[mask, c] = row[c]

    save_data_to_sheet(df)
    st.session_state.df = df
    st.rerun()

# --- 儀表板數據計算與篩選區 (已更新：包含週次分析) ---
st.markdown("---")

# 1. 建立週次資料 (輔助欄位)
current_month_df["Week_Num"] = pd.to_datetime(current_month_df["日期"]).dt.isocalendar().week

# 2. 增加「檢視模式」選擇器
st.subheader("📅 數據檢視範圍")
col_view, col_week = st.columns([1, 3])

with col_view:
    view_mode = st.radio("選擇模式", ["全月累計", "單週分析"], horizontal=True, label_visibility="collapsed")

target_df = current_month_df # 預設為全月資料

if view_mode == "單週分析":
    weeks = sorted(current_month_df["Week_Num"].unique())
    week_options = {}
    
    for w in weeks:
        week_data = current_month_df[current_month_df["Week_Num"] == w]
        if not week_data.empty:
            start_date = week_data["日期"].min().strftime("%m/%d")
            end_date = week_data["日期"].max().strftime("%m/%d")
            week_label = f"Week {w} | {start_date} ~ {end_date}"
            week_options[week_label] = w
    
    with col_week:
        if week_options:
            selected_label = st.selectbox("選擇週次", list(week_options.keys()), index=len(week_options)-1)
            selected_week_num = week_options[selected_label]
            target_df = current_month_df[current_month_df["Week_Num"] == selected_week_num]
        else:
            st.warning("本月尚無資料可供分析")

# 3. 基礎運算邏輯
valid_days_df = target_df[target_df["實績PSD"] > 0]
days_count = valid_days_df.shape[0]

if days_count == 0: 
    days_count = 1
    safe_valid_df = target_df 
else:
    safe_valid_df = valid_days_df

# [Section 1] 績效看板數據
total_sales_actual = target_df["實績PSD"].sum()
total_sales_target = target_df["目標PSD"].sum()
achieve_rate = (total_sales_actual / total_sales_target * 100) if total_sales_target > 0 else 0 
avg_psd = total_sales_actual / days_count
avg_adt = safe_valid_df["ADT"].mean()
total_adt = target_df["ADT"].sum()
avg_at = total_sales_actual / total_adt if total_adt > 0 else 0 

# [Section 2] 關鍵指標數據
avg_pastry_psd = safe_valid_df["糕點PSD"].mean()         
avg_pastry_usd = safe_valid_df["糕點USD"].mean()         
avg_waste_usd = safe_valid_df["糕點報廢USD"].mean()      
avg_ncb = safe_valid_df["NCB"].mean()                    
avg_retail = safe_valid_df["Retail"].mean()              

# 顯示目前的檢視狀態
if view_mode == "單週分析":
    if week_options:
        st.info(f"🔍 目前顯示範圍： **{selected_label}** 之數據分析")
else:
    st.success(f"🔍 目前顯示範圍： **{selected_month} 月份全月累計**")

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
k3.metric("平均糕點報廢", f"{avg_waste_usd:,.1f} 個", delta_color="inverse")
k4.metric("平均 NCB", f"{avg_ncb:,.1f} 杯")
k5.metric("平均 Retail", f"${avg_retail:,.0f}")

# --- [新增/修改] AI 全方位分析指令產生器 (高密度格式版) ---
st.markdown("---")
st.subheader("🤖 呼叫 AI 營運顧問 (高密度數據版)")

with st.expander("點擊展開：取得 AI 深度分析指令", expanded=False):
    st.info("💡 說明：已調整為單行高密度格式，包含每日所有指標與區間平均值。")
    
    # 1. 整理標頭資訊
    if view_mode == "單週分析" and week_options:
        period_info = f"2026年 {selected_label}"
    else:
        period_info = f"2026年 {selected_month}月 (全月累計)"
    
    # 2. 建立 AI Prompt 開頭
    ai_prompt = f"""我是星巴克店經理，請協助我分析以下門市數據，並給出具體改善建議。
【分析區間】：{period_info}

【每日詳細營運數據】：
(格式說明：日期: 業績 /達成率/ 來客數 | 客單價 /糕點PSD/糕點USD/報廢USD/Retail/NCB/BAF/節慶)
"""
    
    # 3. 迴圈整理「每日全品項」數據 (高密度格式)
    detail_data = target_df[target_df["實績PSD"] > 0].sort_values("日期")
    
    if not detail_data.empty:
        for idx, row in detail_data.iterrows():
            d_str = row["日期"].strftime("%m/%d")
            
            # 數值準備
            sales = row['實績PSD']
            target = row['目標PSD']
            rate = (sales / target * 100) if target > 0 else 0
            adt = row['ADT']
            at = row['AT']
            p_psd = row['糕點PSD']
            p_usd = row['糕點USD']
            waste = row['糕點報廢USD']
            retail = row['Retail']
            ncb = row['NCB']
            baf = row['BAF']
            fest = row['節慶USD']
            
            # 依照指定格式組裝字串
            line_str = f"{d_str}: 業績${sales:,.0f} /{rate:.1f}%/ 來客{adt}筆 |客單_${at} /糕點PSD_${p_psd:,.0f}/糕點USD_{p_usd}個/ 報廢USD_{waste}個/Retail商品${retail:,.0f}/NCB_{ncb}杯/BAF/SCHP_{baf}張/節慶禮盒/蛋糕_{fest}個/盒"
            ai_prompt += f"{line_str}\n"

        # 4. 計算並加入「區間平均值」 (所有指標的平均)
        # 使用 valid_days_df (已過濾掉沒營業的日子) 來算平均
        if not valid_days_df.empty:
            m_sales = valid_days_df['實績PSD'].mean()
            # 達成率平均建議用 總實績/總目標，比較符合區間概念
            total_act = valid_days_df['實績PSD'].sum()
            total_tgt = valid_days_df['目標PSD'].sum()
            m_rate = (total_act / total_tgt * 100) if total_tgt > 0 else 0
            
            m_adt = valid_days_df['ADT'].mean()
            # 客單價平均建議用 總業績/總來客
            m_at = total_act / valid_days_df['ADT'].sum() if valid_days_df['ADT'].sum() > 0 else 0
            
            m_p_psd = valid_days_df['糕點PSD'].mean()
            m_p_usd = valid_days_df['糕點USD'].mean()
            m_waste = valid_days_df['糕點報廢USD'].mean()
            m_retail = valid_days_df['Retail'].mean()
            m_ncb = valid_days_df['NCB'].mean()
            m_baf = valid_days_df['BAF'].mean()
            m_fest = valid_days_df['節慶USD'].mean()

            ai_prompt += "\n" + "="*30 + "\n"
            ai_prompt += "【區間日平均 (Daily Average)】\n"
            ai_prompt += f"平均展現: 業績${m_sales:,.0f} /{m_rate:.1f}%/ 來客{m_adt:,.0f}筆 |客單_${m_at:.0f} /糕點PSD_${m_p_psd:,.0f}/糕點USD_{m_p_usd:.1f}個/ 報廢USD_{m_waste:.1f}個/Retail商品${m_retail:,.0f}/NCB_{m_ncb:.1f}杯/BAF/SCHP_{m_baf:.1f}張/節慶禮盒/蛋糕_{m_fest:.1f}個/盒"

    else:
        ai_prompt += "(此區間尚無詳細數據)"

    ai_prompt += """
\n請針對上述數據進行週報分析，告訴我本週的營運亮點與機會點。
"""

    # 5. 顯示複製區塊
    st.code(ai_prompt, language="text")
