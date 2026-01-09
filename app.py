import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime

# --- 設定網頁 ---
st.set_page_config(page_title="星巴克礁溪門市 | 戰情儀表板", page_icon="☕", layout="wide")

# 自訂 CSS 讓表格更緊湊
st.markdown("""
<style>
    .stNumberInput input { padding: 0px 5px; }
    div[data-testid="stMetricValue"] { font-size: 1.2rem; }
</style>
""", unsafe_allow_html=True)

# --- Google Sheet 連線 ---
def get_google_sheet_data():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Jiaoxi_2026_Data").sheet1
    return sheet

@st.cache_data(ttl=60)
def load_data():
    try:
        sheet = get_google_sheet_data()
        data = sheet.get_all_records()
        if not data: return pd.DataFrame()
        df = pd.DataFrame(data)
        df["日期"] = pd.to_datetime(df["日期"]).dt.date
        return df
    except Exception as e:
        st.error(f"連線失敗: {e}")
        return pd.DataFrame()

def save_data_to_sheet(df):
    try:
        sheet = get_google_sheet_data()
        save_df = df.copy()
        save_df["日期"] = save_df["日期"].astype(str)
        # 確保 NaN 被轉為 0 或空字串，避免 JSON 錯誤
        save_df = save_df.fillna(0)
        sheet.update([save_df.columns.values.tolist()] + save_df.values.tolist())
        st.toast("✅ 數據已同步上雲端！", icon="☁️")
        st.cache_data.clear()
    except Exception as e:
        st.error(f"儲存失敗: {e}")

# --- 登入邏輯 ---
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
    # --- 主程式 ---
    with st.sidebar:
        st.success(f"Hi, {st.session_state.role}")
        if st.button("🔄 重新讀取"):
            st.cache_data.clear()
            st.rerun()
        st.info("💡 數據自動同步 Google Sheet")

    st.title("☕ 2026 礁溪門市營運戰情室")

    if "df" not in st.session_state:
        st.session_state.df = load_data()
    
    df = st.session_state.df
    
    # 確保所有新欄位都存在 (防止舊資料報錯)
    new_cols = ['目標PSD', '實績PSD', 'PSD達成率', 'ADT', 'AT', '糕點PSD', '糕點USD', '糕點報廢USD', 'Retail', 'NCB', 'BAF', '節慶USD']
    for col in new_cols:
        if col not in df.columns:
            df[col] = 0

    # 月份選擇
    current_month = datetime.date.today().month
    selected_month = st.selectbox("月份", range(1, 13), index=current_month-1)
    
    df["Month"] = pd.to_datetime(df["日期"]).dt.month
    current_month_df = df[df["Month"] == selected_month].copy()

    # --- 權限設定 ---
    # SM 可以改所有目標，SS 只能改實績
    disabled_target = True if st.session_state.role == "SS" else False

    # --- 數據輸入區 (使用 Tabs 分類) ---
    st.subheader(f"📝 {selected_month} 月數據輸入")
    
    tab1, tab2, tab3 = st.tabs(["💰 核心業績 (Sales/PSD)", "🥐 商品與報廢 (Food/Retail)", "📊 客單與分析 (ADT/AT)"])
    
    with tab1:
        st.caption("每日業績與來客數")
        edited_sales = st.data_editor(
            current_month_df[["日期", "目標", "實績", "目標PSD", "實績PSD", "備註"]],
            column_config={
                "日期": st.column_config.DateColumn(disabled=True, width="small"),
                "目標": st.column_config.NumberColumn("目標 $", format="$%d", disabled=disabled_target),
                "實績": st.column_config.NumberColumn("實績 $", format="$%d"),
                "目標PSD": st.column_config.NumberColumn("目標 PSD", disabled=disabled_target),
                "實績PSD": st.column_config.NumberColumn("實績 PSD"),
                "備註": st.column_config.TextColumn(width="medium"),
            },
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            key="editor_sales"
        )

    with tab2:
        st.caption("糕點、包裝食品、周邊商品與節慶預購")
        edited_products = st.data_editor(
            current_month_df[["日期", "糕點PSD", "糕點USD", "糕點報廢USD", "Retail", "NCB", "BAF", "節慶USD"]],
            column_config={
                "日期": st.column_config.DateColumn(disabled=True),
                "糕點PSD": st.column_config.NumberColumn("糕點 PSD"),
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
            key="editor_products"
        )

    with tab3:
        st.caption("客單價與平均消費 (系統自動計算 ADT 與 AT 建議)")
        # 這裡我們讓 ADT 和 AT 可以手動輸入，也可以寫公式自動算
        # 目前先保留手動輸入彈性
        edited_kpi = st.data_editor(
            current_month_df[["日期", "ADT", "AT"]],
            column_config={
                "日期": st.column_config.DateColumn(disabled=True),
                "ADT": st.column_config.NumberColumn("ADT (單價)", format="$%.1f"),
                "AT": st.column_config.NumberColumn("AT (件數)", format="%.2f"),
            },
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            key="editor_kpi"
        )

    # --- 儲存按鈕 ---
    if st.button("💾 更新所有數據", type="primary"):
        # 合併三個表格的修改
        # 透過日期作為 Key 來更新主表
        for i, row in edited_sales.iterrows():
            mask = df["日期"] == row["日期"]
            # Tab 1
            df.loc[mask, "目標"] = row["目標"]
            df.loc[mask, "實績"] = row["實績"]
            df.loc[mask, "目標PSD"] = row["目標PSD"]
            df.loc[mask, "實績PSD"] = row["實績PSD"]
            df.loc[mask, "備註"] = row["備註"]
            
            # 自動計算 PSD 達成率 (避免除以 0)
            t_psd = row["目標PSD"] if row["目標PSD"] > 0 else 1
            df.loc[mask, "PSD達成率"] = round(row["實績PSD"] / t_psd * 100, 1)

        for i, row in edited_products.iterrows():
            mask = df["日期"] == row["日期"]
            # Tab 2
            cols = ["糕點PSD", "糕點USD", "糕點報廢USD", "Retail", "NCB", "BAF", "節慶USD"]
            for c in cols:
                df.loc[mask, c] = row[c]

        for i, row in edited_kpi.iterrows():
            mask = df["日期"] == row["日期"]
            # Tab 3
            df.loc[mask, "ADT"] = row["ADT"]
            df.loc[mask, "AT"] = row["AT"]

        # 呼叫儲存
        save_data_to_sheet(df)
        st.session_state.df = df
        st.success("更新完成！")

    # --- 儀表板與圖表 ---
    st.markdown("---")
    st.subheader("📊 經營分析")
    
    # 計算總和
    total_target = current_month_df["目標"].sum()
    total_actual = current_month_df["實績"].sum()
    total_scrap = current_month_df["糕點報廢USD"].sum()
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("本月業績達成率", f"{(total_actual/total_target*100 if total_target>0 else 0):.1f}%", delta=f"${total_actual-total_target:,.0f}")
    c2.metric("糕點報廢總額", f"${total_scrap:,.0f}", delta_color="inverse")
    
    # 計算平均客單 (簡單除法)
    total_psd = current_month_df["實績PSD"].sum()
    avg_adt = total_actual / total_psd if total_psd > 0 else 0
    c3.metric("平均 ADT", f"${avg_adt:.1f}")
    
    # 節慶佔比
    festival_sales = current_month_df["節慶USD"].sum()
    c4.metric("節慶預購貢獻", f"${festival_sales:,.0f}")
