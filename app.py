import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime

# --- 1. 設定網頁與樣式 ---
st.set_page_config(page_title="星巴克礁溪門市 | 營運與禮盒控管", page_icon="☕", layout="wide")

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
    .stock-bar-bg { width: 100%; background-color: #e0e0e0; border-radius: 5px; height: 20px; }
    .stock-bar-fill { height: 100%; border-radius: 5px; text-align: center; color: white; font-size: 12px; line-height: 20px;}
</style>
""", unsafe_allow_html=True)

# --- 2. 資料定義 (假日與行銷活動) ---
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
}

def get_date_display(date_input):
    """轉換日期顯示格式 (含星期與假日)"""
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
    """取得當日行銷活動"""
    d_str = str(date_input)
    return MARKETING_CALENDAR.get(d_str, "")

# --- 3. Google Sheet 連線核心 ---
def get_gspread_client():
    """取得 Google Sheets Client 物件"""
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    try:
        creds_dict = dict(st.secrets["gcp_service_account"]) if "gcp_service_account" in st.secrets else dict(st.secrets)
        if "private_key" in creds_dict: creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"❌ GCP 連線錯誤：{str(e)}")
        st.stop()

# --- 3.1 營運報表資料處理 (Sheet 1) ---
def get_main_sheet():
    client = get_gspread_client()
    return client.open("Jiaoxi_2026_Data").sheet1

def initialize_sheet(sheet):
    date_range = pd.date_range(start="2026-01-01", end="2026-12-31", freq="D")
    # [更新] 加入外送欄位
    cols = ['日期', '目標PSD', '實績PSD', 'PSD達成率', 'ADT', 'AT', '糕點PSD', '糕點USD', '糕點報廢USD', 'Retail', 'NCB', 'BAF', '節慶USD', 'foodpanda', 'foodomo', 'MOP', '備註']
    df = pd.DataFrame(columns=cols)
    df['日期'] = date_range.astype(str)
    df = df.fillna(0)
    df['備註'] = ""
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.values.tolist())
    return df

@st.cache_data(ttl=60)
def load_data():
    try:
        sheet = get_main_sheet()
        data = sheet.get_all_records()
        if not data: return initialize_sheet(sheet)
        
        df = pd.DataFrame(data)
        required = ['日期', '目標PSD', '實績PSD']
        if not all(c in df.columns for c in required): return initialize_sheet(sheet)
        
        df["日期"] = pd.to_datetime(df["日期"]).dt.date
        # [更新] 加入外送欄位到數值處理清單
        numeric_cols = ['目標PSD', '實績PSD', 'PSD達成率', 'ADT', 'AT', '糕點PSD', '糕點USD', '糕點報廢USD', 'Retail', 'NCB', 'BAF', '節慶USD', 'foodpanda', 'foodomo', 'MOP']
        for col in numeric_cols:
            if col in df.columns: 
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            else:
                df[col] = 0 # 若試算表還沒新增該欄位，預設為 0 避免錯誤
            
        df["當日活動"] = df["日期"].apply(lambda x: get_event_info(x))
        return df
    except Exception as e:
        st.error(f"讀取錯誤: {e}")
        return pd.DataFrame()

def save_data_to_sheet(df):
    try:
        sheet = get_main_sheet()
        # [更新] 存檔時包含外送欄位
        save_cols = ['日期', '目標PSD', '實績PSD', 'PSD達成率', 'ADT', 'AT', '糕點PSD', '糕點USD', '糕點報廢USD', 'Retail', 'NCB', 'BAF', '節慶USD', 'foodpanda', 'foodomo', 'MOP', '備註']
        
        # 確保所有欄位都存在 (避免 user 手動刪除導致錯誤)
        for col in save_cols:
            if col not in df.columns:
                df[col] = 0 if col != '備註' else ""

        save_df = df[save_cols].copy()
        save_df["日期"] = save_df["日期"].astype(str)
        save_df = save_df.fillna(0)
        sheet.clear()
        sheet.update([save_df.columns.values.tolist()] + save_df.values.tolist())
        st.toast("✅ 營運數據已更新！", icon="💾")
        st.cache_data.clear()
    except Exception as e:
        st.error(f"儲存失敗: {e}")

# --- 3.2 禮盒控管資料處理 (Sheet 2) ---
def get_gift_sheet():
    client = get_gspread_client()
    workbook = client.open("Jiaoxi_2026_Data")
    try:
        return workbook.worksheet("工作表2")
    except:
        try:
            return workbook.get_worksheet(1)
        except:
            return workbook.add_worksheet(title="工作表2", rows=100, cols=4)

@st.cache_data(ttl=60)
def load_gift_data():
    try:
        sheet = get_gift_sheet()
        data = sheet.get_all_records()
        cols = ['檔期', '品項', '原始控量', '剩餘控量']
        
        if not data:
            df = pd.DataFrame(columns=cols)
        else:
            df = pd.DataFrame(data)
            for c in cols:
                if c not in df.columns:
                    df[c] = ""
                    
        df['原始控量'] = pd.to_numeric(df['原始控量'], errors='coerce').fillna(0).astype(int)
        df['剩餘控量'] = pd.to_numeric(df['剩餘控量'], errors='coerce').fillna(0).astype(int)
        return df[cols]
    except Exception as e:
        st.error(f"禮盒資料讀取錯誤: {e}")
        return pd.DataFrame(columns=['檔期', '品項', '原始控量', '剩餘控量'])

def save_gift_data(df):
    try:
        sheet = get_gift_sheet()
        df = df.fillna(0)
        sheet.clear()
        sheet.update([df.columns.values.tolist()] + df.values.tolist())
        st.toast("✅ 禮盒庫存已更新！", icon="🎁")
        st.cache_data.clear()
    except Exception as e:
        st.error(f"禮盒儲存失敗: {e}")

# --- 4. 主程式 ---

with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/zh/d/df/Starbucks_Corporation_Logo_2011.svg", width=100)
    st.title("門市管理系統")
    
    page = st.radio("前往頁面", ["📊 每日營運報表", "🎁 節慶禮盒控管"], index=0)
    
    st.markdown("---")
    if st.button("🔄 重新讀取資料"):
        st.cache_data.clear()
        st.rerun()

# ==========================================
# 頁面 1: 每日營運報表
# ==========================================
if page == "📊 每日營運報表":
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

    st.title("☕ 2026 礁溪門市營運報表")

    st.markdown(f"""
    <div class="activity-box">
        <div class="activity-title">📢 門市活動快訊 (Today: {today.strftime('%m/%d')})</div>
        <div style="font-size: 1.5em; color: #333; margin: 10px 0;">👉 今日重點：{today_event}</div>
        <hr style="border-top: 1px dashed #ccc;">
        <div style="color: #666;">
            <b>🔜 未來預告：</b> {' &nbsp;|&nbsp; '.join(upcoming_text) if upcoming_text else "近期無大型檔期"}
        </div>
    </div>
    """, unsafe_allow_html=True)

    if "df" not in st.session_state: st.session_state.df = load_data()
    df = st.session_state.df
    if df.empty: st.stop()

    current_month = today.month
    selected_month = st.selectbox("月份", range(1, 13), index=current_month-1)
    df["Month"] = pd.to_datetime(df["日期"]).dt.month
    current_month_df = df[df["Month"] == selected_month].copy()
    if not current_month_df.empty:
        current_month_df["顯示日期"] = current_month_df["日期"].apply(get_date_display)

    # 數據輸入區
    st.subheader(f"📝 {selected_month} 月數據輸入")

    # [更新] 新增第三個分頁
    tab1, tab2, tab3 = st.tabs(["📊 核心業績 (PSD/ADT/AT)", "🥐 商品與庫存 (Product/Waste)", "🛵 外送平台 (Delivery)"])

    with tab1:
        st.caption("請輸入每日業績。右側「當日活動」為系統自動帶入，供您參考。")
        edited_kpi = st.data_editor(
            current_month_df[['顯示日期', '日期', '目標PSD', '實績PSD', 'PSD達成率', 'ADT', 'AT', '備註', '當日活動']],
            column_config={
                "顯示日期": st.column_config.TextColumn("日期", disabled=True, width="small"),
                "日期": None,
                "目標PSD": st.column_config.NumberColumn("目標", format="$%d"),
                "實績PSD": st.column_config.NumberColumn("實績", format="$%d"),
                "PSD達成率": st.column_config.NumberColumn("達成%", disabled=True, format="%.1f%%"),
                "ADT": st.column_config.NumberColumn("來客", format="%d"),
                "AT": st.column_config.NumberColumn("客單", disabled=True, format="$%d"),
                "備註": st.column_config.TextColumn("手動備註", width="small"),
                "當日活動": st.column_config.TextColumn("📅 當日活動 (自動)", disabled=True, width="medium"), 
            },
            use_container_width=True, hide_index=True, num_rows="fixed", key="editor_kpi"
        )

    with tab2:
        edited_prod = st.data_editor(
            current_month_df[['顯示日期', '日期', '糕點PSD', '糕點USD', '糕點報廢USD', 'Retail', 'NCB', 'BAF', '節慶USD']],
            column_config={
                "顯示日期": st.column_config.TextColumn("日期", disabled=True, width="small"),
                "日期": None,
                "糕點PSD": st.column_config.NumberColumn("糕點業績", format="$%d"),
                "糕點USD": st.column_config.NumberColumn("糕點銷量", format="%d"),
                "糕點報廢USD": st.column_config.NumberColumn("報廢(個)", format="%d"),
                "Retail": st.column_config.NumberColumn("Retail", format="$%d"),
                "NCB": st.column_config.NumberColumn("NCB", format="%d"),
                "BAF": st.column_config.NumberColumn("BAF", format="%d"),
                "節慶USD": st.column_config.NumberColumn("節慶", format="%d"),
            },
            use_container_width=True, hide_index=True, num_rows="fixed", key="editor_prod"
        )
    
    # [更新] 新增外送分頁內容
    with tab3:
        st.caption("請輸入各平台外送業績 (單位：元)")
        edited_delivery = st.data_editor(
            current_month_df[['顯示日期', '日期', 'foodpanda', 'foodomo', 'MOP']],
            column_config={
                "顯示日期": st.column_config.TextColumn("日期", disabled=True, width="small"),
                "日期": None,
                "foodpanda": st.column_config.NumberColumn("Foodpanda", format="$%d"),
                "foodomo": st.column_config.NumberColumn("Foodomo", format="$%d"),
                "MOP": st.column_config.NumberColumn("MOP", format="$%d"),
            },
            use_container_width=True, hide_index=True, num_rows="fixed", key="editor_delivery"
        )

    if st.button("💾 確認更新 (並自動計算)", type="primary"):
        # 更新 KPI
        for i, row in edited_kpi.iterrows():
            row_date = row["日期"]
            mask = df["日期"] == row_date
            if mask.any():
                df.loc[mask, "目標PSD"] = row["目標PSD"]
                df.loc[mask, "實績PSD"] = row["實績PSD"]
                df.loc[mask, "ADT"] = row["ADT"]
                df.loc[mask, "備註"] = row["備註"]
                
                t_psd = float(row["目標PSD"]) if row["目標PSD"] > 0 else 1.0
                actual_psd = float(row["實績PSD"])
                df.loc[mask, "PSD達成率"] = round((actual_psd / t_psd) * 100, 1)
                
                cust = float(row["ADT"]) if row["ADT"] > 0 else 1.0
                df.loc[mask, "AT"] = int(round(actual_psd / cust, 0)) if row["ADT"] > 0 else 0

        # 更新 商品
        for i, row in edited_prod.iterrows():
            row_date = row["日期"]
            mask = df["日期"] == row_date
            cols = ['糕點PSD', '糕點USD', '糕點報廢USD', 'Retail', 'NCB', 'BAF', '節慶USD']
            for c in cols: df.loc[mask, c] = row[c]
            
        # [更新] 更新 外送
        for i, row in edited_delivery.iterrows():
            row_date = row["日期"]
            mask = df["日期"] == row_date
            cols = ['foodpanda', 'foodomo', 'MOP']
            for c in cols: df.loc[mask, c] = row[c]

        save_data_to_sheet(df)
        st.session_state.df = df
        st.rerun()

    # 儀表板與分析區
    st.markdown("---")
    current_month_df["Week_Num"] = pd.to_datetime(current_month_df["日期"]).dt.isocalendar().week
    st.subheader("📅 數據檢視與 AI 分析")
    col_view, col_week = st.columns([1, 3])

    with col_view:
        view_mode = st.radio("選擇模式", ["全月累計", "單週分析"], horizontal=True, label_visibility="collapsed")

    target_df = current_month_df
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
                sel_label = st.selectbox("選擇週次", list(week_options.keys()), index=len(week_options)-1)
                target_df = current_month_df[current_month_df["Week_Num"] == week_options[sel_label]]

    # 計算邏輯
    valid_df = target_df[target_df["實績PSD"] > 0]
    days_count = max(valid_df.shape[0], 1)

    total_sales = target_df["實績PSD"].sum()
    total_target = target_df["目標PSD"].sum()
    achieve_rate = (total_sales / total_target * 100) if total_target > 0 else 0
    avg_adt = valid_df["ADT"].mean() if not valid_df.empty else 0
    total_adt = target_df["ADT"].sum()
    avg_at = total_sales / total_adt if total_adt > 0 else 0

    st.markdown("##### 🏆 績效看板")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("累積 SALES", f"${total_sales:,.0f}")
    m2.metric("達成率", f"{achieve_rate:.1f}%", delta=f"${total_sales - total_target:,.0f}")
    m3.metric("平均 PSD", f"${total_sales/days_count:,.0f}")
    m4.metric("平均 ADT", f"{avg_adt:,.0f}")
    m5.metric("平均 AT", f"${avg_at:,.0f}")

    st.markdown("##### ⚡ 關鍵指標 (日平均)")
    k1, k2, k3, k4, k5 = st.columns(5)
    if not valid_df.empty:
        k1.metric("糕點 PSD", f"${valid_df['糕點PSD'].mean():,.0f}")
        k2.metric("糕點 USD", f"{valid_df['糕點USD'].mean():.1f} 個")
        k3.metric("糕點報廢", f"{valid_df['糕點報廢USD'].mean():.1f} 個", delta_color="inverse")
        k4.metric("NCB 杯數", f"{valid_df['NCB'].mean():.1f}")
        k5.metric("Retail", f"${valid_df['Retail'].mean():,.0f}")

    st.markdown("---")
    st.subheader("🤖 呼叫 AI 營運顧問")
    with st.expander("點擊展開：取得 AI 深度分析指令 (含行銷活動)", expanded=False):
        period_str = f"2026年 {selected_month}月 ({view_mode})"
        # [更新] AI Prompt 增加外送資訊
        ai_prompt = f"""我是星巴克店經理，請協助分析本門市數據。\n【分析區間】：{period_str}\n\n【每日詳細數據】：\n(格式：日期: 業績 /達成率/ 來客 | 客單 /糕點PSD/USD/報廢/Retail/NCB/BAF/節慶/熊貓/FDM/MOP, 活動：名稱)\n"""
        
        detail_data = target_df[target_df["實績PSD"] > 0].sort_values("日期")
        
        if not detail_data.empty:
            for idx, row in detail_data.iterrows():
                d_str = row["日期"].strftime("%m/%d")
                sales = row['實績PSD']
                target = row['目標PSD']
                rate = (sales / target * 100) if target > 0 else 0
                evt_name = get_event_info(row["日期"])
                evt_str = f", 活動：{evt_name}" if evt_name else ""
                
                # 確保外送欄位有值
                panda = row.get('foodpanda', 0)
                fdm = row.get('foodomo', 0)
                mop = row.get('MOP', 0)

                line_str = (f"{d_str}: 業績${sales:,.0f} /{rate:.1f}%/ 來客{row['ADT']}筆 |"
                            f"客單_${row['AT']} /糕點PSD_${row['糕點PSD']:,.0f}/糕點USD_{row['糕點USD']}個/"
                            f" 報廢USD_{row['糕點報廢USD']}個/Retail商品${row['Retail']:,.0f}/"
                            f"NCB_{row['NCB']}杯/BAF_{row['BAF']}張/節慶_{row['節慶USD']}個/"
                            f"熊貓${panda}/FDM${fdm}/MOP${mop}{evt_str}")
                ai_prompt += f"{line_str}\n"
            if not valid_df.empty:
                avg_line = (f"\n【區間平均】: 業績${valid_df['實績PSD'].mean():,.0f} / 來客{valid_df['ADT'].mean():,.0f} | "
                            f"客單${avg_at:.0f} / 報廢{valid_df['糕點報廢USD'].mean():.1f}個 / NCB{valid_df['NCB'].mean():.1f}杯")
                ai_prompt += avg_line
        else:
            ai_prompt += "(尚無資料)"
        ai_prompt += "\n\n請針對「活動效益」與「業績缺口」進行分析，並觀察外送平台業績(熊貓/Foodomo/MOP)是否有機會點？"
        st.code(ai_prompt, language="text")

# ==========================================
# 頁面 2: 節慶禮盒控管
# ==========================================
elif page == "🎁 節慶禮盒控管":
    st.title("🎁 節慶禮盒庫存控管")
    st.caption("同步 Google Sheet「工作表2」，可直接下方新增、刪除或修改。")
    
    gift_df = load_gift_data()
    
    if not gift_df.empty:
        total_qty = gift_df["原始控量"].sum()
        remain_qty = gift_df["剩餘控量"].sum()
        sold_qty = total_qty - remain_qty
        sell_rate = (sold_qty / total_qty * 100) if total_qty > 0 else 0
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("總控量 (Total)", f"{total_qty} 盒")
        c2.metric("已銷售 (Sold)", f"{sold_qty} 盒")
        c3.metric("庫存剩餘 (Stock)", f"{remain_qty} 盒")
        c4.metric("銷售進度", f"{sell_rate:.1f}%")
        
        st.markdown("---")

    edited_gift_df = st.data_editor(
        gift_df,
        column_config={
            "檔期": st.column_config.SelectboxColumn("檔期", options=["Spring", "Summer", "Moon", "Xmas", "NewYear", "常態"], required=True),
            "品項": st.column_config.TextColumn("禮盒名稱", required=True, width="medium"),
            "原始控量": st.column_config.NumberColumn("原始控量", min_value=0, step=1, format="%d"),
            "剩餘控量": st.column_config.NumberColumn("剩餘控量", min_value=0, step=1, format="%d"),
        },
        num_rows="dynamic",
        use_container_width=True,
        key="gift_editor"
    )
    
    col_btn, col_info = st.columns([1, 4])
    with col_btn:
        if st.button("💾 儲存禮盒變更", type="primary"):
            save_gift_data(edited_gift_df)
            st.rerun()
            
    st.markdown("### 📊 庫存視覺化")
    if not edited_gift_df.empty:
        for index, row in edited_gift_df.iterrows():
            name = row['品項']
            original = row['原始控量']
            remain = row['剩餘控量']
            
            if original > 0:
                pct = int((remain / original) * 100)
                color = "#28a745"
                if pct < 20: color = "#dc3545"
                elif pct < 50: color = "#ffc107"
                
                st.markdown(f"**{name}** (剩 {remain}/{original})")
                st.markdown(f"""
                <div class="stock-bar-bg">
                    <div class="stock-bar-fill" style="width: {pct}%; background-color: {color};">
                        {pct}%
                    </div>
                </div>
                """, unsafe_allow_html=True)
                st.write("")
