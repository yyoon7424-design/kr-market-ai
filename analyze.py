    import os
import json
import datetime
import requests

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

STOCK_CODES = {
    "삼성전자": "005930",
    "SK하이닉스": "000660",
    "NAVER": "035420",
    "카카오": "035720",
    "현대차": "005380",
    "LG에너지솔루션": "373220",
    "셀트리온": "068270",
    "POSCO홀딩스": "005490",
    "기아": "000270",
    "KB금융": "105560",
}

YAHOO_TICKERS = {
    "삼성전자": "005930.KS",
    "SK하이닉스": "000660.KS",
    "NAVER": "035420.KS",
    "카카오": "035720.KS",
    "현대차": "005380.KS",
    "LG에너지솔루션": "373220.KS",
    "셀트리온": "068270.KS",
    "POSCO홀딩스": "005490.KS",
    "기아": "000270.KS",
    "KB금융": "105560.KS",
    "KOSPI": "^KS11",
    "KOSDAQ": "^KQ11",
}

def get_last_trading_date():
    """가장 최근 거래일 날짜 반환 (주말이면 금요일)"""
    kst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    weekday = kst.weekday()
    if weekday == 5:  # 토요일
        kst -= datetime.timedelta(days=1)
    elif weekday == 6:  # 일요일
        kst -= datetime.timedelta(days=2)
    return kst.strftime("%Y%m%d"), kst.strftime("%Y년 %m월 %d일")

def fetch_krx_data(date_str):
    """KRX에서 지수 + 종목 데이터 조회"""
    url = "http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "http://data.krx.co.kr",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    results = {}

    # 지수 조회
    try:
        r = requests.post(url, headers=headers, timeout=10, data={
            "bld": "dbms/MDC/STAT/standard/MDCSTAT00301",
            "locale": "ko_KR",
            "trdDd": date_str,
            "share": "1",
            "money": "1",
            "csvxls_isNo": "false",
        })
        for item in r.json().get("output", []):
            name = item.get("IDX_NM", "")
            price = float(item.get("CLSPRC_IDX", "0").replace(",", ""))
            change_pct = float(item.get("FLUC_RT", "0").replace(",", ""))
            if item.get("UPDN_SGNL") == "2":
                change_pct = -change_pct
            if "코스피" in name and "200" not in name and "배당" not in name:
                results["KOSPI"] = {"price": price, "change_pct": change_pct}
            elif "코스닥" in name and "150" not in name and "배당" not in name:
                results["KOSDAQ"] = {"price": price, "change_pct": change_pct}
    except Exception as e:
        print(f"KRX 지수 오류: {e}")

    # 종목 조회
    try:
        r = requests.post(url, headers=headers, timeout=15, data={
            "bld": "dbms/MDC/STAT/standard/MDCSTAT01501",
            "locale": "ko_KR",
            "mktId": "STK",
            "trdDd": date_str,
            "share": "1",
            "money": "1",
            "csvxls_isNo": "false",
        })
        stock_map = {}
        for item in r.json().get("output", []):
            code = item.get("ISU_SRT_CD", "")
            price = float(item.get("TDD_CLSPRC", "0").replace(",", ""))
            change_pct = float(item.get("FLUC_RT", "0").replace(",", ""))
            if item.get("UPDN_SGNL") == "2":
                change_pct = -change_pct
            stock_map[code] = {"price": price, "change_pct": change_pct}

        for name, code in STOCK_CODES.items():
            if code in stock_map:
                results[name] = stock_map[code]
    except Exception as e:
        print(f"KRX 종목 오류: {e}")

    return results

def fetch_yahoo_data():
    """Yahoo Finance에서 종가 기준 등락률 직접 계산"""
    results = {}
    headers = {"User-Agent": "Mozilla/5.0"}
    for name, ticker in YAHOO_TICKERS.items():
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d"
            r = requests.get(url, headers=headers, timeout=10)
            data = r.json()
            closes = data["chart"]["result"][0]["indicators"]["quote"][0].get("close", [])
            closes = [c for c in closes if c is not None]
            if len(closes) >= 2:
                current = closes[-1]
                prev = closes[-2]
                change_pct = round((current - prev) / prev * 100, 2)
                results[name] = {"price": round(current, 2), "change_pct": change_pct}
            else:
                results[name] = {"price": 0, "change_pct": 0}
        except Exception as e:
            results[name] = {"price": 0, "change_pct": 0}
    return results

def collect_market_data():
    date_str, _ = get_last_trading_date()
    print(f"거래일: {date_str}")

    # KRX 먼저 시도
    print("KRX 데이터 수집 중...")
    results = fetch_krx_data(date_str)

    # KRX 실패 시 Yahoo Finance로 대체
    if not results.get("KOSPI") or results["KOSPI"]["price"] == 0:
        print("KRX 실패 → Yahoo Finance로 대체...")
        results = fetch_yahoo_data()

    for name, val in results.items():
        print(f"  {name}: {val}")

    return results

def call_claude(market_data, date_label):
    prompt = f"""당신은 한국 주식시장 전문 애널리스트입니다.
아래 {date_label} 기준 한국 증시 데이터를 분석해 투자 가이드를 작성해주세요.

데이터: {json.dumps(market_data, ensure_ascii=False)}

다음 구조로 한국어로 작성하세요:
### 1. 오늘의 시장 요약
### 2. 주요 지표 해석
### 3. 투자 전략
### 4. 추천 종목 3개 (종목명, 이유, 진입가, 목표가, 손절가)
### 5. 주의 종목
### 6. 다음 거래일 관전 포인트"""

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}],
    }
    r = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=body, timeout=60)
    return r.json()["content"][0]["text"]

def build_html(market_data, analysis, date_label):
    kst_now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    updated_str = kst_now.strftime("%Y%m%d %H:%M KST")
    kospi = market_data.get("KOSPI", {})
    kosdaq = market_data.get("KOSDAQ", {})

    def cc(v):
        if isinstance(v, (int, float)):
            return "up" if v > 0 else ("down" if v < 0 else "flat")
        return "flat"

    def ca(v):
        if isinstance(v, (int, float)):
            return "▲" if v > 0 else ("▼" if v < 0 else "-")
        return "-"

    stock_cards = ""
    for name, d in market_data.items():
        if name in ("KOSPI", "KOSDAQ"):
            continue
        cp = d.get("change_pct", 0)
        stock_cards += f'<div class="stock-card {cc(cp)}"><div class="stock-name">{name}</div><div class="stock-price">₩{d.get("price", 0):,.0f}</div><div class="stock-change {cc(cp)}">{ca(cp)} {abs(cp):.2f}%</div></div>'

    import re
    html_analysis = analysis
    html_analysis = re.sub(r"### (.+)", r"<h3>\1</h3>", html_analysis)
    html_analysis = re.sub(r"## (.+)", r"<h2>\1</h2>", html_analysis)
    html_analysis = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html_analysis)
    html_analysis = re.sub(r"^- (.+)$", r"<li>\1</li>", html_analysis, flags=re.MULTILINE)
    html_analysis = html_analysis.replace("\n\n", "</p><p>")
    html_analysis = f"<p>{html_analysis}</p>"

    kp = kospi.get("change_pct", 0)
    kq = kosdaq.get("change_pct", 0)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>KRMarketAI</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;700;900&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0a0e1a;--surface:#111827;--border:#1e2d45;--accent:#00d4ff;--up:#00e676;--down:#ff4444;--flat:#94a3b8;--text:#e2e8f0;--dim:#64748b;}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:var(--bg);color:var(--text);font-family:'Noto Sans KR',sans-serif;min-height:100vh;}}
header{{border-bottom:1px solid var(--border);padding:24px 40px;display:flex;justify-content:space-between;align-items:center;background:rgba(17,24,39,0.9);position:sticky;top:0;z-index:100;}}
.logo{{font-size:20px;font-weight:900;}}.logo span{{color:var(--accent);}}
.ts{{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--dim);}}
.wrap{{max-width:1200px;margin:0 auto;padding:40px 24px;}}
.idx{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:40px;}}
.idx-card{{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:28px;}}
.idx-label{{font-size:12px;color:var(--dim);letter-spacing:1px;text-transform:uppercase;margin-bottom:8px;}}
.idx-val{{font-family:'JetBrains Mono',monospace;font-size:36px;font-weight:700;margin-bottom:4px;}}
.idx-chg{{font-family:'JetBrains Mono',monospace;font-size:18px;font-weight:700;}}
.up{{color:var(--up);}}.down{{color:var(--down);}}.flat{{color:var(--flat);}}
.data-date{{text-align:center;color:var(--dim);font-size:13px;margin-bottom:32px;}}
.sec{{font-size:13px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--dim);margin-bottom:16px;padding-bottom:8px;border-bottom:1px solid var(--border);}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px;margin-bottom:40px;}}
.stock-card{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px;}}
.stock-card.up{{border-left:3px solid var(--up);}}.stock-card.down{{border-left:3px solid var(--down);}}
.stock-name{{font-size:13px;color:var(--dim);margin-bottom:6px;}}
.stock-price{{font-family:'JetBrains Mono',monospace;font-size:15px;font-weight:700;margin-bottom:4px;}}
.stock-change{{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;}}
.report{{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:40px;line-height:1.8;}}
.report h3{{font-size:16px;font-weight:700;color:var(--accent);margin:20px 0 8px;}}
.report li{{margin-left:20px;margin-bottom:4px;color:#cbd5e1;}}
.report strong{{color:#fff;}}.report p{{margin-bottom:12px;color:#cbd5e1;}}
.disc{{margin-top:32px;padding:16px;border-radius:8px;background:rgba(255,68,68,0.08);border:1px solid rgba(255,68,68,0.2);font-size:12px;color:var(--dim);}}
footer{{text-align:center;padding:32px;font-size:12px;color:var(--dim);border-top:1px solid var(--border);margin-top:60px;}}
@media(max-width:600px){{.idx{{grid-template-columns:1fr;}}header{{padding:16px 20px;}}.wrap{{padding:24px 16px;}}.report{{padding:24px;}}}}
</style>
</head>
<body>
<header>
<div class="logo">KR<span>Market</span>AI</div>
<div class="ts">updated: {updated_str}</div>
</header>
<div class="wrap">
<div class="data-date">📅 {date_label} 기준 데이터</div>
<div class="idx">
<div class="idx-card">
<div class="idx-label">KOSPI</div>
<div class="idx-val {cc(kp)}">{kospi.get("price", 0):,.2f}</div>
<div class="idx-chg {cc(kp)}">{ca(kp)} {abs(kp):.2f}%</div>
</div>
<div class="idx-card">
<div class="idx-label">KOSDAQ</div>
<div class="idx-val {cc(kq)}">{kosdaq.get("price", 0):,.2f}</div>
<div class="idx-chg {cc(kq)}">{ca(kq)} {abs(kq):.2f}%</div>
</div>
</div>
<div class="sec">주요 종목</div>
<div class="grid">{stock_cards}</div>
<div class="sec">AI 분석 리포트</div>
<div class="report">
{html_analysis}
<div class="disc">면책고지: 이 분석은 Claude AI가 생성한 참고 정보입니다. 투자 결정의 최종 책임은 투자자 본인에게 있습니다.</div>
</div>
</div>
<footer>KRMarketAI · Powered by Claude AI · Data: KRX / Yahoo Finance</footer>
</body>
</html>"""

def main():
    date_str, date_label = get_last_trading_date()
    market_data = collect_market_data()
    analysis = call_claude(market_data, date_label)
    html = build_html(market_data, analysis, date_label)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Done!")

if __name__ == "__main__":
    main()
