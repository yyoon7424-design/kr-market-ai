import os
import json
import datetime
import requests

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

YAHOO_TICKERS = {
    "KOSPI": "^KS11",
    "KOSDAQ": "^KQ11",
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
}

SECTOR_TICKERS = {
    "반도체": "091160.KS",
    "자동차": "091180.KS",
    "바이오": "207490.KS",
    "금융": "139270.KS",
    "2차전지": "305720.KS",
    "방산": "229200.KS",
    "로봇": "411060.KS",
}

THEME_TICKERS = {
    "AI반도체": "000660.KS",
    "2차전지": "373220.KS",
    "바이오": "068270.KS",
    "방산": "012450.KS",
    "로봇": "064350.KS",
}

def get_last_trading_date():
    kst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    weekday = kst.weekday()
    if weekday == 5:
        kst -= datetime.timedelta(days=1)
    elif weekday == 6:
        kst -= datetime.timedelta(days=2)
    else:
        kst -= datetime.timedelta(days=1)
        if kst.weekday() == 5:
            kst -= datetime.timedelta(days=1)
        elif kst.weekday() == 6:
            kst -= datetime.timedelta(days=2)
    return kst.strftime("%Y%m%d"), kst.strftime("%Y년 %m월 %d일")

def fetch_yahoo(ticker, trading_date):
    headers = {"User-Agent": "Mozilla/5.0"}
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=20d"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        result = data["chart"]["result"][0]
        timestamps = result.get("timestamp", [])
        closes = result["indicators"]["quote"][0].get("close", [])
        dated = []
        for ts, cl in zip(timestamps, closes):
            if cl is None:
                continue
            dt = datetime.datetime.utcfromtimestamp(ts) + datetime.timedelta(hours=9)
            dated.append((dt.strftime("%Y%m%d"), dt.strftime("%m/%d"), round(cl, 2)))
        dated.sort(key=lambda x: x[0])
        target_idx = None
        for i in range(len(dated)-1, -1, -1):
            if dated[i][0] <= trading_date:
                target_idx = i
                break
        if target_idx is not None and target_idx >= 1:
            current = dated[target_idx][2]
            prev = dated[target_idx - 1][2]
            change_pct = round((current - prev) / prev * 100, 2)
            history = dated[max(0, target_idx-9):target_idx+1]
            print(f"  {ticker}: {dated[target_idx][0]} {current:,.0f} ({change_pct:+.2f}%)")
            return {"price": current, "change_pct": change_pct, "history": history}
        elif target_idx == 0 and dated:
            return {"price": dated[0][2], "change_pct": 0, "history": [dated[0]]}
        else:
            return {"price": 0, "change_pct": 0, "history": []}
    except Exception as e:
        print(f"오류 {ticker}: {e}")
        return {"price": 0, "change_pct": 0, "history": []}

def collect_market_data():
    trading_date, date_label = get_last_trading_date()
    print(f"기준 거래일: {trading_date} ({date_label})")
    market = {}
    for name, ticker in YAHOO_TICKERS.items():
        market[name] = fetch_yahoo(ticker, trading_date)
    sectors = {}
    for name, ticker in SECTOR_TICKERS.items():
        sectors[name] = fetch_yahoo(ticker, trading_date)
    themes = {}
    for name, ticker in THEME_TICKERS.items():
        themes[name] = fetch_yahoo(ticker, trading_date)
    return market, sectors, themes, date_label

def call_claude(market, sectors, themes, date_label):
    sector_text = ", ".join([f"{k}: {v['change_pct']:+.2f}%" for k, v in sectors.items()])
    theme_text = ", ".join([f"{k}: {v['change_pct']:+.2f}% (₩{v['price']:,.0f})" for k, v in themes.items()])
    prompt = f"""당신은 한국 주식시장 전문 애널리스트입니다. 주식 초보자도 이해할 수 있도록 쉽고 친절하게 설명해주세요.
{date_label} 한국 증시 데이터를 분석해 상세한 투자 가이드를 작성해주세요.

주요지수: KOSPI {market['KOSPI']['price']:,.2f} ({market['KOSPI']['change_pct']:+.2f}%), KOSDAQ {market['KOSDAQ']['price']:,.2f} ({market['KOSDAQ']['change_pct']:+.2f}%)
섹터별 등락률: {sector_text}
테마별 대장주: {theme_text}
주요종목: {', '.join([f"{k} {v['change_pct']:+.2f}%" for k, v in market.items() if k not in ('KOSPI','KOSDAQ')])}

다음 구조로 한국어로 상세하게 작성하세요. 각 섹션을 충분히 자세하게 써주세요:

### 1. 오늘 시장 한눈에 보기
- KOSPI/KOSDAQ 흐름을 초보자도 이해할 수 있게 비유를 들어 설명
- 오늘 시장 분위기 (예: "전반적으로 하락장, 반도체만 선방" 등)
- 특히 주목할 만한 움직임

### 2. 섹터별 상세 분석
각 섹터별로:
- 오늘 등락률과 그 이유 (초보자 설명 포함)
- 해당 섹터에 영향을 준 뉴스/이벤트 추정

### 3. 오늘의 주도 테마와 소외 테마
- 돈이 몰린 테마와 빠진 테마
- 왜 그런지 쉽게 설명

### 4. 투자 전략 (초보자용)
- 지금 같은 시장에서 초보자가 취해야 할 자세
- 단기(1주) / 중기(1~3개월) 전략
- 절대 하지 말아야 할 것

### 5. 추천 종목 3개
각 종목별로:
- 종목명과 왜 추천하는지 (쉬운 설명)
- 지금 가격이 비싼지 싼지
- 진입 가격대 / 목표가 / 손절가
- 예상 수익률과 리스크

### 6. 주의/회피 종목
- 지금 당장 사면 안 되는 종목과 이유

### 7. 초보자를 위한 오늘의 핵심 교훈
- 오늘 시장에서 배울 수 있는 투자 원칙 1가지

### 8. 내일/다음 거래일 예측
- 예상 시나리오 (낙관/중립/비관)
- 주시해야 할 지표와 뉴스"""

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    }
    r = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=body, timeout=90)
    resp = r.json()
    if "content" not in resp:
        print(f"API 오류: {resp}")
        return "분석 데이터를 불러오는 중 오류가 발생했습니다."
    return resp["content"][0]["text"]

def make_sparkline(history, width=120, height=40, is_index=False):
    if len(history) < 2:
        return ""
    prices = [h[2] for h in history]
    min_p = min(prices)
    max_p = max(prices)
    if max_p == min_p:
        return ""
    change = prices[-1] - prices[0]
    color = "#ff4444" if change >= 0 else "#1976d2"
    points = []
    for i, p in enumerate(prices):
        x = i / (len(prices) - 1) * width
        y = height - (p - min_p) / (max_p - min_p) * height
        points.append(f"{x:.1f},{y:.1f}")
    polyline = " ".join(points)
    return f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" style="overflow:visible"><polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round"/></svg>'

def build_html(market, sectors, themes, analysis, date_label):
    kst_now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    updated_str = kst_now.strftime("%Y%m%d %H:%M KST")
    kospi = market.get("KOSPI", {})
    kosdaq = market.get("KOSDAQ", {})

    def cc(v):
        if isinstance(v, (int, float)):
            return "up" if v >= 0 else "down"
        return "flat"

    def ca(v):
        if isinstance(v, (int, float)):
            return "▲" if v >= 0 else "▼"
        return "-"

    kp = kospi.get("change_pct", 0)
    kq = kosdaq.get("change_pct", 0)

    kospi_spark = make_sparkline(kospi.get("history", []), width=200, height=60, is_index=True)
    kosdaq_spark = make_sparkline(kosdaq.get("history", []), width=200, height=60, is_index=True)

    stock_cards = ""
    for name, d in market.items():
        if name in ("KOSPI", "KOSDAQ"):
            continue
        cp = d.get("change_pct", 0)
        spark = make_sparkline(d.get("history", []), width=80, height=30)
        stock_cards += f'''<div class="stock-card {cc(cp)}">
  <div class="stock-name">{name}</div>
  <div class="stock-price">₩{d.get("price", 0):,.0f}</div>
  <div class="stock-change {cc(cp)}">{ca(cp)} {abs(cp):.2f}%</div>
  <div class="spark">{spark}</div>
</div>'''

    sorted_sectors = sorted(sectors.items(), key=lambda x: x[1].get("change_pct", 0), reverse=True)
    sector_cards = ""
    for name, d in sorted_sectors:
        cp = d.get("change_pct", 0)
        bar_width = min(abs(cp) * 8, 100)
        sector_cards += f'''<div class="sector-row">
  <div class="sector-name">{name}</div>
  <div class="sector-bar-wrap">
    <div class="sector-bar {cc(cp)}" style="width:{bar_width}%"></div>
  </div>
  <div class="sector-pct {cc(cp)}">{ca(cp)} {abs(cp):.2f}%</div>
</div>'''

    theme_cards = ""
    for name, d in themes.items():
        cp = d.get("change_pct", 0)
        spark = make_sparkline(d.get("history", []), width=80, height=30)
        theme_cards += f'''<div class="theme-card {cc(cp)}">
  <div class="theme-name">{name}</div>
  <div class="theme-price">₩{d.get("price", 0):,.0f}</div>
  <div class="theme-change {cc(cp)}">{ca(cp)} {abs(cp):.2f}%</div>
  <div class="spark">{spark}</div>
</div>'''

    import re
    html_analysis = analysis
    html_analysis = re.sub(r"### (.+)", r"<h3>\1</h3>", html_analysis)
    html_analysis = re.sub(r"## (.+)", r"<h2>\1</h2>", html_analysis)
    html_analysis = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html_analysis)
    html_analysis = re.sub(r"^- (.+)$", r"<li>\1</li>", html_analysis, flags=re.MULTILINE)
    html_analysis = html_analysis.replace("\n\n", "</p><p>")
    html_analysis = f"<p>{html_analysis}</p>"

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>KRMarketAI</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;700;900&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0a0e1a;--surface:#111827;--border:#1e2d45;--accent:#00d4ff;--up:#ff4444;--down:#1976d2;--flat:#94a3b8;--text:#e2e8f0;--dim:#64748b;}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:var(--bg);color:var(--text);font-family:'Noto Sans KR',sans-serif;min-height:100vh;}}
header{{border-bottom:1px solid var(--border);padding:20px 40px;display:flex;justify-content:space-between;align-items:center;background:rgba(17,24,39,0.95);position:sticky;top:0;z-index:100;}}
.logo{{font-size:20px;font-weight:900;}}.logo span{{color:var(--accent);}}
.ts{{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--dim);}}
.wrap{{max-width:1200px;margin:0 auto;padding:32px 24px;}}
.data-date{{text-align:center;color:var(--accent);font-size:14px;font-weight:700;margin-bottom:28px;padding:12px;background:var(--surface);border-radius:8px;border:1px solid var(--border);}}
.idx{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:8px;}}
.idx-card{{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:24px;display:flex;justify-content:space-between;align-items:center;}}
.idx-left .idx-label{{font-size:12px;color:var(--dim);letter-spacing:1px;text-transform:uppercase;margin-bottom:6px;}}
.idx-left .idx-val{{font-family:'JetBrains Mono',monospace;font-size:32px;font-weight:700;margin-bottom:4px;}}
.idx-left .idx-chg{{font-family:'JetBrains Mono',monospace;font-size:16px;font-weight:700;}}
.up{{color:var(--up);}}.down{{color:var(--down);}}.flat{{color:var(--flat);}}
.sec{{font-size:12px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--dim);margin:28px 0 14px;padding-bottom:8px;border-bottom:1px solid var(--border);}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px;}}
.stock-card{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px;}}
.stock-card.up{{border-left:3px solid var(--up);}}.stock-card.down{{border-left:3px solid var(--down);}}
.stock-name{{font-size:12px;color:var(--dim);margin-bottom:4px;}}
.stock-price{{font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:700;margin-bottom:2px;}}
.stock-change{{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;margin-bottom:6px;}}
.spark{{opacity:0.8;}}
.sector-row{{display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid var(--border);}}
.sector-name{{width:60px;font-size:13px;font-weight:700;flex-shrink:0;}}
.sector-bar-wrap{{flex:1;background:rgba(255,255,255,0.05);border-radius:4px;height:8px;overflow:hidden;}}
.sector-bar{{height:100%;border-radius:4px;transition:width 0.3s;}}
.sector-bar.up{{background:var(--up);}}.sector-bar.down{{background:var(--down);}}
.sector-pct{{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;width:70px;text-align:right;flex-shrink:0;}}
.theme-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px;}}
.theme-card{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px;}}
.theme-card.up{{border-left:3px solid var(--up);}}.theme-card.down{{border-left:3px solid var(--down);}}
.theme-name{{font-size:12px;color:var(--dim);margin-bottom:4px;font-weight:700;}}
.theme-price{{font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:700;margin-bottom:2px;}}
.theme-change{{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;margin-bottom:6px;}}
.report{{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:40px;line-height:1.9;}}
.report h3{{font-size:16px;font-weight:700;color:var(--accent);margin:24px 0 10px;padding:10px 14px;background:rgba(0,212,255,0.05);border-left:3px solid var(--accent);border-radius:0 6px 6px 0;}}
.report li{{margin-left:20px;margin-bottom:6px;color:#cbd5e1;}}
.report strong{{color:#fff;}}
.report p{{margin-bottom:12px;color:#cbd5e1;}}
.disc{{margin-top:32px;padding:16px;border-radius:8px;background:rgba(255,68,68,0.06);border:1px solid rgba(255,68,68,0.2);font-size:12px;color:var(--dim);}}
footer{{text-align:center;padding:28px;font-size:12px;color:var(--dim);border-top:1px solid var(--border);margin-top:60px;}}
@media(max-width:600px){{.idx{{grid-template-columns:1fr;}}header{{padding:14px 16px;}}.wrap{{padding:20px 14px;}}.report{{padding:22px;}}}}
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
<div class="idx-left">
<div class="idx-label">KOSPI</div>
<div class="idx-val {cc(kp)}">{kospi.get("price", 0):,.2f}</div>
<div class="idx-chg {cc(kp)}">{ca(kp)} {abs(kp):.2f}%</div>
</div>
<div class="idx-right">{kospi_spark}</div>
</div>
<div class="idx-card">
<div class="idx-left">
<div class="idx-label">KOSDAQ</div>
<div class="idx-val {cc(kq)}">{kosdaq.get("price", 0):,.2f}</div>
<div class="idx-chg {cc(kq)}">{ca(kq)} {abs(kq):.2f}%</div>
</div>
<div class="idx-right">{kosdaq_spark}</div>
</div>
</div>

<div class="sec">📊 섹터별 등락률</div>
<div>{sector_cards}</div>

<div class="sec">🎯 테마별 대장주</div>
<div class="theme-grid">{theme_cards}</div>

<div class="sec">📈 주요 종목</div>
<div class="grid">{stock_cards}</div>

<div class="sec">🤖 AI 종합 분석 리포트 (초보자용 상세 설명)</div>
<div class="report">
{html_analysis}
<div class="disc">⚠️ 면책고지: 이 분석은 Claude AI가 생성한 참고 정보입니다. 투자 결정의 최종 책임은 투자자 본인에게 있으며, 본 리포트는 투자 권유가 아닙니다.</div>
</div>
</div>
<footer>KRMarketAI · Powered by Claude AI · Data: Yahoo Finance</footer>
</body>
</html>"""

def main():
    market, sectors, themes, date_label = collect_market_data()
    analysis = call_claude(market, sectors, themes, date_label)
    html = build_html(market, sectors, themes, analysis, date_label)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Done!")

if __name__ == "__main__":
    main()
