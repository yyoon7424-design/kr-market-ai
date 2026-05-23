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
    "방산": "1570.KS",
    "로봇": "411060.KS",
}

THEME_TICKERS = {
    "AI반도체_대장": "000660.KS",
    "2차전지_대장": "373220.KS",
    "바이오_대장": "068270.KS",
    "방산_대장": "012450.KS",
    "로봇_대장": "064350.KS",
}

def get_last_trading_date():
    kst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    if kst.weekday() == 5:
        kst -= datetime.timedelta(days=1)
    elif kst.weekday() == 6:
        kst -= datetime.timedelta(days=2)
    return kst.strftime("%Y%m%d"), kst.strftime("%Y년 %m월 %d일")

def fetch_yahoo(ticker, trading_date):
    headers = {"User-Agent": "Mozilla/5.0"}
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=10d"
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
            dated.append((dt.strftime("%Y%m%d"), cl))
        dated.sort(key=lambda x: x[0])
        target_idx = None
        for i, (d, _) in enumerate(dated):
            if d == trading_date:
                target_idx = i
                break
        if target_idx is None and dated:
            target_idx = len(dated) - 1
        if target_idx is not None and target_idx >= 1:
            current = dated[target_idx][1]
            prev = dated[target_idx - 1][1]
            change_pct = round((current - prev) / prev * 100, 2)
            return {"price": round(current, 2), "change_pct": change_pct}
        elif target_idx == 0 and dated:
            return {"price": round(dated[0][1], 2), "change_pct": 0}
        else:
            return {"price": 0, "change_pct": 0}
    except Exception as e:
        print(f"오류 {ticker}: {e}")
        return {"price": 0, "change_pct": 0}

def fetch_krx_foreign_institution(trading_date):
    url = "http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "http://data.krx.co.kr",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    result = {"외국인_순매수": [], "기관_순매수": [], "외국인_순매도": [], "기관_순매도": []}
    try:
        r = requests.post(url, headers=headers, timeout=15, data={
            "bld": "dbms/MDC/STAT/standard/MDCSTAT02401",
            "locale": "ko_KR",
            "mktId": "STK",
            "trdDd": trading_date,
            "invstTpCd": "4000",
            "share": "1",
            "money": "1",
            "csvxls_isNo": "false",
        })
        items = r.json().get("output", [])
        buy = [(i.get("ISU_ABBRV", ""), int(i.get("NETBUY_TRDVAL", "0").replace(",", "").replace("-", "0") or 0)) for i in items if i.get("NETBUY_TRDVAL", "").startswith("-") is False and i.get("NETBUY_TRDVAL", "0") != "0"]
        sell = [(i.get("ISU_ABBRV", ""), abs(int(i.get("NETBUY_TRDVAL", "0").replace(",", "") or 0))) for i in items if i.get("NETBUY_TRDVAL", "").startswith("-")]
        buy.sort(key=lambda x: x[1], reverse=True)
        sell.sort(key=lambda x: x[1], reverse=True)
        result["외국인_순매수"] = [x[0] for x in buy[:5]]
        result["외국인_순매도"] = [x[0] for x in sell[:5]]
    except Exception as e:
        print(f"외국인 데이터 오류: {e}")
    try:
        r = requests.post(url, headers=headers, timeout=15, data={
            "bld": "dbms/MDC/STAT/standard/MDCSTAT02401",
            "locale": "ko_KR",
            "mktId": "STK",
            "trdDd": trading_date,
            "invstTpCd": "2000",
            "share": "1",
            "money": "1",
            "csvxls_isNo": "false",
        })
        items = r.json().get("output", [])
        buy = [(i.get("ISU_ABBRV", ""), int(i.get("NETBUY_TRDVAL", "0").replace(",", "").replace("-", "0") or 0)) for i in items if not i.get("NETBUY_TRDVAL", "").startswith("-") and i.get("NETBUY_TRDVAL", "0") != "0"]
        sell = [(i.get("ISU_ABBRV", ""), abs(int(i.get("NETBUY_TRDVAL", "0").replace(",", "") or 0))) for i in items if i.get("NETBUY_TRDVAL", "").startswith("-")]
        buy.sort(key=lambda x: x[1], reverse=True)
        sell.sort(key=lambda x: x[1], reverse=True)
        result["기관_순매수"] = [x[0] for x in buy[:5]]
        result["기관_순매도"] = [x[0] for x in sell[:5]]
    except Exception as e:
        print(f"기관 데이터 오류: {e}")
    return result

def collect_market_data():
    trading_date, date_label = get_last_trading_date()
    print(f"기준 거래일: {trading_date}")

    results = {}
    for name, ticker in YAHOO_TICKERS.items():
        results[name] = fetch_yahoo(ticker, trading_date)
        print(f"  {name}: {results[name]}")

    sectors = {}
    for name, ticker in SECTOR_TICKERS.items():
        sectors[name] = fetch_yahoo(ticker, trading_date)
        print(f"  섹터 {name}: {sectors[name]}")

    themes = {}
    for name, ticker in THEME_TICKERS.items():
        themes[name] = fetch_yahoo(ticker, trading_date)
        print(f"  테마 {name}: {themes[name]}")

    print("외국인/기관 매매 수집 중...")
    investor = fetch_krx_foreign_institution(trading_date)
    print(f"  외국인 순매수: {investor['외국인_순매수']}")
    print(f"  기관 순매수: {investor['기관_순매수']}")

    return results, sectors, themes, investor, date_label

def call_claude(market_data, sectors, themes, investor, date_label):
    prompt = f"""당신은 한국 주식시장 전문 애널리스트입니다.
아래 {date_label} 기준 데이터를 종합 분석해 투자 가이드를 작성해주세요.

## 주요 지수 및 종목 데이터
{json.dumps(market_data, ensure_ascii=False)}

## 섹터별 ETF 등락률
{json.dumps(sectors, ensure_ascii=False)}

## 테마별 대장주 흐름
{json.dumps(themes, ensure_ascii=False)}

## 외국인/기관 매매 동향
{json.dumps(investor, ensure_ascii=False)}

다음 구조로 한국어로 상세하게 작성하세요:

### 1. 오늘의 시장 요약
### 2. 섹터별 분석 (강세/약세 섹터, 이유 포함)
### 3. 테마별 분석 (주도 테마, 소외 테마)
### 4. 외국인/기관 매매 동향 분석
### 5. 투자 전략 (단기/중기)
### 6. 추천 종목 3개 (종목명, 이유, 진입가, 목표가, 손절가)
### 7. 주의 종목
### 8. 다음 거래일 관전 포인트"""

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 3000,
        "messages": [{"role": "user", "content": prompt}],
    }
    r = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=body, timeout=60)
    return r.json()["content"][0]["text"]

def build_html(market_data, sectors, themes, investor, analysis, date_label):
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

    sector_cards = ""
    sorted_sectors = sorted(sectors.items(), key=lambda x: x[1].get("change_pct", 0), reverse=True)
    for name, d in sorted_sectors:
        cp = d.get("change_pct", 0)
        sector_cards += f'<div class="sector-card {cc(cp)}"><div class="sector-name">{name}</div><div class="sector-change {cc(cp)}">{ca(cp)} {abs(cp):.2f}%</div></div>'

    theme_cards = ""
    for name, d in themes.items():
        cp = d.get("change_pct", 0)
        label = name.replace("_대장", "").replace("_", " ")
        theme_cards += f'<div class="theme-card {cc(cp)}"><div class="theme-name">{label}</div><div class="theme-price">₩{d.get("price", 0):,.0f}</div><div class="theme-change {cc(cp)}">{ca(cp)} {abs(cp):.2f}%</div></div>'

    def make_investor_list(items, cls):
        if not items:
            return '<li style="color:var(--dim)">데이터 없음</li>'
        return "".join([f'<li class="{cls}">{item}</li>' for item in items])

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
.data-date{{text-align:center;color:var(--accent);font-size:14px;font-weight:700;margin-bottom:32px;padding:12px;background:var(--surface);border-radius:8px;border:1px solid var(--border);}}
.idx{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:40px;}}
.idx-card{{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:28px;}}
.idx-label{{font-size:12px;color:var(--dim);letter-spacing:1px;text-transform:uppercase;margin-bottom:8px;}}
.idx-val{{font-family:'JetBrains Mono',monospace;font-size:36px;font-weight:700;margin-bottom:4px;}}
.idx-chg{{font-family:'JetBrains Mono',monospace;font-size:18px;font-weight:700;}}
.up{{color:var(--up);}}.down{{color:var(--down);}}.flat{{color:var(--flat);}}
.sec{{font-size:13px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--dim);margin-bottom:16px;padding-bottom:8px;border-bottom:1px solid var(--border);margin-top:40px;}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px;margin-bottom:16px;}}
.stock-card{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px;}}
.stock-card.up{{border-left:3px solid var(--up);}}.stock-card.down{{border-left:3px solid var(--down);}}
.stock-name{{font-size:13px;color:var(--dim);margin-bottom:6px;}}
.stock-price{{font-family:'JetBrains Mono',monospace;font-size:15px;font-weight:700;margin-bottom:4px;}}
.stock-change{{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;}}
.sector-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:10px;margin-bottom:16px;}}
.sector-card{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px;text-align:center;}}
.sector-card.up{{border-top:3px solid var(--up);}}.sector-card.down{{border-top:3px solid var(--down);}}
.sector-name{{font-size:13px;color:var(--text);margin-bottom:6px;font-weight:700;}}
.sector-change{{font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:700;}}
.theme-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin-bottom:16px;}}
.theme-card{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px;}}
.theme-card.up{{border-left:3px solid var(--up);}}.theme-card.down{{border-left:3px solid var(--down);}}
.theme-name{{font-size:12px;color:var(--dim);margin-bottom:4px;}}
.theme-price{{font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:700;margin-bottom:4px;}}
.theme-change{{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;}}
.investor-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px;}}
.investor-card{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px;}}
.investor-title{{font-size:13px;font-weight:700;margin-bottom:12px;}}
.investor-card ul{{list-style:none;}}
.investor-card li{{padding:4px 0;font-size:13px;border-bottom:1px solid var(--border);}}
.investor-card li.buy{{color:var(--up);}}.investor-card li.sell{{color:var(--down);}}
.report{{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:40px;line-height:1.8;}}
.report h3{{font-size:16px;font-weight:700;color:var(--accent);margin:20px 0 8px;}}
.report li{{margin-left:20px;margin-bottom:4px;color:#cbd5e1;}}
.report strong{{color:#fff;}}.report p{{margin-bottom:12px;color:#cbd5e1;}}
.disc{{margin-top:32px;padding:16px;border-radius:8px;background:rgba(255,68,68,0.08);border:1px solid rgba(255,68,68,0.2);font-size:12px;color:var(--dim);}}
footer{{text-align:center;padding:32px;font-size:12px;color:var(--dim);border-top:1px solid var(--border);margin-top:60px;}}
@media(max-width:600px){{.idx,.investor-grid{{grid-template-columns:1fr;}}header{{padding:16px 20px;}}.wrap{{padding:24px 16px;}}.report{{padding:24px;}}}}
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

<div class="sec">📊 섹터별 등락률</div>
<div class="sector-grid">{sector_cards}</div>

<div class="sec">🎯 테마별 대장주</div>
<div class="theme-grid">{theme_cards}</div>

<div class="sec">💰 외국인/기관 매매 동향</div>
<div class="investor-grid">
<div class="investor-card">
<div class="investor-title" style="color:var(--up)">🔺 외국인 순매수 TOP5</div>
<ul>{make_investor_list(investor.get("외국인_순매수", []), "buy")}</ul>
</div>
<div class="investor-card">
<div class="investor-title" style="color:var(--down)">🔻 외국인 순매도 TOP5</div>
<ul>{make_investor_list(investor.get("외국인_순매도", []), "sell")}</ul>
</div>
<div class="investor-card">
<div class="investor-title" style="color:var(--up)">🔺 기관 순매수 TOP5</div>
<ul>{make_investor_list(investor.get("기관_순매수", []), "buy")}</ul>
</div>
<div class="investor-card">
<div class="investor-title" style="color:var(--down)">🔻 기관 순매도 TOP5</div>
<ul>{make_investor_list(investor.get("기관_순매도", []), "sell")}</ul>
</div>
</div>

<div class="sec">🤖 AI 종합 분석 리포트</div>
<div class="report">
{html_analysis}
<div class="disc">면책고지: 이 분석은 Claude AI가 생성한 참고 정보입니다. 투자 결정의 최종 책임은 투자자 본인에게 있습니다.</div>
</div>
</div>

<div class="sec">주요 종목</div>
<div class="grid">{stock_cards}</div>

<footer>KRMarketAI · Powered by Claude AI · Data: Yahoo Finance / KRX</footer>
</div>
</body>
</html>"""

def main():
    market_data, sectors, themes, investor, date_label = collect_market_data()
    analysis = call_claude(market_data, sectors, themes, investor, date_label)
    html = build_html(market_data, sectors, themes, investor, analysis, date_label)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Done!")

if __name__ == "__main__":
    main()
