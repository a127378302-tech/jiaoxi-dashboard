import streamlit as st
import pandas as pd
import datetime

# --- 設定網頁標題與版面 ---
st.set_page_config(page_title="星巴克礁溪門市 | 營運儀表板", page_icon="☕", layout="wide")

# --- 模擬資料庫 (密碼設定) ---
USERS = {
    "SM": "sm2026",      # 店經理帳號
    "SS": "coffee123"    # 值班經理帳號
}

# --- 登入驗證函式 ---
def check_login():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        # 顯示登入畫面
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.title("🔒 礁溪門市登入系統")
            username = st.text_input("帳號")
            password = st.text_input("密碼", type="password")
            if st.button("登入"):
                if username in USERS and USERS[username] == password:
                    st.session_state.authenticated = True
                    st.session_state.role = "SM" if username == "SM" else "SS"
                    st.rerun()
                else:
                    st.error("帳號或密碼錯誤")
        return False
    return True

# --- 初始化空白資料 ---
@st.cache_data
def get_empty_data():
    date_range = pd.date_range(start="2026-01-01", end="2026-12-31", freq="D")
    df = pd.DataFrame({
        "日期": date_range,
        "目標": [0] * len(date_range),
        "實績": [0] * len(date_range),
        "備註": [""] * len(date_range)
    })
    df["日期"] = df["日期"].dt.date
    df["星期"] = pd.to_datetime(df["日期"]).dt.day_name().map({
        'Monday': '一', 'Tuesday': '二', 'Wednesday': '三', 'Thursday': '四',
        'Friday': '五', 'Saturday': '六', 'Sunday': '日'
    })
    return df

# --- 主程式開始 ---
if check_login():
    # 側邊欄：功能區
    with st.sidebar:
        st.success(f"Hi, {st.session_state.role}")
        st.markdown("---")
        st.markdown("### 📥 1. 讀取進度")
        uploaded_file = st.file_uploader("上傳上次下載的 CSV", type=["csv"])
        
        st.markdown("### 📅 2. 選擇月份")
        selected_month = st.selectbox("月份", range(1, 13), format_func=lambda x: f"{x} 月")
        
        # 資料初始化邏輯
        if "df" not in st.session_state:
            st.session_state.df = get_empty_data()
        
        # 如果有上傳檔案，就用上傳的檔案覆蓋
        if uploaded_file:
            try:
                uploaded_df = pd.read_csv(uploaded_file)
                uploaded_df["日期"] = pd.to_datetime(uploaded_df["日期"]).dt.date
                st.session_state.df = uploaded_df
            except:
                st.error("檔案格式不正確")

    # 主畫面
    df = st.session_state.df
    st.title(f"📊 2026 營運目標 - {selected_month}月")

    # 篩選當月資料
    df["Month"] = pd.to_datetime(df["日期"]).dt.month
    current_month_df = df[df["Month"] == selected_month].copy()

    # 權限控管 (SS 不能改目標)
    disabled_cols = ["日期", "星期"]
    if st.session_state.role == "SS":
        disabled_cols.append("目標")
        st.info("💡 值班經理模式：僅能輸入實績與備註，無法修改目標。")

    # 編輯表格
    edited_df = st.data_editor(
        current_month_df[["日期", "星期", "目標", "實績", "備註"]],
        column_config={
            "目標": st.column_config.NumberColumn("目標 $", format="$%d", disabled="目標" in disabled_cols),
            "實績": st.column_config.NumberColumn("實績 $", format="$%d"),
            "日期": st.column_config.DateColumn(format="YYYY-MM-DD", disabled=True),
        },
        use_container_width=True,
        hide_index=True,
        num_rows="fixed"
    )

    # 儲存按鈕 (更新記憶體中的資料)
    if st.button("💾 確認修改 (暫存)"):
        # 更新總表
        for index, row in edited_df.iterrows():
            mask = df["日期"] == row["日期"]
            df.loc[mask, "目標"] = row["目標"]
            df.loc[mask, "實績"] = row["實績"]
            df.loc[mask, "備註"] = row["備註"]
        st.session_state.df = df
        st.success("✅ 修改已暫存！離開前請務必按下側邊欄的下載按鈕。")

    # 儀表板計算
    st.markdown("---")
    total_target = current_month_df["目標"].sum()
    total_actual = current_month_df["實績"].sum()
    rate = (total_actual / total_target * 100) if total_target > 0 else 0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("本月目標", f"${total_target:,.0f}")
    c2.metric("本月實績", f"${total_actual:,.0f}", delta=f"{total_actual-total_target:,.0f}")
    c3.metric("達成率", f"{rate:.1f}%")

    # 下載備份 (最重要的一步)
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 💾 3. 儲存進度 (必做)")
    csv = df.to_csv(index=False).encode('utf-8')
    st.sidebar.download_button(
        label="📥 下載最新資料表 (Backup)",
        data=csv,
        file_name=f"Jiaoxi_Data_{datetime.date.today()}.csv",
        mime="text/csv"
    )
