import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import json

# --- 1. 設定網頁與樣式 ---
st.set_page_config(page_title="星巴克礁溪門市 | 營運報表", page_icon="☕", layout="wide")

st.markdown("""
<style>
    .stNumberInput input { padding: 0px 5px; }
    div[data-testid="stMetricValue"] { font-size: 1.2rem; }
    .big-font { font-size: 18px !important; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- 2. Google Sheet 連線設定 ---
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
    """初始化試算表結構"""
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
            st.warning("偵測到新格式，正在初始化試算表... (請稍候)")
            df = initialize_sheet(sheet)
            df["日期"] = pd.to_datetime(df["日期"]).dt.date
            return df

        df = pd.DataFrame(data)
        
        # 檢查欄位
        required_cols = ['日期', '目標PSD', '實績PSD', 'NCB', 'BAF'] 
        if not all(col in df.columns for col in required_cols):
            st.error("試算表欄位與新格式不符，正在進行格式升級...")
            df = initialize_sheet(sheet)
            df["日期"] = pd.to_datetime(df["日期"]).dt.date
            return df
            
        df["日期"] = pd.to_datetime(df["日期"]).dt.date
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

# --- 3. 主程式 ---

with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/zh/d/df/Starbucks_Corporation_Logo_2011.svg", width=100)
    st.title("營運控制台")
    if st.button("🔄 重新讀取資料"):
        st.cache_data.clear()
        st.rerun()
    st.info("💡 資料與 Google Sheet 即時同步")

st.title("☕ 2026 礁溪門市營運報表")

if "df" not in st.session_state:
    st.session_state.df = load_data()

df = st.session_state.df

if df.empty:
    st.stop()

# 月份選擇
current_month = datetime.date.today().month
selected_month = st.selectbox("月份", range(1, 13), index=current_month-1)

df["Month"] = pd.to_datetime(df["日期"]).dt.month
current_month_df = df[df["Month"] == selected_month].copy()

# 數據輸入區
st.subheader(f"📝 {selected_month} 月數據輸入")

tab1, tab2 = st.tabs(["📊 核心業績 (PSD/ADT/AT)", "🥐 商品與庫存 (Product/Waste)"])

with tab1:
    st.caption("輸入說明：請輸入「每日業績」與「來客數」，系統將自動計算「客單價」。")
    
    edited_kpi = st.data_editor(
        current_month_df[['日期', '目標PSD', '實績PSD', 'PSD達成率', 'ADT', 'AT', '備註']],
        column_config={
            "日期": st.column_config.DateColumn(disabled=True, width="small"),
            
            # --- 核心邏輯修正 ---
            "目標PSD": st.column_config.NumberColumn("每日業績目標 ($)", format="$%d", min_value=0),
            "實績PSD": st.column_config.NumberColumn("每日實績業績 ($)", format="$%d", min_value=0),
            
            "PSD達成率": st.column_config.NumberColumn("業績達成率 %", disabled=True, format="%.1f%%"),
            
            "ADT": st.column_config.NumberColumn("每日來客數 (人)", format="%d", min_value=0),
            "AT": st.column_config.NumberColumn("客單價 AT (系統自動算)", disabled=True, format="$%.1f"),
            
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
        current_month_df[['日期', '糕點PSD', '糕點USD', '糕點報廢USD', 'Retail', 'NCB', 'BAF', '節慶USD']],
        column_config={
            "日期": st.column_config.DateColumn(disabled=True),
            
            "糕點PSD": st.column_config.NumberColumn("糕點業績 PSD (元)", format="$%d"),
            "糕點USD": st.column_config.NumberColumn("糕點銷量 USD (個)", format="%d"),
            "糕點報廢USD": st.column_config.NumberColumn("糕點報廢 USD (個)", format="%d"),
            "Retail": st.column_config.NumberColumn("Retail 商品 (元)", format="$%d"),
            "NCB": st.column_config.NumberColumn("NCB (元)", format="$%d"),
            "BAF": st.column_config.NumberColumn("BAF/SCHP (張)", format="%d"),
            "節慶USD": st.column_config.NumberColumn("節慶禮盒/蛋糕 (個)", format="%d"),
        },
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        key="editor_prod"
    )

# 儲存按鈕 (包含運算邏輯)
if st.button("💾 確認更新 (並自動計算客單價)", type="primary"):
    # Tab 1: 業績與來客 (含自動計算)
    for i, row in edited_kpi.iterrows():
        mask = df["日期"] == row["日期"]
        
        # 1. 寫入使用者輸入的數值
        df.loc[mask, "目標PSD"] = row["目標PSD"]
        df.loc[mask, "實績PSD"] = row["實績PSD"]
        df.loc[mask, "ADT"] = row["ADT"] # 這是來客數
        df.loc[mask, "備註"] = row["備註"]
        
        # 2. 自動計算：PSD達成率 (實績業績 / 目標業績)
        t_psd = row["目標PSD"] if row["目標PSD"] > 0 else 1
        df.loc[mask, "PSD達成率"] = round(row["實績PSD"] / t_psd * 100, 1)
        
        # 3. 自動計算：客單價 AT (實績業績 / 實績來客數)
        # 防止除以 0
        customer_count = row["ADT"] if row["ADT"] > 0 else 1
        calculated_at = row["實績PSD"] / customer_count
        # 如果來客數是 0，客單價就是 0
        if row["ADT"] == 0: calculated_at = 0
            
        df.loc[mask, "AT"] = round(calculated_at, 1)

    # Tab 2: 商品 (直接寫入)
    for i, row in edited_prod.iterrows():
        mask = df["日期"] == row["日期"]
        cols = ['糕點PSD', '糕點USD', '糕點報廢USD', 'Retail', 'NCB', 'BAF', '節慶USD']
        for c in cols: df.loc[mask, c] = row[c]

    save_data_to_sheet(df)
    st.session_state.df = df
    st.success("已儲存！客單價 (AT) 與達成率已自動更新。")

# 儀表板
st.markdown("---")
st.subheader("📈 關鍵指標分析")

# 總業績
total_sales_target = current_month_df["目標PSD"].sum()
total_sales_actual = current_month_df["實績PSD"].sum()
sales_achieve_rate = (total_sales_actual / total_sales_target * 100) if total_sales_target > 0 else 0

# 總來客數 (ADT)
total_visitors = current_month_df["ADT"].sum()

# 平均客單價 (總業績 / 總來客)
avg_at = total_sales_actual / total_visitors if total_visitors > 0 else 0

total_food_sales = current_month_df["糕點PSD"].sum()
total_waste_unit = current_month_df["糕點報廢USD"].sum()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("業績達成率 (PSD)", f"{sales_achieve_rate:.1f}%", delta=f"${total_sales_actual - total_sales_target:,.0f}")
c2.metric("總來客數 (ADT)", f"{total_visitors:,.0f} 人")
c3.metric("平均客單價 (AT)", f"${avg_at:.0f}")
c4.metric("糕點總業績", f"${total_food_sales:,.0f}")
c5.metric("糕點報廢量", f"{total_waste_unit:,.0f} 個", delta_color="inverse")
