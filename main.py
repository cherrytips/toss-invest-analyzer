"""
토스증권 관심종목 분석 도구 - 메인 실행 파일
실행: python main.py
옵션:
  --clear-session   저장된 로그인 세션 초기화
  --no-browser      브라우저 없이 수동 입력 모드
"""

import asyncio
import sys
from datetime import datetime

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel

from config import Config
from src.auth.toss_login import TossLogin
from src.scraper.watchlist_scraper import WatchlistScraper
from src.scraper.news_scraper import NewsScraper
from src.data.stock_data import StockData
from src.analyzer.technical_analyzer import TechnicalAnalyzer
from src.analyzer.news_analyzer import NewsAnalyzer
from src.analyzer.investment_advisor import InvestmentAdvisor
from src.dashboard.visualizer import Visualizer
from src.reporter.terminal_reporter import TerminalReporter

console = Console()


def print_banner():
    banner = """
╔══════════════════════════════════════════════════════╗
║     📊  토스증권 관심종목 분석 도구  v1.0             ║
║     주식시장 10년차 베테랑 분석가의 인사이트            ║
╚══════════════════════════════════════════════════════╝"""
    console.print(f"[bold blue]{banner}[/bold blue]")
    console.print(f"[dim]  분석 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]\n")


async def main():
    print_banner()

    # ── 인수 처리 ──────────────────────────────────────────────
    args = sys.argv[1:]
    clear_session = "--clear-session" in args
    no_browser = "--no-browser" in args

    # ── 설정 로드 ──────────────────────────────────────────────
    try:
        config = Config()
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]설정 오류:[/red] {e}")
        sys.exit(1)

    console.print(
        Panel(
            f"사용자: [bold]{config.user_name}[/bold]  "
            f"|  전화번호: {config.user_phone}  "
            f"|  AI 분석: {'✓ 활성' if config.use_ai else '✗ 비활성 (규칙 기반)'}",
            title="사용자 정보",
            border_style="dim",
        )
    )

    # ── 세션 초기화 ────────────────────────────────────────────
    if clear_session:
        TossLogin(config).clear_session()

    # ── 1단계: 토스증권 로그인 및 관심종목 수집 ──────────────────
    watchlist = []

    if no_browser:
        # 수동 입력 모드
        console.print("[yellow]수동 입력 모드: 관심종목을 직접 입력해주세요.[/yellow]")
        from src.scraper.watchlist_scraper import WatchlistScraper as WS
        scraper_tmp = WS(None, config)
        watchlist = await scraper_tmp._manual_input_fallback()
    else:
        console.print("\n[bold yellow]Step 1.[/bold yellow] 토스증권 로그인 및 관심종목 수집")
        login = TossLogin(config)
        page, browser = await login.login()

        if page is None:
            console.print("[red]로그인 실패. --no-browser 옵션으로 수동 입력을 사용할 수 있습니다.[/red]")
            sys.exit(1)

        scraper = WatchlistScraper(page, config)
        watchlist = await scraper.get_watchlist()
        await browser.close()

    if not watchlist:
        console.print("[red]관심종목이 없습니다. 프로그램을 종료합니다.[/red]")
        sys.exit(1)

    console.print(
        f"\n[green]✓ 관심종목 {len(watchlist)}개 수집 완료[/green]: "
        + ", ".join(s["name"] for s in watchlist)
    )

    # ── 2단계: 종목 분석 ──────────────────────────────────────
    console.print("\n[bold yellow]Step 2.[/bold yellow] 종목 데이터 수집 및 분석")

    stock_fetcher = StockData(config)
    news_scraper = NewsScraper(config)
    tech_analyzer = TechnicalAnalyzer(config)
    news_analyzer = NewsAnalyzer(config)
    advisor = InvestmentAdvisor(config)

    results = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30),
        TaskProgressColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task("[cyan]분석 중...", total=len(watchlist))

        for stock in watchlist:
            name = stock.get("name", stock.get("code", ""))
            progress.update(task, description=f"[cyan]{name}[/cyan] 분석 중...")

            # 주가 데이터 수집
            ohlcv = stock_fetcher.get_ohlcv(stock)
            fundamentals = stock_fetcher.get_fundamentals(stock)

            # 뉴스 수집
            news_list = news_scraper.get_news(stock)

            # 기술적 분석
            technical = tech_analyzer.analyze(stock, ohlcv)

            # 뉴스 분석
            news_analysis = news_analyzer.analyze(stock, news_list)

            # 투자 의견
            opinion = advisor.generate_opinion(stock, technical, news_analysis, fundamentals)

            results.append({
                "stock": stock,
                "ohlcv": ohlcv,
                "fundamentals": fundamentals,
                "news": news_list,
                "technical": technical,
                "news_analysis": news_analysis,
                "opinion": opinion,
            })

            progress.advance(task)

    # ── 3단계: 대시보드 생성 ──────────────────────────────────
    console.print("\n[bold yellow]Step 3.[/bold yellow] 대시보드 및 차트 생성")
    visualizer = Visualizer(config)
    chart_paths = visualizer.generate_dashboard(results)

    # ── 4단계: 터미널 리포트 출력 ─────────────────────────────
    console.print("\n[bold yellow]Step 4.[/bold yellow] 분석 결과 출력\n")
    reporter = TerminalReporter(config)
    reporter.display_report(results, chart_paths)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]사용자에 의해 중단되었습니다.[/yellow]")
    except Exception as e:
        console.print(f"\n[red]오류 발생:[/red] {e}")
        import traceback
        console.print_exception()
        sys.exit(1)
