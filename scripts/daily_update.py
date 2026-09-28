"""
每日定時抓取盤後報告腳本
設定於每日 19:00 自動執行，亦可隨時手動直接執行：
python scripts/daily_update.py
"""
import os
import sys
import time
import schedule

# 設定路徑
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
sys.path.insert(0, PROJECT_ROOT)

from modules.daily_report import scrape_report, get_today_date_str

def daily_job():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 開始執行每日盤後報告抓取作業...")
    today_str = get_today_date_str()
    result = scrape_report(today_str)
    
    if result.get('status') == 'success':
        date_str = result.get('date', today_str)
        stocks_count = len(result.get('stocks_found', []))
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ✅ 抓取成功！報告日期: {date_str}，共收錄 {stocks_count} 檔個股深度分析")
    else:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ⚠️ 今日尚未發布或抓取失敗，稍後會自動重試...")

if __name__ == '__main__':
    print("=" * 60)
    print("台股盤後分析 — 每日定時抓取服務已啟動")
    print("設定排程時間：每日 19:00 自動執行")
    print("=" * 60)
    
    # 啟動時先立即執行一次檢查
    daily_job()
    
    # 排程每日 19:00 執行；若 19:00 失敗，19:30 再試一次
    schedule.every().day.at("19:00").do(daily_job)
    schedule.every().day.at("19:30").do(daily_job)
    schedule.every().day.at("20:00").do(daily_job)

    print("\n背景監聽中... 按 Ctrl + C 可終止排程。\n")
    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        print("\n定時服務已停止。")
