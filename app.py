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

# --- 2. Google Sheet 連線設定 ---
def get_google_sheet_data():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Jiaoxi_2026_Data").sheet1
    return sheet

def initialize_sheet(sheet):
    """
    初始化試算表結構
    欄位：日期, 目標PSD, 實績PSD, PSD達成率, ADT, AT, 糕點PSD, 糕點USD, 
         糕點報廢USD, Retail, NCB, BAF, 節慶USD, 備註
    """
    date_range = pd.date_range(start="2026-01-01", end="2026-12-31", freq="D")
    
    # 您指定的專屬欄位
    cols = [
        '日期', '目標PSD', '實績PSD', 'PSD達成率', 'ADT', 'AT', 
        '糕點PSD', '糕點USD', '糕點報廢USD', 'Retail', 'NCB', 'BAF', 
        '節慶USD', '備註'
    ]
    
    # 建立 DataFrame
    df = pd.DataFrame(columns=cols)
    df['日期'] = date_range.astype(str)
    
    # 填入預設值
    for c in cols:
        if c == '備註':
            df[c] = ""
        elif c != '日期':
            df[c] = 0
            
    # 清空並寫入 Google Sheet
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.values.tolist())
    return df

@st.cache_data(ttl=60)
def load_data():
    try:
        sheet = get_google_sheet_data()
        data = sheet.get_all_records()
        
        # 如果是空的，直接初始化
        if not data:
            st.warning("偵測到新格式，正在初始化試算表... (請稍候)")
            df = initialize_sheet(sheet)
            df["日期"] = pd.to_datetime(df["日期"]).dt.date
            return df

        df = pd.DataFrame(data)
        
        # 檢查關鍵欄位是否存在，若缺少則視為舊格式需更新
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
        # 只保留指定的欄位順序進行存檔
        save_cols = [
            '日期', '目標PSD', '實績PSD', 'PSD達成率', 'ADT', 'AT', 
            '糕點PSD', '糕點USD', '糕點報廢USD', 'Retail', 'NCB', 'BAF', 
            '節慶USD', '備註'
        ]
        
        # 確保 DataFrame 只有這些欄位
        save_df = df[save_cols].copy()
        save_df["日期"] = save_df["日期"].astype(str)
        save_df = save_df.fillna(0)
        
        sheet.clear() # 清除舊資料以確保欄位乾淨
        sheet.update([save_df.columns.values.tolist()] + save_df.values.tolist())
        st.toast("✅ 數據已更新！", icon="💾")
        st.cache_data.clear()
    except Exception as e:
        st.error(f"儲存失敗: {e}")

# --- 3. 登入邏輯 ---
USERS = {"SM": "sm2026", "SS": "coffee123"}
if "authenticated" not in st.session_state: st.session_state.authenticated = False

if not st.session_state.authenticated:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔒 礁溪門市登入")
        u = st.text_input("User")
        p = st.text_input("Password", type="password")
        if st.button("Login"):
            if u in USERS and USERS[u] == p:
                st.session_state.authenticated = True
                st.session_state.role = "SM" if u == "SM" else "SS"
                st.rerun()
else:
    # --- 4. 主畫面 ---
    with st.sidebar:
        st.success(f"Hi, {st.session_state.role}")
        if st.button("🔄 重新整理"):
            st.cache_data.clear()
            st.rerun()
        st.info("💡 格式已更新為：PSD / ADT / 分類業績")

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

    # SS 權限控制 (鎖定目標PSD)
    disabled_target = True if st.session_state.role == "SS" else False

    st.subheader(f"📝 {selected_month} 月數據輸入")
    
    # 分頁設計：依據您的新欄位分類
    tab1, tab2 = st.tabs(["📊 PSD & KPI (來客/客單)", "🥐 商品銷售 (Product Sales)"])
    
    with tab1:
        st.caption("填寫：目標/實績PSD、ADT、AT")
        edited_kpi = st.data_editor(
            current_month_df[['日期', '目標PSD', '實績PSD', 'PSD達成率', 'ADT', 'AT', '備註']],
            column_config={
                "日期": st.column_config.DateColumn(disabled=True, width="small"),
                "目標PSD": st.column_config.NumberColumn("目標 PSD", disabled=disabled_target),
                "實績PSD": st.column_config.NumberColumn("實績 PSD"),
                "PSD達成率": st.column_config.NumberColumn("達成率 %", disabled=True, format="%.1f%%"),
                "ADT": st.column_config.NumberColumn("ADT", format="$%.1f"),
                "AT": st.column_config.NumberColumn("AT", format="%.2f"),
                "備註": st.column_config.TextColumn(width="medium"),
            },
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            key="editor_kpi"
        )

    with tab2:
        st.caption("填寫：糕點、Retail、NCB、BAF、節慶")
        edited_prod = st.data_editor(
            current_month_df[['日期', '糕點PSD', '糕點USD', '糕點報廢USD', 'Retail', 'NCB', 'BAF', '節慶USD']],
            column_config={
                "日期": st.column_config.DateColumn(disabled=True),
                "糕點PSD": st.column_config.NumberColumn("糕點PSD"),
                "糕點USD": st.column_config.NumberColumn("糕點 $", format="$%d"),
                "糕點報廢USD": st.column_config.NumberColumn("報廢 $", format="$%d"),
                "Retail": st.column_config.NumberColumn("Retail $", format="$%d"),
                "NCB": st.column_config.NumberColumn("NCB $", format="$%d"),
                "BAF": st.column_config.NumberColumn("BAF $", format="$%d"),
                "節慶USD": st.column_config.NumberColumn("節慶 $", format="$%d"),
            },
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            key="editor_prod"
        )

    # --- 儲存與運算 ---
    if st.button("💾 確認更新", type="primary"):
        # 合併 Tab 1 的修改
        for i, row in edited_kpi.iterrows():
            mask = df["日期"] == row["日期"]
            df.loc[mask, "目標PSD"] = row["目標PSD"]
            df.loc[mask, "實績PSD"] = row["實績PSD"]
            df.loc[mask, "ADT"] = row["ADT"]
            df.loc[mask, "AT"] = row["AT"]
            df.loc[mask, "備註"] = row["備註"]
            
            # 自動計算 PSD 達成率
            t_psd = row["目標PSD"] if row["目標PSD"] > 0 else 1
            df.loc[mask, "PSD達成率"] = round(row["實績PSD"] / t_psd * 100, 1)

        # 合併 Tab 2 的修改
        for i, row in edited_prod.iterrows():
            mask = df["日期"] == row["日期"]
            cols = ['糕點PSD', '糕點USD', '糕點報廢USD', 'Retail', 'NCB', 'BAF', '節慶USD']
            for c in cols:
                df.loc[mask, c] = row[c]

        save_data_to_sheet(df)
        st.session_state.df = df
        st.success("已儲存！")

    # --- 儀表板 ---
    st.markdown("---")
    st.subheader("📈 關鍵指標分析")
    
    # 統計運算
    total_target_psd = current_month_df["目標PSD"].sum()
    total_actual_psd = current_month_df["實績PSD"].sum()
    psd_rate = (total_actual_psd / total_target_psd * 100) if total_target_psd > 0 else 0
    
    # 預估業績 (PSD * ADT) - 因為沒有直接的業績欄位，我們用加權平均估算
    # 或者單純顯示各項總和
    total_food = current_month_df["糕點USD"].sum()
    total_retail = current_month_df["Retail"].sum()
    total_ncb = current_month_df["NCB"].sum()
    total_waste = current_month_df["糕點報廢USD"].sum()
    
    c1, c2, c3, c4, c5 = st.columns(5)
    
    c1.metric("PSD 達成率", f"{psd_rate:.1f}%", delta=f"{total_actual_psd - total_target_psd:,.0f} 人")
    c2.metric("糕點總業績", f"${total_food:,.0f}")
    c3.metric("Retail 總業績", f"${total_retail:,.0f}")
    c4.metric("NCB 總業績", f"${total_ncb:,.0f}")
    c5.metric("糕點報廢", f"${total_waste:,.0f}", delta_color="inverse")
