import streamlit as st

st.title("🔍 Secrets 診斷室")

st.write("正在讀取您的設定檔...")

# 1. 檢查有沒有讀到任何東西
if not st.secrets:
    st.error("❌ Secrets 是空的！請確認您有按 Save。")
else:
    st.success("✅ 成功讀取到 Secrets 檔案！")
    
    # 2. 列出所有讀到的標題 (Key)
    st.write("目前系統看到的標題 (Keys) 有：")
    st.json(list(st.secrets.keys()))

    # 3. 專門檢查機器人設定
    if "gcp_service_account" in st.secrets:
        st.success("🎉 太棒了！找到 [gcp_service_account] 標題了！")
        st.info("請把 app.py 換回原本的正式版程式碼即可。")
    else:
        st.error("😱 找不到 [gcp_service_account] 標題！")
        st.warning("請回到 Secrets，確認第一行是不是 `[gcp_service_account]`")
