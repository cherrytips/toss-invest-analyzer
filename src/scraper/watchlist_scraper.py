"""
토스증권 관심종목 스크래퍼
- 로그인 후 관심목록 페이지에서 종목 정보 수집
- 다중 셀렉터 전략으로 UI 변경에 강건하게 대응
- 네트워크 요청 인터셉트를 통한 API 데이터 수집 시도
"""

import json
import re
from playwright.async_api import Page
from rich.console import Console

console = Console()

WATCHLIST_URLS = [
    "https://www.tossinvest.com/watchlist",
    "https://www.tossinvest.com/assets/watchlist",
    "https://www.tossinvest.com/interest-stock",
]

WATCHLIST_NAV_SELECTORS = [
    "a:has-text('관심종목')",
    "a:has-text('관심목록')",
    "button:has-text('관심종목')",
    "[data-testid*='watchlist']",
    "[href*='watchlist']",
    "[href*='interest']",
]

STOCK_ITEM_SELECTORS = [
    "[data-testid*='stock-item']",
    "[class*='StockItem']",
    "[class*='stockItem']",
    "[class*='WatchlistItem']",
    "[class*='watchlistItem']",
    "[class*='InterestItem']",
]


class WatchlistScraper:
    def __init__(self, page: Page, config):
        self.page = page
        self.config = config
        self._api_responses = []

    async def get_watchlist(self) -> list[dict]:
        """관심종목 목록을 반환 (각 항목: code, name, market, current_price, change_rate)"""

        # 방법 1: 네트워크 API 응답 가로채기
        watchlist = await self._try_api_intercept()
        if watchlist:
            console.print(f"[green]✓ API 인터셉트로 {len(watchlist)}개 종목 수집[/green]")
            return watchlist

        # 방법 2: 관심종목 페이지로 직접 이동
        watchlist = await self._navigate_to_watchlist()
        if watchlist:
            console.print(f"[green]✓ 페이지 스크래핑으로 {len(watchlist)}개 종목 수집[/green]")
            return watchlist

        # 방법 3: 수동 입력 폴백
        console.print("[yellow]관심종목을 자동으로 수집하지 못했습니다.[/yellow]")
        return await self._manual_input_fallback()

    async def _try_api_intercept(self) -> list[dict]:
        """API 응답을 가로채어 관심종목 데이터 수집"""
        api_data = []

        async def handle_response(response):
            url = response.url
            if any(kw in url for kw in ["watchlist", "interest", "favorite", "stock/list"]):
                try:
                    if "application/json" in response.headers.get("content-type", ""):
                        data = await response.json()
                        api_data.append(data)
                except Exception:
                    pass

        self.page.on("response", handle_response)

        # 관심종목 접근 유도
        for nav_sel in WATCHLIST_NAV_SELECTORS:
            try:
                await self.page.click(nav_sel, timeout=2000)
                await self.page.wait_for_timeout(2000)
                break
            except Exception:
                pass

        self.page.remove_listener("response", handle_response)

        if api_data:
            return self._parse_api_data(api_data)

        return []

    def _parse_api_data(self, api_data_list: list) -> list[dict]:
        """API 응답에서 종목 정보 파싱"""
        stocks = []
        for data in api_data_list:
            extracted = self._extract_stocks_from_dict(data)
            stocks.extend(extracted)

        # 중복 제거
        seen = set()
        unique = []
        for s in stocks:
            if s.get("code") and s["code"] not in seen:
                seen.add(s["code"])
                unique.append(s)
        return unique

    def _extract_stocks_from_dict(self, data, depth=0) -> list[dict]:
        """재귀적으로 딕셔너리에서 종목 정보 추출"""
        if depth > 5:
            return []
        stocks = []
        if isinstance(data, dict):
            # 종목 코드 패턴: 6자리 숫자 (한국) 또는 영문 티커 (미국)
            code = data.get("code") or data.get("stockCode") or data.get("ticker") or data.get("symbol")
            name = data.get("name") or data.get("stockName") or data.get("companyName") or data.get("korName")
            if code and name:
                market = data.get("market") or data.get("exchange") or self._detect_market(str(code))
                stocks.append({
                    "code": str(code).strip(),
                    "name": str(name).strip(),
                    "market": str(market).upper() if market else "UNKNOWN",
                    "current_price": data.get("price") or data.get("currentPrice") or data.get("closePrice") or 0,
                    "change_rate": data.get("changeRate") or data.get("fluctuationRate") or data.get("priceChange") or 0,
                })
            else:
                for v in data.values():
                    stocks.extend(self._extract_stocks_from_dict(v, depth + 1))
        elif isinstance(data, list):
            for item in data:
                stocks.extend(self._extract_stocks_from_dict(item, depth + 1))
        return stocks

    async def _navigate_to_watchlist(self) -> list[dict]:
        """관심종목 페이지로 이동 후 DOM 스크래핑"""
        # 알려진 URL 시도
        for url in WATCHLIST_URLS:
            try:
                await self.page.goto(url, wait_until="domcontentloaded", timeout=10000)
                await self.page.wait_for_timeout(2000)
                stocks = await self._scrape_stock_list()
                if stocks:
                    return stocks
            except Exception:
                pass

        # 내비게이션 클릭 시도
        for sel in WATCHLIST_NAV_SELECTORS:
            try:
                await self.page.click(sel, timeout=3000)
                await self.page.wait_for_timeout(2000)
                stocks = await self._scrape_stock_list()
                if stocks:
                    return stocks
            except Exception:
                pass

        return []

    async def _scrape_stock_list(self) -> list[dict]:
        """현재 페이지에서 종목 목록 스크래핑"""
        stocks = []

        for selector in STOCK_ITEM_SELECTORS:
            try:
                items = await self.page.query_selector_all(selector)
                if not items:
                    continue

                for item in items:
                    text = await item.inner_text()
                    stock = self._parse_stock_text(text)
                    if stock:
                        stocks.append(stock)

                if stocks:
                    break
            except Exception:
                pass

        # 스크린샷 저장 (디버깅용)
        if not stocks:
            try:
                screenshot_path = self.config.cache_dir / "watchlist_debug.png"
                await self.page.screenshot(path=str(screenshot_path))
                console.print(f"[dim]디버그 스크린샷 저장: {screenshot_path}[/dim]")
            except Exception:
                pass

        return stocks

    def _parse_stock_text(self, text: str) -> dict | None:
        """텍스트에서 종목 정보 추출"""
        lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
        if not lines:
            return None

        # 한국 주식 코드 (6자리 숫자)
        kr_code_match = re.search(r"\b(\d{6})\b", text)
        # 미국 주식 티커 (2-5자 영문 대문자)
        us_code_match = re.search(r"\b([A-Z]{2,5})\b", text)

        # 가격 패턴
        price_match = re.search(r"([\d,]+)원?", text)
        change_match = re.search(r"([+-]?\d+\.?\d*)%", text)

        code = kr_code_match.group(1) if kr_code_match else (us_code_match.group(1) if us_code_match else None)
        if not code:
            return None

        name = lines[0] if lines else "알 수 없음"
        market = self._detect_market(code)
        price = int(price_match.group(1).replace(",", "")) if price_match else 0
        change = float(change_match.group(1)) if change_match else 0.0

        return {
            "code": code,
            "name": name,
            "market": market,
            "current_price": price,
            "change_rate": change,
        }

    def _detect_market(self, code: str) -> str:
        """코드 형식으로 시장 추정"""
        if re.match(r"^\d{6}$", code):
            return "KRX"  # 한국 (KOSPI/KOSDAQ 구분은 yfinance 조회 시 결정)
        elif re.match(r"^[A-Z]{1,5}$", code):
            return "US"
        return "UNKNOWN"

    async def _manual_input_fallback(self) -> list[dict]:
        """관심종목을 수동으로 입력받는 폴백"""
        console.print()
        console.print("[bold yellow]관심종목 수동 입력 모드[/bold yellow]")
        console.print("[dim]종목코드(또는 티커)와 종목명을 입력해주세요.[/dim]")
        console.print("[dim]예시: 005930 삼성전자 / AAPL 애플[/dim]")
        console.print("[dim]입력 완료 후 빈 줄에서 Enter를 누르세요.[/dim]")
        console.print()

        stocks = []
        while True:
            line = input("  종목 입력 (코드 이름): ").strip()
            if not line:
                break
            parts = line.split(maxsplit=1)
            if len(parts) >= 2:
                code, name = parts[0], parts[1]
                market = self._detect_market(code.upper())
                stocks.append({
                    "code": code.upper() if market == "US" else code,
                    "name": name,
                    "market": market,
                    "current_price": 0,
                    "change_rate": 0.0,
                })
                console.print(f"  [green]✓[/green] {name} ({code}) 추가됨")
            else:
                console.print("  [red]입력 형식 오류: '코드 이름' 형식으로 입력해주세요.[/red]")

        return stocks
