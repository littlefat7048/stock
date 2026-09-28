# 台股分析平台

## 功能介紹
提供台股每日分析報告，包括個股技術面、基本面、籌碼面分析，以及AI評語。
支援概念股分類瀏覽與自選股追蹤。

## 安裝步驟
```bash
pip install -r requirements.txt
```

## 設定 Gemini API Key 步驟
將 `.streamlit/secrets.toml.example` 複製為 `.streamlit/secrets.toml`，並填入您的 Gemini API 密鑰。

## 啟動方式
```bash
streamlit run app.py
```

## 設定每日自動更新
可透過 Windows 工作排程器設定每日 19:00 執行以下指令：
```bash
python scripts/daily_update.py
```

## 部署到 Streamlit Community Cloud 步驟
1. 將專案推送到 GitHub。
2. 進入 [Streamlit Community Cloud](https://share.streamlit.io/) 建立新應用程式。
3. 選擇 GitHub 存放區、分支，並指定主程式為 `app.py`。
4. 在進階設定中填入 `secrets.toml` 的內容。
5. 點擊 Deploy 部署。
