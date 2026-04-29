# 📊 토스증권 관심종목 분석 도구

토스증권에 로그인하여 관심종목을 자동으로 수집하고, 기술적 분석 · 뉴스 감성 분석 · 펀더멘털 분석을 통해 단기/중기/장기 투자 의견을 제공하는 로컬 실행 분석 도구입니다.

---

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# Python 3.11+ 필요
pip install -r requirements.txt

# Playwright 브라우저 설치
playwright install chromium
```

### 2. 사용자 정보 입력

`UserInfo.md` 파일을 열어 본인 정보를 입력합니다:

```markdown
이름: 홍길동
생년월일: 1990-01-01
전화번호: 010-1234-5678
```

### 3. 환경변수 설정 (선택)

`.env.example`을 `.env`로 복사하고 수정합니다:

```bash
copy .env.example .env
```

```env
# AI 분석 활성화 (선택 - 없으면 규칙 기반 분석)
OPENAI_API_KEY=sk-...

# 브라우저 표시 여부 (false = 화면 표시, true = 백그라운드)
HEADLESS=false
```

### 4. 실행

```bash
python main.py
```

---

## 📋 실행 흐름

```
1. 브라우저 자동 실행
   → 토스증권 접속
   → 전화번호 자동 입력
   → 사용자가 SMS 인증번호를 브라우저에서 직접 입력
   → Enter 키 입력 시 분석 시작

2. 관심종목 자동 수집
   → 토스증권 관심목록 스크래핑
   → 수집 실패 시 수동 입력 모드로 전환

3. 종목 분석
   → yfinance로 OHLCV / 펀더멘털 수집
   → 네이버 금융에서 뉴스 수집
   → RSI, MACD, 볼린저밴드, 스토캐스틱, 이동평균 계산
   → 뉴스 감성 분석 (호재/악재 분류)
   → 단기/중기/장기 투자 의견 생성

4. 결과 출력
   → 터미널: Rich 컬러 리포트
   → 브라우저: Plotly 인터랙티브 HTML 대시보드
```

---

## 🛠️ 실행 옵션

| 옵션 | 설명 |
|------|------|
| `python main.py` | 기본 실행 (브라우저 로그인) |
| `python main.py --no-browser` | 브라우저 없이 종목 수동 입력 |
| `python main.py --clear-session` | 저장된 로그인 세션 초기화 |

---

## 📊 제공 분석 항목

### 기술적 분석
- **RSI (14)**: 과매수/과매도 판단
- **MACD (12/26/9)**: 모멘텀 방향 및 골든/데드크로스
- **볼린저 밴드 (20/2σ)**: 변동성 및 가격 위치
- **이동평균**: MA5 / MA20 / MA60 / MA120
- **스토캐스틱 (14/3)**: 단기 과매수/과매도
- **거래량 분석**: 20일 평균 대비 거래량 비율

### 뉴스 분석
- 네이버 금융 종목 뉴스 수집 (한국주식)
- Yahoo Finance RSS (미국주식)
- 한국어 금융 키워드 기반 호재/악재 분류
- OpenAI GPT 기반 뉴스 요약 (API 키 설정 시)

### 투자 의견

| 기간 | 기반 지표 |
|------|-----------|
| 단기 (1~4주) | MACD, RSI, 거래량, 단기 뉴스 |
| 중기 (1~6개월) | 이동평균 추세, 실적 성장률, 섹터 뉴스 |
| 장기 (1~3년) | PER, PBR, ROE, 부채비율 |

### 대시보드 (HTML)
- 캔들차트 + 이동평균 + 볼린저밴드
- RSI / MACD / 거래량 서브차트
- 종목별 등락률 비교
- 섹터별 분포 파이차트
- 단기/중기/장기 투자 점수 비교

---

## 📁 프로젝트 구조

```
toss-invest-analyzer/
├── main.py                          # 메인 실행 파일
├── config.py                        # 설정 로더
├── requirements.txt                 # 패키지 목록
├── .env.example                     # 환경변수 템플릿
├── UserInfo.md                      # 사용자 정보 (직접 수정)
├── src/
│   ├── auth/
│   │   └── toss_login.py            # 토스증권 로그인 (Playwright)
│   ├── scraper/
│   │   ├── watchlist_scraper.py     # 관심종목 스크래핑
│   │   └── news_scraper.py          # 뉴스 수집 (네이버금융/Yahoo)
│   ├── data/
│   │   └── stock_data.py            # yfinance OHLCV/펀더멘털
│   ├── analyzer/
│   │   ├── technical_analyzer.py    # RSI/MACD/BB/스토캐스틱
│   │   ├── news_analyzer.py         # 뉴스 감성 분석
│   │   └── investment_advisor.py    # 단기/중기/장기 투자 의견
│   ├── dashboard/
│   │   └── visualizer.py            # Plotly HTML 대시보드
│   └── reporter/
│       └── terminal_reporter.py     # Rich 터미널 출력
├── cache/                           # 세션/데이터 캐시 (자동 생성)
└── output/                          # 분석 결과 HTML (자동 생성)
```

---

## ⚠️ 주의사항

- **토스증권 로그인**: SMS 인증번호는 브라우저에서 직접 입력해야 합니다.
- **세션 유지**: 로그인 후 세션 쿠키가 `cache/toss_session.json`에 저장되어 재시작 시 자동 로그인됩니다.
- **데이터 출처**: 주가 데이터는 Yahoo Finance (yfinance), 뉴스는 네이버 금융에서 수집합니다.
- **투자 면책**: 이 도구는 참고용이며 투자 결정의 최종 책임은 투자자 본인에게 있습니다.

---

## 📦 주요 의존성

| 패키지 | 용도 |
|--------|------|
| `playwright` | 브라우저 자동화 (토스증권 로그인) |
| `yfinance` | 주가/펀더멘털 데이터 |
| `pandas` / `numpy` | 데이터 처리 |
| `plotly` | 인터랙티브 차트 |
| `rich` | 터미널 UI |
| `beautifulsoup4` | 웹 스크래핑 |
| `openai` | AI 분석 (선택) |