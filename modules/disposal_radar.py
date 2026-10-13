"""
disposal_radar.py - 處置股預測、當沖券差借券軋空、注意股自結損益雷達模組
資料來源：Chengwaye 與證交所公開資料
"""

import os
import json
import time
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from collections import defaultdict

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def _load_cache(cache_file, max_age_seconds=1800):
    """讀取快取，超過 max_age_seconds 回傳 None"""
    if os.path.exists(cache_file):
        try:
            mtime = os.path.getmtime(cache_file)
            if time.time() - mtime < max_age_seconds:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
    return None

def _save_cache(cache_file, data):
    """儲存快取"""
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def get_disposal_forecast(force_refresh=False):
    """
    抓取並解析處置預測清單
    含：差1次就處置、差2次警戒、目前處置中股票、LINE轉貼版
    """
    cache_file = os.path.join(CACHE_DIR, "disposal_forecast.json")
    if not force_refresh:
        cached = _load_cache(cache_file, max_age_seconds=1800) # 30 分鐘
        if cached:
            return cached

    url = "https://chengwaye.com/disposal-forecast"
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code != 200:
            cached = _load_cache(cache_file, max_age_seconds=86400 * 7)
            if cached:
                return cached
            return {"status": "error", "message": f"HTTP {r.status_code}"}
        
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # 標題與日期
        h1 = soup.find('h1')
        title_text = h1.text.strip() if h1 else 'Chengwaye 明日處置股清單'
        subtitle = soup.find(class_='subtitle')
        subtitle_text = subtitle.text.strip() if subtitle else ''
        
        # LINE 轉貼文字
        line_pre = soup.find(id='line-share-text')
        line_share_text = line_pre.text.strip() if line_pre else ''
        
        # 1. 差 1 次就處置 (High Risk)
        high_stocks = []
        high_sec = soup.find(id='disposal-high-section')
        if high_sec:
            for row in high_sec.find_all('tr', class_='clickable-row'):
                code = row.get('data-code', '')
                name = row.get('data-name', '')
                tds = row.find_all('td')
                if len(tds) >= 6:
                    market = tds[0].text.strip()
                    close_price = tds[3].text.strip()
                    trigger_cond = tds[4].text.strip().replace('\n', ' ')
                    soonest_date = tds[5].text.strip()
                    
                    # 條款進度
                    c_3_1 = tds[6].find('div').get('title', '') if len(tds) > 6 and tds[6].find('div') else ''
                    c_5 = tds[7].find('div').get('title', '') if len(tds) > 7 and tds[7].find('div') else ''
                    c_6 = tds[8].find('div').get('title', '') if len(tds) > 8 and tds[8].find('div') else ''
                    c_12 = tds[9].find('div').get('title', '') if len(tds) > 9 and tds[9].find('div') else ''
                    
                    # 展開明細
                    detail_row = row.find_next_sibling('tr', class_='detail-row')
                    detail_text = detail_row.text.strip().replace('\n', ' ') if detail_row else ''
                    
                    high_stocks.append({
                        'code': code,
                        'name': name,
                        'market': market,
                        'close': close_price,
                        'trigger_cond': trigger_cond,
                        'soonest_disposal': soonest_date,
                        'c_3_1': c_3_1,
                        'c_5': c_5,
                        'c_6': c_6,
                        'c_12': c_12,
                        'detail': detail_text
                    })
                    
        # 2. 差 2 次處置 (Medium Risk)
        med_stocks = []
        med_sec = soup.find(id='disposal-medium-section')
        if med_sec:
            for row in med_sec.find_all('tr', class_='clickable-row'):
                code = row.get('data-code', '')
                name = row.get('data-name', '')
                tds = row.find_all('td')
                if len(tds) >= 6:
                    market = tds[0].text.strip()
                    close_price = tds[3].text.strip()
                    trigger_cond = tds[4].text.strip().replace('\n', ' ')
                    soonest_date = tds[5].text.strip()
                    
                    c_3_1 = tds[6].find('div').get('title', '') if len(tds) > 6 and tds[6].find('div') else ''
                    c_5 = tds[7].find('div').get('title', '') if len(tds) > 7 and tds[7].find('div') else ''
                    c_6 = tds[8].find('div').get('title', '') if len(tds) > 8 and tds[8].find('div') else ''
                    c_12 = tds[9].find('div').get('title', '') if len(tds) > 9 and tds[9].find('div') else ''
                    
                    detail_row = row.find_next_sibling('tr', class_='detail-row')
                    detail_text = detail_row.text.strip().replace('\n', ' ') if detail_row else ''
                    
                    med_stocks.append({
                        'code': code,
                        'name': name,
                        'market': market,
                        'close': close_price,
                        'trigger_cond': trigger_cond,
                        'soonest_disposal': soonest_date,
                        'c_3_1': c_3_1,
                        'c_5': c_5,
                        'c_6': c_6,
                        'c_12': c_12,
                        'detail': detail_text
                    })
                    
        # 3. 處置中股票
        active_stocks = []
        disp_sec = soup.find(class_='section-disposal')
        if disp_sec:
            for row in disp_sec.find_all('tr'):
                if row.get('id', '').startswith('stock-active-'):
                    code = row.get('data-code', '')
                    name = row.get('data-name', '')
                    tds = row.find_all('td')
                    if len(tds) >= 8:
                        market = tds[0].text.strip()
                        interval = tds[3].text.strip()
                        start_date = tds[4].text.strip()
                        end_date = tds[5].text.strip()
                        exit_date = tds[6].text.strip()
                        remaining_days = tds[7].text.strip()
                        reason = tds[8].text.strip() if len(tds) > 8 else ''
                        
                        active_stocks.append({
                            'code': code,
                            'name': name,
                            'market': market,
                            'interval': interval,
                            'start_date': start_date,
                            'end_date': end_date,
                            'exit_date': exit_date,
                            'remaining_days': remaining_days,
                            'reason': reason
                        })
                        
        exit_soon = [s for s in active_stocks if s['remaining_days'] in ['出關', '1天', '2天']]
        
        result = {
            'status': 'success',
            'fetched_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'title': title_text,
            'subtitle': subtitle_text,
            'high_risk': high_stocks,
            'med_risk': med_stocks,
            'active_disposal': active_stocks,
            'exit_soon': exit_soon,
            'line_share_text': line_share_text,
            'stats': {
                'high_count': len(high_stocks),
                'med_count': len(med_stocks),
                'active_count': len(active_stocks),
                'exit_soon_count': len(exit_soon)
            }
        }
        _save_cache(cache_file, result)
        return result
    except Exception as e:
        cached = _load_cache(cache_file, max_age_seconds=86400 * 7)
        if cached:
            return cached
        return {"status": "error", "message": str(e)}

def get_borrowed_short_squeeze(force_refresh=False):
    """
    抓取並彙整當沖券差借券費率與借量（核彈級軋空指標）
    """
    cache_file = os.path.join(CACHE_DIR, "borrowed_squeeze.json")
    if not force_refresh:
        cached = _load_cache(cache_file, max_age_seconds=1800)
        if cached:
            return cached

    url = "https://chengwaye-data.pages.dev/realtime_borrowed.json"
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code != 200:
            cached = _load_cache(cache_file, max_age_seconds=86400 * 7)
            if cached:
                return cached
            return {"status": "error", "message": f"HTTP {r.status_code}"}
        
        data = r.json()
        entries = data.get('entries', [])
        
        # 依個股分組計算
        grouped = defaultdict(list)
        for e in entries:
            grouped[e['code']].append(e)
            
        summary_list = []
        for code, items in grouped.items():
            first = items[0]
            name = first.get('name', '')
            market = first.get('market', '')
            close = first.get('close', 0)
            daily_pct_val = first.get('dailyPct')
            daily_pct = round(float(daily_pct_val), 2) if daily_pct_val is not None else 0.0
            locked = first.get('locked', '')
            
            total_shares_num = sum(it.get('shares', 0) for it in items)
            total_lots = round(total_shares_num / 1000) # 換算為張數
            
            rates = [float(it.get('rate', 0)) for it in items if it.get('rate') is not None]
            max_rate = max(rates) if rates else 0.0
            min_rate = min(rates) if rates else 0.0
            
            if total_shares_num > 0:
                weighted_avg_rate = sum(float(it.get('rate', 0)) * float(it.get('shares', 0)) for it in items if it.get('rate') is not None) / total_shares_num
            else:
                weighted_avg_rate = sum(rates) / len(rates) if rates else 0.0
                
            is_locked_up = (locked == 'up') or (daily_pct >= 9.5)
            
            # 軋空危險評級
            if is_locked_up and total_lots >= 30:
                squeeze_rank = '🚨 極高危 (漲停鎖死軋空)'
                rank_score = 3
            elif is_locked_up or weighted_avg_rate >= 3.0 or total_lots >= 100:
                squeeze_rank = '⚡ 高危 (空單遭咬住)'
                rank_score = 2
            else:
                squeeze_rank = '⚠️ 中度 (留意早盤回補)'
                rank_score = 1
                
            summary_list.append({
                'code': code,
                'name': name,
                'market': '上市' if market == 'TSE' else '上櫃',
                'close': close,
                'daily_pct': round(daily_pct, 2) if daily_pct is not None else 0.0,
                'total_lots': total_lots,
                'records_count': len(items),
                'avg_rate': round(weighted_avg_rate, 2),
                'max_rate': round(max_rate, 2),
                'min_rate': round(min_rate, 2),
                'is_locked_up': is_locked_up,
                'squeeze_rank': squeeze_rank,
                'rank_score': rank_score
            })
            
        # 依軋空危險評級與張數排序
        summary_list.sort(key=lambda x: (x['rank_score'], x['total_lots']), reverse=True)
        
        result = {
            'status': 'success',
            'date': data.get('date', ''),
            'generated_at': data.get('generatedAt', ''),
            'total_stocks': len(summary_list),
            'high_squeeze_count': len([x for x in summary_list if x['rank_score'] >= 2]),
            'entries': summary_list
        }
        _save_cache(cache_file, result)
        return result
    except Exception as e:
        cached = _load_cache(cache_file, max_age_seconds=86400 * 7)
        if cached:
            return cached
        return {"status": "error", "message": str(e)}

def get_attention_self_reported_eps(force_refresh=False):
    """
    抓取注意股最新自結損益公告與 AI 評分榜
    """
    cache_file = os.path.join(CACHE_DIR, "attention_self_reported_eps.json")
    if not force_refresh:
        cached = _load_cache(cache_file, max_age_seconds=1800)
        if cached:
            return cached

    url = "https://chengwaye-data.pages.dev/realtime_att.json"
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code != 200:
            cached = _load_cache(cache_file, max_age_seconds=86400 * 7)
            if cached:
                return cached
            return {"status": "error", "message": f"HTTP {r.status_code}"}
        
        data = r.json()
        raw_entries = data.get('entries', [])
        
        parsed_entries = []
        for e in raw_entries:
            code = e.get('code', '')
            name = e.get('name', '')
            date = e.get('date', '')
            time_str = e.get('time', '')
            subject = e.get('subject', '')
            ai_score = e.get('ai_score', 0)
            ai_reason = e.get('ai_reason', '')
            
            p = e.get('parsed', {})
            eps = p.get('EPS') if p.get('EPS') is not None else p.get('季EPS')
            period = p.get('自結期間', '')
            prev_quarter_avg = p.get('月均EPS', 0.0)
            prev_month_eps = p.get('上月EPS')
            
            parsed_entries.append({
                'code': code,
                'name': name,
                'date': date,
                'time': time_str,
                'subject': subject,
                'period': period,
                'eps': eps,
                'prev_quarter_avg': prev_quarter_avg,
                'prev_month_eps': prev_month_eps,
                'ai_score': ai_score,
                'ai_reason': ai_reason,
                'raw': e.get('raw', '')
            })
            
        result = {
            'status': 'success',
            'fetched_at': data.get('fetched_at', ''),
            'total': len(parsed_entries),
            'entries': parsed_entries
        }
        _save_cache(cache_file, result)
        return result
    except Exception as e:
        cached = _load_cache(cache_file, max_age_seconds=86400 * 7)
        if cached:
            return cached
        return {"status": "error", "message": str(e)}

def get_stock_disposal_status(stock_code):
    """
    查詢特定個股的處置、警戒、券差與自結綜合狀態
    用於個股分析頁 (pages/1_📊_股票分析.py)
    """
    code_str = str(stock_code).strip()
    status = {
        'in_disposal': False,
        'disposal_info': None,
        'near_disposal': False,
        'near_disposal_info': None,
        'has_short_squeeze': False,
        'squeeze_info': None,
        'has_self_reported_eps': False,
        'att_info': None
    }
    
    # 1. 處置與預測
    try:
        disp_data = get_disposal_forecast()
        if disp_data.get('status') == 'success':
            # 查處置中
            for item in disp_data.get('active_disposal', []):
                if item.get('code') == code_str:
                    status['in_disposal'] = True
                    status['disposal_info'] = item
                    break
            # 查差1次處置
            for item in disp_data.get('high_risk', []):
                if item.get('code') == code_str:
                    status['near_disposal'] = True
                    status['near_disposal_info'] = {
                        'level': '🔴 差 1 次處置 (高危警戒)',
                        'trigger_cond': item.get('trigger_cond'),
                        'soonest': item.get('soonest_disposal'),
                        'c_3_1': item.get('c_3_1'),
                        'c_5': item.get('c_5'),
                        'c_6': item.get('c_6'),
                        'c_12': item.get('c_12'),
                        'detail': item.get('detail')
                    }
                    break
            # 查差2次處置
            if not status['near_disposal']:
                for item in disp_data.get('med_risk', []):
                    if item.get('code') == code_str:
                        status['near_disposal'] = True
                        status['near_disposal_info'] = {
                            'level': '🟡 差 2 次處置 (中度觀察)',
                            'trigger_cond': item.get('trigger_cond'),
                            'soonest': item.get('soonest_disposal'),
                            'c_3_1': item.get('c_3_1'),
                            'c_5': item.get('c_5'),
                            'c_6': item.get('c_6'),
                            'c_12': item.get('c_12'),
                            'detail': item.get('detail')
                        }
                        break
    except Exception:
        pass
        
    # 2. 當沖券差軋空
    try:
        squeeze_data = get_borrowed_short_squeeze()
        if squeeze_data.get('status') == 'success':
            for item in squeeze_data.get('entries', []):
                if item.get('code') == code_str:
                    status['has_short_squeeze'] = True
                    status['squeeze_info'] = item
                    break
    except Exception:
        pass
        
    # 3. 注意股自結損益
    try:
        att_data = get_attention_self_reported_eps()
        if att_data.get('status') == 'success':
            for item in att_data.get('entries', []):
                if item.get('code') == code_str:
                    status['has_self_reported_eps'] = True
                    status['att_info'] = item
                    break
    except Exception:
        pass
        
    return status

if __name__ == '__main__':
    print("=== Testing get_disposal_forecast ===")
    d = get_disposal_forecast()
    print("Status:", d.get('status'), "High:", len(d.get('high_risk', [])), "Active:", len(d.get('active_disposal', [])))
    
    print("\n=== Testing get_borrowed_short_squeeze ===")
    b = get_borrowed_short_squeeze()
    print("Status:", b.get('status'), "Total stocks:", b.get('total_stocks', 0), "High squeeze:", b.get('high_squeeze_count', 0))
    
    print("\n=== Testing get_attention_self_reported_eps ===")
    a = get_attention_self_reported_eps()
    print("Status:", a.get('status'), "Total:", a.get('total', 0))
    
    print("\n=== Testing get_stock_disposal_status('3564') ===")
    print(get_stock_disposal_status('3564'))
    
    print("\n=== Testing get_stock_disposal_status('3081') ===")
    print(get_stock_disposal_status('3081'))
