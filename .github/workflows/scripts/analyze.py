import os
import json
import datetime
import requests
from pathlib import Path
 
# ── 설정 ──────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OUTPUT_DIR = Path("docs")
OUTPUT_DIR.mkdir(exist_ok=True)
 
# 분석할 주요 한국 ETF / 지수 티커 (Yahoo Finance 기준)
TICKERS = {
    "KOSPI":   "^KS11",
    "KOSDAQ":  "^KQ11",
    "삼성전자": "005930.KS",
    "SK하이닉스": "000660.KS",
    "NAVER":   "035420.KS",
    "카카오":   "035720.KS",
    "현대차":   "005380.KS",
    "LG에너지솔루션": "373220.KS",
    "셀트리온":  "068270.KS",
    "POSCO홀딩스": "005490.KS",
    "기아":    "000270.KS",
    "KB금융":  "105560.KS",
}
 
def fetch_quote(ticker: str) -> dict:
    """Yahoo Finance v8 API로 현재가 데이터 조회"""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        meta = data["chart"]["result"][0]["meta"]
        closes = data["chart"]["result"][0]["indicators"]["quote"][0].get("close", [])
        closes = [c for c in closes if c is not None]
        prev_close = closes[-2] if len(closes) >= 2 else meta.get("previousClose", 0)
        current = meta.get("regularMarketPrice") or (closes[-1] if closes else 0)
        change_pct = ((current - prev_close) / prev_close * 100) if prev_close else 0
        return {
            "ticker": ticker,
            "price": round(current, 2),
            "prev_close": round(prev_close, 2),
            "change_pct": round(change_pct, 2),
            "volume": meta.get("regularMarketVolume", 0),
            "52w_high": meta.get("fiftyTwoWeekHigh", 0),
            "52w_low": meta.get("fiftyTwoWeekLow", 0),
            "closes_5d": [round(c, 2) for c in closes[-5:]],
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}
 
def collect_market_data() -> dict:
    print("📡 시장 데이터 수집 중...")
    results = {}
    for name, ticker in TICKERS.items():
        results[name] = fetch_quote(ticker)
        print(f"  ✓ {name} ({ticker})")
    return results
 
def call_claude(market_data: dict) -> str:
    """Claude API로 시장 분석 및 종목 추천 요청"""
    kst_now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    date_str = kst_now.strftime("%Y년 %m월 %d일")
 
    prompt = f"""당신은 한국 주식시장 전문 애널리스트입니다.
아래 {date_str} 기준 한국 증시 데이터를 분석해 투자 가이드를 작성해주세요.
 
## 시장 데이터 (JSON)
{json.dumps(market_data, ensure_ascii=False, indent=2)}
 
## 요청 사항
다음 구조로 HTML 없이 순수 텍스트+마크다운으로 작성하세요:
 
### 1. 오늘의 시장 요약 (3~4줄)
- KOSPI/KOSDAQ 흐름
- 전반적인 시장 분위기
 
### 2. 주요 지표 해석
- 눈에 띄는 강세/약세 종목
- 52주 고저 대비 현재 위치
- 거래량 특이사항
 
### 3. 오늘의 투자 전략
- 시장 전반 방향성 (강세/약세/중립)
- 섹터별 접근 전략
 
### 4. 추천 종목 (3개)
각 종목별:
- 종목명
- 추천 이유 (데이터 근거)
- 진입 가격대 / 목표가 / 손절가
- 리스크 요인
 
### 5. 주의 종목 (1~2개)
- 피해야 할 종목과 이유
 
### 6. 내일을 위한 관전 포인트
- 주시해야 할 지표나 이벤트
 
⚠️ 면책고지: 이 분석은 AI가 생성한 참고 정보이며, 투자 결정의 최종 책임은 투자자 본인에게 있습니다.
"""
 
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
    print("🤖 Claude API 분석 요청 중...")
    r = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=body, timeout=60)
    result = r.json()
    return result["content"][0]["text"]
 
def build_html(market_data: dict, analysis: str) -> str:
    """분석 결과를 예쁜 HTML로 변환"""
    kst_now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    date_str = kst_now.strftime("%Y년 %m월 %d일 %H:%M KST")
 
    kospi = market_data.get("KOSPI", {})
    kosdaq = market_data.get("KOSDAQ", {})
 
    def change_class(v):
        if isinstance(v, (int, float)):
            return "up" if v > 0 else ("down" if v < 0 else "flat")
        return "flat"
 
    def change_arrow(v):
        if isinstance(v, (int, float)):
            return "▲" if v > 0 else ("▼" if v < 0 else "–")
        return "–"
 
    # 종목 카드 HTML 생성
    stock_cards = ""
    for name, d in market_data.items():
        if name in ("KOSPI", "KOSDAQ") or "error" in d:
            continue
        cp = d.get("change_pct", 0)
        cc = change_class(cp)
        ca = change_arrow(cp)
        stock_cards += f"""
        <div class="stock-card {cc}">
          <div class="stock-name">{name}</div>
          <div class="stock-price">₩{d.get('price', 0):,.0f}</div>
          <div class="stock-change {cc}">{ca} {abs(cp):.2f}%</div>
        </div>"""
 
    # 마크다운 → HTML 간단 변환
    import re
    html_analysis = analysis
    html_analysis = re.sub(r"### (.+)", r"<h3>\1</h3>", html_analysis)
    html_analysis = re.sub(r"## (.+)", r"<h2>\1</h2>", html_analysis)
    html_analysis = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html_analysis)
    html_analysis = re.sub(r"^- (.+)$", r"<li>\1</li>", html_analysis, flags=re.MULTILINE)
    html_analysis = html_analysis.replace("\n\n", "</p><p>")
    html_analysis = f"<p>{html_analysis}</p>"
 
    kospi_chg = kospi.get('change_pct', 0)
    kosdaq_chg = kosdaq.get('change_pct', 0)
 
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>한국 증시 AI 분석 리포트</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #0a0e1a;
    --surface: #111827;
    --surface2: #1c2537;
    --border: #1e2d45;
    --accent: #00d4ff;
    --accent2: #7c3aed;
    --up: #00e676;
    --down: #ff4444;
    --flat: #94a3b8;
    --text: #e2e8f0;
    --text-dim: #64748b;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Noto Sans KR', sans-serif;
    min-height: 100vh;
    background-image:
      radial-gradient(ellipse at 20% 20%, rgba(0,212,255,0.05) 0%, transparent 50%),
      radial-gradient(ellipse at 80% 80%, rgba(124,58,237,0.05) 0%, transparent 50%);
  }}
  header {{
    border-bottom: 1px solid var(--border);
    padding: 24px 40px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: rgba(17,24,39,0.8);
    backdrop-filter: blur(12px);
    position: sticky; top: 0; z-index: 100;
  }}
  .logo {{ font-size: 20px; font-weight: 900; letter-spacing: -0.5px; }}
  .logo span {{ color: var(--accent); }}
  .timestamp {{ font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--text-dim); }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 40px 24px; }}
 
  /* 지수 요약 */
  .index-bar {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 40px;
  }}
  .index-card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 16px; padding: 28px;
    position: relative; overflow: hidden;
  }}
  .index-card::before {{
    content: ''; position: absolute; inset: 0;
    background: linear-gradient(135deg, rgba(0,212,255,0.03), transparent);
  }}
  .index-label {{ font-size: 12px; color: var(--text-dim); font-weight: 500; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 8px; }}
  .index-value {{ font-family: 'JetBrains Mono', monospace; font-size: 36px; font-weight: 700; margin-bottom: 4px; }}
  .index-change {{ font-family: 'JetBrains Mono', monospace; font-size: 18px; font-weight: 700; }}
  .up {{ color: var(--up); }}
  .down {{ color: var(--down); }}
  .flat {{ color: var(--flat); }}
 
  /* 종목 그리드 */
  .section-title {{
    font-size: 13px; font-weight: 700; letter-spacing: 2px;
    text-transform: uppercase; color: var(--text-dim);
    margin-bottom: 16px; padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
  }}
  .stocks-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 12px; margin-bottom: 40px;
  }}
  .stock-card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 12px; padding: 16px;
    transition: transform 0.2s, border-color 0.2s;
  }}
  .stock-card:hover {{ transform: translateY(-2px); border-color: var(--accent); }}
  .stock-card.up {{ border-left: 3px solid var(--up); }}
  .stock-card.down {{ border-left: 3px solid var(--down); }}
  .stock-name {{ font-size: 13px; color: var(--text-dim); margin-bottom: 6px; }}
  .stock-price {{ font-family: 'JetBrains Mono', monospace; font-size: 15px; font-weight: 700; margin-bottom: 4px; }}
  .stock-change {{ font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 700; }}
 
  /* 분석 리포트 */
  .report-card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 16px; padding: 40px;
    line-height: 1.8;
  }}
  .report-card h2 {{
    font-size: 20px; font-weight: 700; color: var(--accent);
    margin: 28px 0 12px; padding-top: 20px;
    border-top: 1px solid var(--border);
  }}
  .report-card h2:first-child {{ border-top: none; padding-top: 0; margin-top: 0; }}
  .report-card h3 {{
    font-size: 16px; font-weight: 700; color: var(--text);
    margin: 20px 0 8px;
  }}
  .report-card li {{
    margin-left: 20px; margin-bottom: 4px; color: #cbd5e1;
  }}
  .report-card strong {{ color: #fff; }}
  .report-card p {{ margin-bottom: 12px; color: #cbd5e1; }}
 
  .disclaimer {{
    margin-top: 32px; padding: 16px; border-radius: 8px;
    background: rgba(255,68,68,0.08); border: 1px solid rgba(255,68,68,0.2);
    font-size: 12px; color: var(--text-dim); line-height: 1.6;
  }}
  footer {{
    text-align: center; padding: 32px;
    font-size: 12px; color: var(--text-dim);
    border-top: 1px solid var(--border);
    margin-top: 60px;
  }}
  @media (max-width: 600px) {{
    .index-bar {{ grid-template-columns: 1fr; }}
    header {{ padding: 16px 20px; }}
    .container {{ padding: 24px 16px; }}
    .report-card {{ padding: 24px; }}
  }}
</style>
</head>
<body>
<header>
  <div class="logo">KR<span>Market</span>AI</div>
  <div class="timestamp">🕐 {date_str}</div>
</header>
<div class="container">
 
  <div class="index-bar">
    <div class="index-card">
      <div class="index-label">KOSPI</div>
      <div class="index-value {change_class(kospi_chg)}">{kospi.get('price', '—'):,.2f}</div>
      <div class="index-change {change_class(kospi_chg)}">{change_arrow(kospi_chg)} {abs(kospi_chg):.2f}%</div>
    </div>
    <div class="index-card">
      <div class="index-label">KOSDAQ</div>
      <div class="index-value {change_class(kosdaq_chg)}">{kosdaq.get('price', '—'):,.2f}</div>
      <div class="index-change {change_class(kosdaq_chg)}">{change_arrow(kosdaq_chg)} {abs(kosdaq_chg):.2f}%</div>
    </div>
  </div>
 
  <div class="section-title">주요 종목 현황</div>
  <div class="stocks-grid">{stock_cards}</div>
 
  <div class="section-title">AI 시장 분석 리포트</div>
  <div class="report-card">
    {html_analysis}
    <div class="disclaimer">
      ⚠️ <strong>면책고지</strong>: 이 분석은 Claude AI가 생성한 참고 정보입니다.
      투자 결정의 최종 책임은 투자자 본인에게 있으며, 본 리포트는 투자 권유가 아닙니다.
      과거 데이터 기반 분석으로 미래 수익을 보장하지 않습니다.
    </div>
  </div>
</div>
<footer>
  KRMarketAI · Powered by Claude AI · 데이터 출처: Yahoo Finance
</footer>
</body>
</html>"""
 
def main():
    market_data = collect_market_data()
    analysis = call_claude(market_data)
 
    # HTML 생성 및 저장
    html = build_html(market_data, analysis)
    out_path = OUTPUT_DIR / "index.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"✅ 리포트 생성 완료: {out_path}")
 
    # 마지막 업데이트 시간 저장
    kst_now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    meta = {"last_updated": kst_now.isoformat(), "status": "success"}
    (OUTPUT_DIR / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
 
if __name__ == "__main__":
    main()
 
