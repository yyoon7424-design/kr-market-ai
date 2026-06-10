import os, re, datetime, requests

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "")

STOCK_TICKERS = {
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

SECTORS = {
    "반도체": "091160.KS", "자동차": "091180.KS", "바이오": "207490.KS",
    "금융": "139270.KS", "2차전지": "305720.KS", "방산": "229200.KS", "로봇": "411060.KS",
}

THEMES = {
    "AI반도체": "000660.KS", "2차전지": "373220.KS", "바이오": "068270.KS",
    "방산": "012450.KS", "로봇": "064350.KS",
}

def get_trading_date():
    kst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    w = kst.weekday()
    if w == 5: kst -= datetime.timedelta(days=1)
    elif w == 6: kst -= datetime.timedelta(days=2)
    elif kst.hour < 16:
        kst -= datetime.timedelta(days=1)
        if kst.weekday() == 5: kst -= datetime.timedelta(days=1)
        elif kst.weekday() == 6: kst -= datetime.timedelta(days=2)
    return kst.strftime("%Y%m%d"), kst.strftime("%Y년 %m월 %d일")

def fetch_index_alpha(symbol, tdate):
    """Alpha Vantage로 KOSPI/KOSDAQ 지수 조회"""
    try:
        url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={ALPHA_VANTAGE_KEY}&outputsize=compact"
        r = requests.get(url, timeout=15)
        data = r.json()
        ts = data.get("Time Series (Daily)", {})
        if not ts:
            print(f"  Alpha Vantage 오류 {symbol}: {data}")
            return {"price": 0, "change_pct": 0, "history": []}
        dates = sorted(ts.keys(), reverse=True)
        # tdate 이하 가장 최근 날짜 찾기
        target = next((d for d in dates if d.replace("-","") <= tdate), None)
        if not target:
            return {"price": 0, "change_pct": 0, "history": []}
        t_idx = dates.index(target)
        cur = float(ts[target]["4. close"])
        history = []
        for d in reversed(dates[t_idx:t_idx+10]):
            history.append([d.replace("-",""), round(float(ts[d]["4. close"]), 2)])
        if t_idx + 1 < len(dates):
            prv = float(ts[dates[t_idx+1]]["4. close"])
            change_pct = round((cur - prv) / prv * 100, 2)
        else:
            change_pct = 0
        print(f"  {symbol}: {target} {cur:,.2f} ({change_pct:+.2f}%)")
        return {"price": round(cur, 2), "change_pct": change_pct, "history": history}
    except Exception as e:
        print(f"  Alpha Vantage 오류 {symbol}: {e}")
        return {"price": 0, "change_pct": 0, "history": []}

def fetch_yahoo(ticker, tdate):
    """Yahoo Finance로 개별 종목 조회"""
    try:
        r = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=20d",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        res = r.json()["chart"]["result"][0]
        ts = res.get("timestamp", [])
        cl = res["indicators"]["quote"][0].get("close", [])
        dated = sorted(
            [(datetime.datetime.utcfromtimestamp(t) + datetime.timedelta(hours=9)).strftime("%Y%m%d"), round(c, 2)]
            for t, c in zip(ts, cl) if c is not None
        )
        idx = next((i for i in range(len(dated)-1, -1, -1) if dated[i][0] <= tdate), None)
        if idx is not None and idx >= 1:
            cur, prv = dated[idx][1], dated[idx-1][1]
            hist = dated[max(0, idx-9):idx+1]
            return {"price": cur, "change_pct": round((cur-prv)/prv*100, 2), "history": hist}
        return {"price": 0, "change_pct": 0, "history": []}
    except Exception as e:
        print(f"  Yahoo 오류 {ticker}: {e}")
        return {"price": 0, "change_pct": 0, "history": []}

def collect(tdate):
    print(f"데이터 수집: {tdate}")
    m = {}
    print("  [Alpha Vantage] KOSPI/KOSDAQ 수집...")
    m["KOSPI"] = fetch_index_alpha("399001.KS", tdate)
    m["KOSDAQ"] = fetch_index_alpha("229200.KS", tdate)
    # Alpha Vantage 실패 시 Yahoo 백업
    if m["KOSPI"]["price"] == 0:
        print("  Alpha Vantage 실패, Yahoo 백업 사용...")
        m["KOSPI"] = fetch_yahoo("^KS11", tdate)
    if m["KOSDAQ"]["price"] == 0:
        m["KOSDAQ"] = fetch_yahoo("^KQ11", tdate)
    print("  [Yahoo Finance] 개별 종목 수집...")
    for k, v in STOCK_TICKERS.items():
        m[k] = fetch_yahoo(v, tdate)
        print(f"  {k}: {m[k]['price']:,.0f} ({m[k]['change_pct']:+.2f}%)")
    s = {k: fetch_yahoo(v, tdate) for k, v in SECTORS.items()}
    t = {k: fetch_yahoo(v, tdate) for k, v in THEMES.items()}
    return m, s, t

def analyze(m, s, t, date_label):
    sector_text = ", ".join(f"{k}: {v['change_pct']:+.2f}%" for k, v in s.items())
    theme_text = ", ".join(f"{k}: {v['change_pct']:+.2f}%" for k, v in t.items())
    stock_text = ", ".join(f"{k}: {v['change_pct']:+.2f}%" for k, v in m.items() if k not in ("KOSPI","KOSDAQ"))

    prompt = f"""당신은 15년 경력 한국 주식시장 전문 애널리스트입니다.

[원칙]
- 모든 현상은 왜? → 그게 왜? → 근본원인? 3단계 파고들기
- 수치 인용 시 반드시 web_search로 출처 확인 후 명시
- 확인 안된 수치는 "~추정" 표현 사용
- 각 섹션 5줄 이상, 초보자 괄호 설명 포함

먼저 web_search로 검색하세요:
1. "{date_label} 코스피 증시"
2. "반도체 주가 {date_label}"
3. "나스닥 미국증시 {date_label}"

{date_label} 데이터:
KOSPI {m['KOSPI']['price']:,.2f} ({m['KOSPI']['change_pct']:+.2f}%)
KOSDAQ {m['KOSDAQ']['price']:,.2f} ({m['KOSDAQ']['change_pct']:+.2f}%)
섹터: {sector_text}
테마: {theme_text}
종목: {stock_text}

### 1. 오늘 시장 핵심 요약 (검색 뉴스 근거)
### 2. 섹터별 심층 분석 (글로벌 트리거 → 한국 영향 경로 → 시장심리 → 구조적 원인)
### 3. 테마별 자금 흐름
### 4. 핵심 리스크 분석
### 5. 투자 전략 (단기/중기)
### 6. 추천 종목 3개 (근거+출처+진입가/목표가/손절가)
### 7. 주의 종목
### 8. 초보자 핵심 교훈
### 9. 내일 시나리오 (낙관X%/중립X%/비관X%)"""

    headers = {"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    body = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 4096,
        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
        "messages": [{"role": "user", "content": prompt}],
    }
    print("Claude API 분석 중...")
    r = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=body, timeout=120)
    resp = r.json()
    if "content" not in resp:
        print(f"API 오류: {resp}")
        return "분석 중 오류가 발생했습니다."
    if any(b.get("type") == "tool_use" for b in resp["content"]):
        tool_results = [
            {"type": "tool_result", "tool_use_id": b["id"], "content": b.get("input", {}).get("query", "")}
            for b in resp["content"] if b.get("type") == "tool_use"
        ]
        body2 = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 4096,
            "tools": [{"type": "web_search_20250305", "name": "web_search"}],
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": resp["content"]},
                {"role": "user", "content": tool_results},
            ],
        }
        r = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=body2, timeout=120)
        resp = r.json()
    if "content" not in resp:
        return "분석 중 오류가 발생했습니다."
    return "".join(b.get("text", "") for b in resp["content"] if b.get("type") == "text")

def sparkline(history, w=120, h=40):
    if len(history) < 2: return ""
    prices = [h[1] for h in history]
    mn, mx = min(prices), max(prices)
    if mx == mn: return ""
    color = "#ff4444" if prices[-1] >= prices[0] else "#1976d2"
    pts = " ".join(f"{i/(len(prices)-1)*w:.1f},{h-(p-mn)/(mx-mn)*h:.1f}" for i, p in enumerate(prices))
    return f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" style="overflow:visible"><polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round"/></svg>'

def build_html(m, s, t, analysis, date_label, tdate, updated, all_dates):
    def cc(v): return "up" if isinstance(v,(int,float)) and v>=0 else "down"
    def ca(v): return "▲" if isinstance(v,(int,float)) and v>=0 else "▼"
    kospi, kosdaq = m.get("KOSPI",{}), m.get("KOSDAQ",{})
    kp, kq = kospi.get("change_pct",0), kosdaq.get("change_pct",0)
    date_btns = ""
    for d in sorted(all_dates, reverse=True)[:30]:
        lbl = f"{d[4:6]}.{d[6:8]}"
        act = "active" if d == tdate else ""
        href = "index.html" if d == sorted(all_dates, reverse=True)[0] else f"{d}.html"
        date_btns += f'<a href="{href}" class="dbtn {act}">{lbl}</a>'
    stocks = ""
    for name, d in m.items():
        if name in ("KOSPI","KOSDAQ"): continue
        cp = d.get("change_pct",0)
        sp = sparkline(d.get("history",[]), 80, 28)
        stocks += f'<div class="scard {cc(cp)}"><div class="sname">{name}</div><div class="sprice">₩{d.get("price",0):,.0f}</div><div class="schg {cc(cp)}">{ca(cp)} {abs(cp):.2f}%</div><div>{sp}</div></div>'
    sec_rows = ""
    for name, d in sorted(s.items(), key=lambda x: x[1].get("change_pct",0), reverse=True):
        cp = d.get("change_pct",0)
        bw = min(abs(cp)*8, 100)
        sec_rows += f'<div class="srow"><div class="slabel">{name}</div><div class="sbar-wrap"><div class="sbar {cc(cp)}" style="width:{bw}%"></div></div><div class="spct {cc(cp)}">{ca(cp)} {abs(cp):.2f}%</div></div>'
    themes_html = ""
    for name, d in t.items():
        cp = d.get("change_pct",0)
        sp = sparkline(d.get("history",[]), 80, 28)
        themes_html += f'<div class="scard {cc(cp)}"><div class="sname">{name}</div><div class="sprice">₩{d.get("price",0):,.0f}</div><div class="schg {cc(cp)}">{ca(cp)} {abs(cp):.2f}%</div><div>{sp}</div></div>'
    html_a = re.sub(r"### (.+)", r"<h3>\1</h3>", analysis)
    html_a = re.sub(r"## (.+)", r"<h2>\1</h2>", html_a)
    html_a = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html_a)
    html_a = re.sub(r"^- (.+)$", r"<li>\1</li>", html_a, flags=re.MULTILINE)
    html_a = f"<p>{html_a.replace(chr(10)+chr(10), '</p><p>')}</p>"
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>KRMarketAI - {date_label}</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700;900&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0a0e1a;--sf:#111827;--bd:#1e2d45;--ac:#00d4ff;--up:#ff4444;--dn:#1976d2;--tx:#e2e8f0;--dm:#64748b;}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:var(--bg);color:var(--tx);font-family:'Noto Sans KR',sans-serif;}}
header{{border-bottom:1px solid var(--bd);padding:18px 40px;display:flex;justify-content:space-between;align-items:center;background:rgba(17,24,39,.95);position:sticky;top:0;z-index:100;}}
.logo{{font-size:20px;font-weight:900;}}.logo span{{color:var(--ac);}}
.ts{{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--dm);}}
.wrap{{max-width:1200px;margin:0 auto;padding:28px 24px;}}
.dnav{{background:var(--sf);border:1px solid var(--bd);border-radius:10px;padding:14px 18px;margin-bottom:20px;}}
.dnav-title{{font-size:11px;font-weight:700;letter-spacing:2px;color:var(--dm);margin-bottom:8px;}}
.dbtns{{display:flex;flex-wrap:wrap;gap:6px;}}
.dbtn{{padding:4px 12px;border-radius:5px;border:1px solid var(--bd);background:transparent;color:var(--tx);font-size:12px;font-family:'JetBrains Mono',monospace;text-decoration:none;transition:.15s;}}
.dbtn:hover,.dbtn.active{{background:var(--ac);color:#000;border-color:var(--ac);font-weight:700;}}
.ddate{{text-align:center;color:var(--ac);font-size:13px;font-weight:700;padding:10px;background:var(--sf);border-radius:8px;border:1px solid var(--bd);margin-bottom:24px;}}
.idx{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:6px;}}
.icard{{background:var(--sf);border:1px solid var(--bd);border-radius:14px;padding:22px;display:flex;justify-content:space-between;align-items:center;}}
.ilabel{{font-size:11px;color:var(--dm);letter-spacing:1px;text-transform:uppercase;margin-bottom:5px;}}
.ival{{font-family:'JetBrains Mono',monospace;font-size:30px;font-weight:700;margin-bottom:3px;}}
.ichg{{font-family:'JetBrains Mono',monospace;font-size:15px;font-weight:700;}}
.up{{color:var(--up);}}.down{{color:var(--dn);}}
.sec{{font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--dm);margin:24px 0 12px;padding-bottom:7px;border-bottom:1px solid var(--bd);}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(148px,1fr));gap:10px;}}
.scard{{background:var(--sf);border:1px solid var(--bd);border-radius:10px;padding:12px;}}
.scard.up{{border-left:3px solid var(--up);}}.scard.down{{border-left:3px solid var(--dn);}}
.sname{{font-size:11px;color:var(--dm);margin-bottom:3px;}}
.sprice{{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;margin-bottom:2px;}}
.schg{{font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700;margin-bottom:5px;}}
.srow{{display:flex;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid var(--bd);}}
.slabel{{width:55px;font-size:12px;font-weight:700;flex-shrink:0;}}
.sbar-wrap{{flex:1;background:rgba(255,255,255,.05);border-radius:3px;height:7px;overflow:hidden;}}
.sbar{{height:100%;border-radius:3px;}}.sbar.up{{background:var(--up);}}.sbar.down{{background:var(--dn);}}
.spct{{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;width:68px;text-align:right;flex-shrink:0;}}
.report{{background:var(--sf);border:1px solid var(--bd);border-radius:14px;padding:36px;line-height:1.9;margin-top:6px;}}
.report h3{{font-size:15px;font-weight:700;color:var(--ac);margin:22px 0 9px;padding:9px 13px;background:rgba(0,212,255,.05);border-left:3px solid var(--ac);border-radius:0 5px 5px 0;}}
.report li{{margin-left:18px;margin-bottom:5px;color:#cbd5e1;}}
.report strong{{color:#fff;}}.report p{{margin-bottom:11px;color:#cbd5e1;}}
.disc{{margin-top:28px;padding:14px;border-radius:7px;background:rgba(255,68,68,.06);border:1px solid rgba(255,68,68,.2);font-size:11px;color:var(--dm);}}
footer{{text-align:center;padding:24px;font-size:11px;color:var(--dm);border-top:1px solid var(--bd);margin-top:50px;}}
@media(max-width:600px){{.idx{{grid-template-columns:1fr;}}header{{padding:12px 16px;}}.wrap{{padding:16px 12px;}}.report{{padding:18px;}}}}
</style>
</head>
<body>
<header>
<div class="logo">KR<span>Market</span>AI</div>
<div class="ts">updated: {updated}</div>
</header>
<div class="wrap">
<div class="dnav">
<div class="dnav-title">📅 날짜 선택 (최근 30일)</div>
<div class="dbtns">{date_btns}</div>
</div>
<div class="ddate">📅 {date_label} 기준 데이터</div>
<div class="idx">
<div class="icard"><div><div class="ilabel">KOSPI</div><div class="ival {cc(kp)}">{kospi.get("price",0):,.2f}</div><div class="ichg {cc(kp)}">{ca(kp)} {abs(kp):.2f}%</div></div><div>{sparkline(kospi.get("history",[]),180,55)}</div></div>
<div class="icard"><div><div class="ilabel">KOSDAQ</div><div class="ival {cc(kq)}">{kosdaq.get("price",0):,.2f}</div><div class="ichg {cc(kq)}">{ca(kq)} {abs(kq):.2f}%</div></div><div>{sparkline(kosdaq.get("history",[]),180,55)}</div></div>
</div>
<div class="sec">📊 섹터별 등락률</div><div>{sec_rows}</div>
<div class="sec">🎯 테마별 대장주</div><div class="grid">{themes_html}</div>
<div class="sec">📈 주요 종목</div><div class="grid">{stocks}</div>
<div class="sec">🤖 AI 심층 분석 리포트</div>
<div class="report">{html_a}<div class="disc">⚠️ 면책고지: Claude AI 실시간 뉴스 검색 기반 참고 정보입니다. 투자 결정의 최종 책임은 본인에게 있습니다.</div></div>
</div>
<footer>KRMarketAI · Claude AI + 실시간 뉴스 검색 · Data: Alpha Vantage + Yahoo Finance</footer>
</body>
</html>"""

def main():
    tdate, date_label = get_trading_date()
    m, s, t = collect(tdate)
    analysis = analyze(m, s, t, date_label)
    updated = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y%m%d %H:%M KST")
    all_dates = sorted(set(
        [f.replace(".html","") for f in os.listdir(".") if re.match(r"^\d{8}\.html$", f)]
        + [tdate]
    ), reverse=True)
    html = build_html(m, s, t, analysis, date_label, tdate, updated, all_dates)
    with open(f"{tdate}.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ {tdate}.html 저장")
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ index.html 업데이트")

if __name__ == "__main__":
    main()
