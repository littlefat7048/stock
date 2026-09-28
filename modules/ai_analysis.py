"""
Gemini AI 股票分析整合模組
支援：個股多維度分析報告、題材概念股分析
"""
import os
import json
import time
from datetime import datetime
import google.generativeai as genai

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'cache')
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_EXPIRY_SECONDS = 14400  # 4 小時快取

def _get_api_key():
    """取得 Gemini API Key（依序從 Streamlit secrets / secrets.toml / 環境變數取得）"""
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and 'GEMINI_API_KEY' in st.secrets:
            return st.secrets['GEMINI_API_KEY']
    except Exception:
        pass

    # 直接讀取 .streamlit/secrets.toml
    secrets_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.streamlit', 'secrets.toml')
    if os.path.exists(secrets_path):
        try:
            with open(secrets_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('GEMINI_API_KEY') and '=' in line:
                        val = line.split('=', 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
        except Exception:
            pass

    return os.environ.get('GEMINI_API_KEY', '')

def get_gemini_model(model_name=None):
    """初始化並回傳 Gemini GenerativeModel"""
    api_key = _get_api_key()
    if not api_key:
        raise ValueError("未設定 GEMINI_API_KEY，請確認 E:\\antigravity\\STOCK\\.streamlit\\secrets.toml 檔案")
    
    genai.configure(api_key=api_key)
    
    # 優先使用最新旗艦快速模型 gemini-3.8-flash
    target_models = [model_name] if model_name else ['gemini-3.8-flash', 'gemini-flash-latest', 'gemini-3.6-flash']
    for m in target_models:
        if m:
            try:
                return genai.GenerativeModel(m)
            except Exception:
                continue
    return genai.GenerativeModel('gemini-3.8-flash')


def generate_stock_analysis(stock_code, stock_name, tech_data, chip_data, fundamental_data, financial_data):
    """呼叫 Gemini 產生個股綜合分析"""
    cache_key = f"ai_analysis_{stock_code}"
    cache_path = os.path.join(CACHE_DIR, f"{cache_key}.json")

    if os.path.exists(cache_path):
        if time.time() - os.path.getmtime(cache_path) < CACHE_EXPIRY_SECONDS:
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass

    prompt = f"""
你是一位資深台灣股票分析師（20年以上實戰經驗）。請根據以下數據對 {stock_code} {stock_name} 進行全面深度評估。

【技術面數據】
{tech_data}

【籌碼面數據】
{chip_data}

【基本面估值】
{fundamental_data}

【財務表現】
{financial_data}

請以繁體中文輸出，格式必須為合法的 JSON 物件（不要加 ```json 標籤，純文字），包含以下欄位：
{{
  "rating": "買進" 或 "觀望" 或 "賣出",
  "confidence": 1到10的整數信心度,
  "target_price": 目標價數字,
  "stop_loss": 停損價數字,
  "buy_zone_low": 建議買進區間低點,
  "buy_zone_high": 建議買進區間高點,
  "summary": "100字以內綜合評語",
  "strengths": ["優勢1", "優勢2", "優勢3"],
  "risks": ["風險1", "風險2"],
  "strategy": "具體進出場與停利停損操作策略",
  "industry_outlook": "所屬產業未來展望"
}}
"""

    try:
        model = get_gemini_model()
        time.sleep(1)
        response = model.generate_content(prompt)
        text = response.text.strip()
        text = text.replace('```json', '').replace('```', '').strip()

        result = json.loads(text)

        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        return result
    except ValueError as e:
        print(f"Gemini 金鑰錯誤: {e}")
        return {'error': str(e)}
    except Exception as e:
        print(f"AI 分析產生失敗: {e}")
        return {'error': f'分析失敗：{e}'}

def generate_concept_analysis(concept_name, stocks_data):
    """分析特定概念股題材"""
    prompt = f"""
你是一位資深台灣股票分析師。請深入分析近期熱門題材：「{concept_name}」。
相關概念股：{stocks_data}

請用繁體中文提供專業分析報告（約300字），說明：
1. 此題材的核心市場驅動力
2. 法人與市場資金流向
3. 優先受惠個股排名與理由
4. 追價風險與關鍵觀察指標
"""
    try:
        model = get_gemini_model()
        time.sleep(1)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"產生概念分析失敗：{e}"
