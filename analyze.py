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
    elif kst.hour < 16:
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
    return market, sectors, themes, date_label, trading_date

def call_claude_with_search(market, sectors, themes, date_label):
    sector_text = ", ".join([f"{k}: {v['change_pct']:+.2f}%" for k, v in sectors.items()])
    theme_text = ", ".join([f"{k}: {v['change_pct']:+.2f}% (₩{v['price']:,.0f})" for k, v in themes.items()])

    prompt = f"""당신은 15년 경력의 한국 주식시장 전문 애널리스트입니다.

[분석 원칙 - 반드시 준수]
1. 모든 현상은 "왜?" -> "그게 왜?" -> "근본 원인은?" 3단계 이상 파고드세요.
2. 수치나 통계를 인용할 때는 반드시 web_search 툴로 검색해서 실제 출처를 확인하고 명시하세요.
3. "실적 부진", "수요 둔화" 등의 표현은 반드시 구체적 기업명, 수치, 출처와 함께 작성하세요.
4. 확인되지 않은 수치는 절대 사실처럼 제시하지 말고 "~로 추정된다", "~우려가 있다"고 표현하세요.
5. 초보자용 괄호 설명 포함, 각 섹션 최소 5줄 이상.

먼저 web_search 툴로 다음을 검색하세요:
- "{date_label} 한국 증시 코스피"
- "반도체 주가 뉴스 {date_label}"
- "삼성전자 SK하이닉스 {date_label}"
- "미국 반도체 나스닥 {date_label}"
- "브로드컴 엔비디아 TSMC 최근 뉴스"

{date_label} 한국 증시 데이터:
KOSPI {market['KOSPI']['price']:,.2f} ({market['KOSPI']['change_pct']:+.2f}%), KOSDAQ {market['KOSDAQ']['price']:,.2f} ({market['KOSDAQ']['change_pct']:+.2f}%)
섹터: {sector_text}
테마: {theme_text}
종목: {', '.join([f"{k} {v['change_pct']:+.2f}%" for k, v in market.items() if k not in ('KOSPI','KOSDAQ')])}

### 1. 오늘 시장 핵심 요약
### 2. 섹터별 심층 분석 (글로벌 트리거 + 출처 필수)
각 섹터별: 글로벌 트리거 → 한국 시장 영향 경로 → 시장 심리 메커니즘 → 근본 구조적 원인
### 3. 테마별 자금 흐름 분석
### 4. 리스크 요인 근본 분석
### 5. 투자 전략 (단기/중기)
### 6. 추천 종목 3개 (근거 + 출처)
### 7. 주의/회피 종목
### 8. 초보자를 위한 오늘의 교훈
### 9. 내일 시나리오 (낙관/중립/비관 확률 포함)"""

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 4096,
        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
        "messages": [{"role": "user", "content": prompt}],
    }

    print("Claude API + 웹 검색 실행 중...")
    r = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=body, timeout=120)
    resp = r.json()

    if "content" not in resp:
        print(f"API 오류: {resp}")
        return "분석 데이터를 불러오는 중 오류가 발생했습니다."

    full_text = ""
    for block in resp["content"]:
        if block.get("type") == "text":
            full_text += block.get("text", "")

    if any(block.get("type") == "tool_use" for block in resp["content"]):
        print("웹 검색 결과 처리 중...")
        messages = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": resp["content"]},
        ]
        tool_results = []
        for block in resp["content"]:
            if block.get("type") == "tool_use":
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": block.get("input", {}).get("query", "검색 완료")
                })
        if tool_results:
            messages.append({"role": "user", "content": tool_results})
        body2 = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 4096,
            "tools": [{"type": "web_search_20250305", "name": "web_search"}],
            "messages": messages,
        }
        r2 = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=body2, timeout=120)
        resp2 = r2.json()
        if "content" in resp2:
            full_text = ""
            for block in resp2["content"]:
                if block.get("type") == "text":
                    full_text += block.get("text", "")

    return full_text if full_text else "분석 데이터를 불러오는 중 오류가 발생했습니다."

def make_sparkline(history, width=120, height=40):
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
    return f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" style="overflow:visible"><polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round"/></svg>'

def save_data(market, sectors, themes, analysis, date_label, trading_date):
    """날짜별 JSON 데이터 저장"""
    os.makedirs("docs/data", exist_ok=True)
    data = {
        "date": trading_date,
        "date_label": date_label,
        "market": {k: {"price": v["price"], "change_pct": v["change_pct"]} for k, v in market.items()},
        "sectors": {k: {"price": v["price"], "change_pct": v["change_pct"]} for k, v in sectors.items()},
        "themes": {k: {"price": v["price"], "change_pct": v["change_pct"]} for k, v in themes.items()},
        "analysis": analysis,
        "updated_at": (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y%m%d %H:%M KST")
    }
    # 날짜별 저장
    with open(f"docs/data/{trading_date}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # 날짜 목록 업데이트
    index_path = "docs/data/index.json"
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            idx = json.load(f)
    else:
        idx = {"dates": []}
    if trading_date not in idx["dates"]:
        idx["dates"].append(trading_date)
        idx["dates"].sort(reverse=True)
    idx["latest"] = trading_date
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)
    print(f"✅ 데이터 저장 완료: docs/data/{trading_date}.json")

def build_index_html():
    """날짜 선택 가능한 메인 페이지 생성"""
    html = '''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>KRMarketAI</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;700;900&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
:root{--bg:#0a0e1a;--surface:#111827;--border:#1e2d45;--accent:#00d4ff;--up:#ff4444;--down:#1976d2;--flat:#94a3b8;--text:#e2e8f0;--dim:#64748b;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:'Noto Sans KR',sans-serif;min-height:100vh;}
header{border-bottom:1px solid var(--border);padding:20px 40px;display:flex;justify-content:space-between;align-items:center;background:rgba(17,24,39,0.95);position:sticky;top:0;z-index:100;}
.logo{font-size:20px;font-weight:900;}.logo span{color:var(--accent);}
.ts{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--dim);}
.wrap{max-width:1200px;margin:0 auto;padding:32px 24px;}

/* 날짜 선택 */
.date-nav{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px;margin-bottom:28px;}
.date-nav-title{font-size:12px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--dim);margin-bottom:12px;}
.date-buttons{display:flex;flex-wrap:wrap;gap:8px;}
.date-btn{padding:6px 14px;border-radius:6px;border:1px solid var(--border);background:transparent;color:var(--text);font-size:13px;font-family:'JetBrains Mono',monospace;cursor:pointer;transition:all 0.2s;}
.date-btn:hover{border-color:var(--accent);color:var(--accent);}
.date-btn.active{background:var(--accent);color:#000;border-color:var(--accent);font-weight:700;}

.data-date{text-align:center;color:var(--accent);font-size:14px;font-weight:700;margin-bottom:28px;padding:12px;background:var(--surface);border-radius:8px;border:1px solid var(--border);}
.idx{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:8px;}
.idx-card{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:24px;display:flex;justify-content:space-between;align-items:center;}
.idx-label{font-size:12px;color:var(--dim);letter-spacing:1px;text-transform:uppercase;margin-bottom:6px;}
.idx-val{font-family:'JetBrains Mono',monospace;font-size:32px;font-weight:700;margin-bottom:4px;}
.idx-chg{font-family:'JetBrains Mono',monospace;font-size:16px;font-weight:700;}
.up{color:var(--up);}.down{color:var(--down);}.flat{color:var(--flat);}
.sec{font-size:12px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--dim);margin:28px 0 14px;padding-bottom:8px;border-bottom:1px solid var(--border);}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px;}
.stock-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px;}
.stock-card.up{border-left:3px solid var(--up);}.stock-card.down{border-left:3px solid var(--down);}
.stock-name{font-size:12px;color:var(--dim);margin-bottom:4px;}
.stock-price{font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:700;margin-bottom:2px;}
.stock-change{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;}
.sector-row{display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid var(--border);}
.sector-name{width:60px;font-size:13px;font-weight:700;flex-shrink:0;}
.sector-bar-wrap{flex:1;background:rgba(255,255,255,0.05);border-radius:4px;height:8px;overflow:hidden;}
.sector-bar{height:100%;border-radius:4px;}
.sector-bar.up{background:var(--up);}.sector-bar.down{background:var(--down);}
.sector-pct{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;width:70px;text-align:right;flex-shrink:0;}
.theme-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px;}
.theme-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px;}
.theme-card.up{border-left:3px solid var(--up);}.theme-card.down{border-left:3px solid var(--down);}
.theme-name{font-size:12px;color:var(--dim);margin-bottom:4px;font-weight:700;}
.theme-price{font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:700;margin-bottom:2px;}
.theme-change{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;}
.report{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:40px;line-height:1.9;}
.report h3{font-size:16px;font-weight:700;color:var(--accent);margin:24px 0 10px;padding:10px 14px;background:rgba(0,212,255,0.05);border-left:3px solid var(--accent);border-radius:0 6px 6px 0;}
.report li{margin-left:20px;margin-bottom:6px;color:#cbd5e1;}
.report strong{color:#fff;}
.report p{margin-bottom:12px;color:#cbd5e1;}
.disc{margin-top:32px;padding:16px;border-radius:8px;background:rgba(255,68,68,0.06);border:1px solid rgba(255,68,68,0.2);font-size:12px;color:var(--dim);}
.loading{text-align:center;padding:60px;color:var(--dim);font-size:16px;}
footer{text-align:center;padding:28px;font-size:12px;color:var(--dim);border-top:1px solid var(--border);margin-top:60px;}
@media(max-width:600px){.idx{grid-template-columns:1fr;}header{padding:14px 16px;}.wrap{padding:20px 14px;}.report{padding:22px;}}
</style>
</head>
<body>
<header>
<div class="logo">KR<span>Market</span>AI</div>
<div class="ts" id="ts">로딩 중...</div>
</header>
<div class="wrap">
  <div class="date-nav">
    <div class="date-nav-title">📅 날짜 선택</div>
    <div class="date-buttons" id="date-buttons">로딩 중...</div>
  </div>
  <div id="content"><div class="loading">⏳ 데이터 로딩 중...</div></div>
</div>
<footer>KRMarketAI · Powered by Claude AI + 실시간 뉴스 검색 · Data: Yahoo Finance</footer>
<script>
let allDates = [];
let currentDate = null;

function cc(v) { return v >= 0 ? 'up' : 'down'; }
function ca(v) { return v >= 0 ? '▲' : '▼'; }

async function loadIndex() {
  const r = await fetch('data/index.json?t=' + Date.now());
  const idx = await r.json();
  allDates = idx.dates || [];
  currentDate = idx.latest;
  renderDateButtons();
  if (currentDate) loadDate(currentDate);
}

function renderDateButtons() {
  const wrap = document.getElementById('date-buttons');
  if (!allDates.length) { wrap.innerHTML = '저장된 데이터가 없습니다.'; return; }
  wrap.innerHTML = allDates.map(d => {
    const label = d.slice(0,4) + '.' + d.slice(4,6) + '.' + d.slice(6,8);
    return `<button class="date-btn ${d === currentDate ? 'active' : ''}" onclick="loadDate('${d}')">${label}</button>`;
  }).join('');
}

async function loadDate(date) {
  currentDate = date;
  renderDateButtons();
  document.getElementById('content').innerHTML = '<div class="loading">⏳ 데이터 로딩 중...</div>';
  const r = await fetch(`data/${date}.json?t=` + Date.now());
  const data = await r.json();
  document.getElementById('ts').textContent = 'updated: ' + data.updated_at;
  renderContent(data);
}

function renderContent(data) {
  const m = data.market;
  const s = data.sectors;
  const t = data.themes;
  const kospi = m['KOSPI'] || {};
  const kosdaq = m['KOSDAQ'] || {};
  const kp = kospi.change_pct || 0;
  const kq = kosdaq.change_pct || 0;

  let stockCards = '';
  for (const [name, d] of Object.entries(m)) {
    if (name === 'KOSPI' || name === 'KOSDAQ') continue;
    const cp = d.change_pct || 0;
    stockCards += `<div class="stock-card ${cc(cp)}"><div class="stock-name">${name}</div><div class="stock-price">₩${d.price.toLocaleString()}</div><div class="stock-change ${cc(cp)}">${ca(cp)} ${Math.abs(cp).toFixed(2)}%</div></div>`;
  }

  const sortedSectors = Object.entries(s).sort((a,b) => b[1].change_pct - a[1].change_pct);
  let sectorCards = '';
  for (const [name, d] of sortedSectors) {
    const cp = d.change_pct || 0;
    const bw = Math.min(Math.abs(cp) * 8, 100);
    sectorCards += `<div class="sector-row"><div class="sector-name">${name}</div><div class="sector-bar-wrap"><div class="sector-bar ${cc(cp)}" style="width:${bw}%"></div></div><div class="sector-pct ${cc(cp)}">${ca(cp)} ${Math.abs(cp).toFixed(2)}%</div></div>`;
  }

  let themeCards = '';
  for (const [name, d] of Object.entries(t)) {
    const cp = d.change_pct || 0;
    themeCards += `<div class="theme-card ${cc(cp)}"><div class="theme-name">${name}</div><div class="theme-price">₩${d.price.toLocaleString()}</div><div class="theme-change ${cc(cp)}">${ca(cp)} ${Math.abs(cp).toFixed(2)}%</div></div>`;
  }

  let analysis = data.analysis || '';
  analysis = analysis.replace(/### (.+)/g, '<h3>$1</h3>');
  analysis = analysis.replace(/## (.+)/g, '<h2>$1</h2>');
  analysis = analysis.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  analysis = analysis.replace(/^- (.+)$/gm, '<li>$1</li>');
  analysis = analysis.replace(/\\n\\n/g, '</p><p>');
  analysis = analysis.replace(/\n\n/g, '</p><p>');
  analysis = '<p>' + analysis + '</p>';

  document.getElementById('content').innerHTML = `
    <div class="data-date">📅 ${data.date_label} 기준 데이터</div>
    <div class="idx">
      <div class="idx-card">
        <div>
          <div class="idx-label">KOSPI</div>
          <div class="idx-val ${cc(kp)}">${kospi.price?.toLocaleString('ko-KR', {minimumFractionDigits:2, maximumFractionDigits:2})}</div>
          <div class="idx-chg ${cc(kp)}">${ca(kp)} ${Math.abs(kp).toFixed(2)}%</div>
        </div>
      </div>
      <div class="idx-card">
        <div>
          <div class="idx-label">KOSDAQ</div>
          <div class="idx-val ${cc(kq)}">${kosdaq.price?.toLocaleString('ko-KR', {minimumFractionDigits:2, maximumFractionDigits:2})}</div>
          <div class="idx-chg ${cc(kq)}">${ca(kq)} ${Math.abs(kq).toFixed(2)}%</div>
        </div>
      </div>
    </div>
    <div class="sec">📊 섹터별 등락률</div>
    <div>${sectorCards}</div>
    <div class="sec">🎯 테마별 대장주</div>
    <div class="theme-grid">${themeCards}</div>
    <div class="sec">📈 주요 종목</div>
    <div class="grid">${stockCards}</div>
    <div class="sec">🤖 AI 심층 분석 리포트</div>
    <div class="report">
      ${analysis}
      <div class="disc">⚠️ 면책고지: 이 분석은 Claude AI가 실시간 뉴스 검색을 통해 생성한 참고 정보입니다. 투자 결정의 최종 책임은 투자자 본인에게 있습니다.</div>
    </div>
  `;
}

loadIndex();
</script>
</body>
</html>'''
    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ index.html 생성 완료")

def main():
    market, sectors, themes, date_label, trading_date = collect_market_data()
    analysis = call_claude_with_search(market, sectors, themes, date_label)
    save_data(market, sectors, themes, analysis, date_label, trading_date)
    build_index_html()
    print("Done!")

if __name__ == "__main__":
    main()
