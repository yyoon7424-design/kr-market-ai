# 📈 KRMarketAI — 한국 증시 AI 분석 자동화

매일 오전 6시(KST), Claude AI가 한국 증시를 자동 분석해 웹페이지로 제공합니다.

---

## ✅ 설치 방법 (10분이면 완료!)

### 1단계 — GitHub 저장소 만들기

1. [github.com](https://github.com) 로그인
2. 우측 상단 `+` → **New repository** 클릭
3. Repository name: `kr-market-ai`
4. **Public** 선택 (GitHub Pages 무료 사용)
5. **Create repository** 클릭

---

### 2단계 — 파일 업로드

이 폴더의 파일들을 그대로 GitHub에 업로드하세요:

```
kr-market-ai/
├── .github/
│   └── workflows/
│       └── daily-analysis.yml   ← 자동 실행 설정
├── scripts/
│   └── analyze.py               ← 분석 스크립트
├── docs/
│   └── index.html               ← 웹페이지 (자동 생성됨)
└── README.md
```

업로드 방법:
- GitHub 저장소 페이지에서 **Add file** → **Upload files**
- 또는 git 명령어 사용

---

### 3단계 — Claude API 키 등록

1. [console.anthropic.com](https://console.anthropic.com) 접속 → API Keys → **Create Key**
2. GitHub 저장소 → **Settings** → **Secrets and variables** → **Actions**
3. **New repository secret** 클릭
4. Name: `ANTHROPIC_API_KEY`
5. Value: 발급받은 API 키 붙여넣기
6. **Add secret** 클릭

---

### 4단계 — GitHub Pages 활성화

1. 저장소 **Settings** → **Pages**
2. Source: **Deploy from a branch**
3. Branch: `main` / Folder: `/docs`
4. **Save** 클릭

약 1분 후 `https://[내 GitHub 아이디].github.io/kr-market-ai/` 로 접속 가능!

---

### 5단계 — 첫 번째 실행 테스트

1. 저장소 → **Actions** 탭
2. **한국 증시 AI 분석** 워크플로우 선택
3. **Run workflow** 버튼 클릭
4. 약 1~2분 후 완료 → 웹페이지 확인!

---

## 🕐 자동 실행 스케줄

| 시간 | 동작 |
|------|------|
| 매일 오전 6:00 KST | 자동 분석 실행 |
| 분석 소요 시간 | 약 1~2분 |
| 결과 확인 | GitHub Pages 웹페이지 |

---

## 💰 비용 안내

| 항목 | 비용 |
|------|------|
| GitHub Actions | 무료 (월 2,000분) |
| GitHub Pages | 무료 |
| Yahoo Finance API | 무료 |
| Claude API | 약 분석 1회당 $0.01~0.03 (월 300~900원) |

---

## 📊 분석 내용

- KOSPI / KOSDAQ 지수 현황
- 주요 10개 종목 실시간 시세
- AI 시장 요약 및 투자 전략
- 추천 종목 3개 (진입가/목표가/손절가 포함)
- 주의 종목 및 내일 관전 포인트

---

## ⚠️ 면책고지

이 분석은 AI가 생성한 참고 정보입니다.
투자 결정의 최종 책임은 투자자 본인에게 있으며,
본 서비스는 투자 권유가 아닙니다.
