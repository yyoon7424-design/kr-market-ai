import os
import json
import datetime
import requests

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

TICKERS = {
    "KOSPI": "^KS11",
    "KOSDAQ": "^KQ11",
    "Samsung": "005930.KS",
    "SK Hynix": "000660.KS",
    "NAVER": "035420.KS",
    "Kakao": "035720.KS",
    "Hyundai": "005380.KS",
    "LG Energy": "373220.KS",
    "Celltrion": "068270.KS",
    "POSCO": "005490.KS",
    "Kia": "000270.KS",
    "KB Finance": "105560.KS",
}

def fetch_quote(ticker):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        meta = data["chart"]["result"][0]["meta"]
        current = meta.get("regularMarketPrice", 0)
        change_pct = meta.get("regularMarketChangePercent", 0)
        prev_close = meta.get("chartPreviousClose", 0) or meta.get("previousClose", 0)
        return {
            "ticker": ticker,
            "price": round(current, 2),
            "prev_close": round(prev_close, 2),
            "change_pct": round(change_pct, 2),
            "volume": meta.get("regularMarketVolume", 0),
            "52w_high": meta.get("fiftyTwoWeekHigh", 0),
            "52w_low": meta.get("fiftyTwoWeekLow", 0),
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}

def collect_market_data():
    results = {}
    for name, ticker in TICKERS.items():
        results[name] = fetch_quote(ticker)
        print(f"  {name}: price={results[name].get('price')} change={results[name].get('change_pct')}%")
    return results

def call_claude(market_data):
    kst_now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    date_str = kst_now.strftime("%Y년 %m월 %d일")
    prompt = f"""당신은 한국 주식시장 전문 애널리스트입니다.
아래 {date_str} 기준 한국 증시 데이터를 분석해 투자 가이드를 작성해주세요.

데이터: {json.dumps(market_data, ensure_ascii=False)}

다음 구조로 한국어로 작성하세요:
### 1. 오늘의 시장 요약
### 2. 주요 지표 해석
### 3. 투자 전략
### 4. 추천 종목 3개 (종목명, 이유, 진입가, 목표가, 손절가)
### 5. 주의 종목
### 6. 내일 관전 포인트"""

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

def build_html(market_data, analysis):
    kst_now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    date_str = kst_now.strftime("%Y%m%d %H:%M KST")
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
        if name in ("KOSPI", "KOSDAQ") or "error" in d:
            continue
        cp = d.get("change_pct", 0)
        stock_cards += f'<div class="stock-card {cc(cp)}"><div class="stock-name">{name}</div><div class="stock-price">{d.get("price", 0):,.0f}</div><div class="stock-change {cc(cp)}">{ca(cp)} {abs(cp):.2f}%</div></div>'

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
<div class="ts">updated: {date_str}</div>
</header>
<div class="wrap">
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
<footer>KRMarketAI · Powered by Claude AI · Data: Yahoo Finance</footer>
</body>
</html>"""

def main():
    market_data = collect_market_data()
    analysis = call_claude(market_data)
    html = build_html(market_data, analysis)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Done!")

if __name__ == "__main__":
    main()
