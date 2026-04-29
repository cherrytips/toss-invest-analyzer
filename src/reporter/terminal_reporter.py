"""
터미널 리포트 출력 모듈
- Rich 라이브러리 기반 컬러풀한 터미널 출력
- 종목별 기술적 분석, 뉴스 요약, 투자 의견 표시
- 종합 대시보드 테이블
"""

from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.rule import Rule
from rich import box
from rich.align import Align

console = Console()

SIGNAL_STYLE = {
    "강력매수": "bold red",
    "매수": "red",
    "매수우위": "dark_orange",
    "중립": "white",
    "매도우위": "cornflower_blue",
    "매도": "blue",
    "강력매도": "bold blue",
}

SENTIMENT_STYLE = {
    "매우 긍정적": "bold green",
    "긍정적": "green",
    "중립": "white",
    "부정적": "red",
    "매우 부정적": "bold red",
}

RISK_STYLE = {
    "낮음": "green",
    "중간": "yellow",
    "높음": "red",
}


class TerminalReporter:
    def __init__(self, config):
        self.config = config

    def display_report(self, results: list[dict], chart_paths: dict):
        now = datetime.now().strftime("%Y년 %m월 %d일 %H:%M:%S")

        console.print()
        console.rule("[bold blue]📊 토스증권 관심종목 분석 리포트[/bold blue]")
        console.print(f"[dim]분석 시점: {now}  |  종목 수: {len(results)}개[/dim]", justify="center")
        console.print()

        # ── 종합 요약 테이블 ────────────────────────────────────────
        self._print_summary_table(results)
        console.print()

        # ── 개별 종목 상세 분석 ─────────────────────────────────────
        for r in results:
            self._print_stock_detail(r)
            console.print()

        # ── 차트/리포트 경로 ────────────────────────────────────────
        if chart_paths.get("html_report"):
            console.print(
                Panel(
                    f"[green]HTML 대시보드:[/green] {chart_paths['html_report']}",
                    title="📁 저장된 리포트",
                    border_style="green",
                )
            )

        console.print()
        console.rule("[dim]본 분석은 참고용이며 투자 결정의 최종 책임은 투자자 본인에게 있습니다.[/dim]")
        console.print()

    def _print_summary_table(self, results: list[dict]):
        table = Table(
            title="[bold]📋 관심종목 종합 현황[/bold]",
            box=box.ROUNDED,
            border_style="blue",
            header_style="bold cyan",
            show_lines=True,
        )

        table.add_column("종목명", style="bold", min_width=12)
        table.add_column("코드", justify="center", min_width=8)
        table.add_column("현재가", justify="right", min_width=10)
        table.add_column("등락률", justify="center", min_width=9)
        table.add_column("RSI", justify="center", min_width=8)
        table.add_column("MACD", justify="center", min_width=14)
        table.add_column("뉴스감성", justify="center", min_width=10)
        table.add_column("단기", justify="center", min_width=9)
        table.add_column("중기", justify="center", min_width=9)
        table.add_column("장기", justify="center", min_width=9)
        table.add_column("종합의견", justify="center", min_width=9)
        table.add_column("리스크", justify="center", min_width=7)

        for r in results:
            stock = r["stock"]
            technical = r.get("technical")
            news = r.get("news_analysis")
            opinion = r.get("opinion")

            name = stock.get("name", "")
            code = stock.get("code", "")
            price = f"{technical.current_price:,.0f}" if technical and technical.current_price else "-"
            change_1d = technical.price_change_1d if technical else 0
            change_str = f"{change_1d:+.2f}%"
            change_style = "red" if change_1d >= 0 else "blue"

            rsi = f"{technical.rsi:.1f}" if technical else "-"
            rsi_style = (
                "red" if technical and technical.rsi >= 70
                else "blue" if technical and technical.rsi <= 30
                else "white"
            )

            macd_cross = technical.macd_cross if technical else "-"
            macd_style = "red" if technical and "매수" in macd_cross else (
                "blue" if technical and "매도" in macd_cross else "white"
            )

            sentiment = news.sentiment_label if news else "-"
            sentiment_style = SENTIMENT_STYLE.get(sentiment, "white")

            short_sig = opinion.short_term_signal if opinion else "-"
            mid_sig = opinion.mid_term_signal if opinion else "-"
            long_sig = opinion.long_term_signal if opinion else "-"
            overall_sig = opinion.overall_signal if opinion else "-"
            risk = opinion.risk_level if opinion else "-"

            table.add_row(
                name,
                code,
                price,
                Text(change_str, style=change_style),
                Text(rsi, style=rsi_style),
                Text(macd_cross, style=macd_style),
                Text(sentiment, style=sentiment_style),
                Text(short_sig, style=SIGNAL_STYLE.get(short_sig, "white")),
                Text(mid_sig, style=SIGNAL_STYLE.get(mid_sig, "white")),
                Text(long_sig, style=SIGNAL_STYLE.get(long_sig, "white")),
                Text(overall_sig, style=SIGNAL_STYLE.get(overall_sig, "white")),
                Text(risk, style=RISK_STYLE.get(risk, "white")),
            )

        console.print(Align.center(table))

    def _print_stock_detail(self, r: dict):
        stock = r["stock"]
        technical = r.get("technical")
        news = r.get("news_analysis")
        opinion = r.get("opinion")
        fundamentals = r.get("fundamentals", {})

        name = stock.get("name", "")
        code = stock.get("code", "")
        overall_sig = opinion.overall_signal if opinion else "분석 중"
        sig_style = SIGNAL_STYLE.get(overall_sig, "white")

        title = f"[bold]{name}[/bold] [dim]({code})[/dim]  →  [{sig_style}]{overall_sig}[/{sig_style}]"
        console.print(Panel(title, border_style="cyan", padding=(0, 1)))

        # ── 가격 정보 ──
        if technical:
            price = technical.current_price
            c1d = technical.price_change_1d
            c5d = technical.price_change_5d
            c20d = technical.price_change_20d
            price_color = "red" if c1d >= 0 else "blue"

            console.print(
                f"  현재가 [bold]{price:,.0f}원[/bold]  "
                f"당일 [{price_color}]{c1d:+.2f}%[/{price_color}]  |  "
                f"5일 {c5d:+.2f}%  |  20일 {c20d:+.2f}%"
            )

        # ── 기술적 지표 테이블 ──
        if technical:
            tech_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
            tech_table.add_column("지표", style="dim", min_width=14)
            tech_table.add_column("값", min_width=16)
            tech_table.add_column("지표", style="dim", min_width=14)
            tech_table.add_column("값", min_width=16)

            rsi_style = (
                "bold red" if technical.rsi >= 70 else
                "bold blue" if technical.rsi <= 30 else "white"
            )
            vol_style = "yellow" if technical.volume_ratio >= 2 else "white"

            tech_table.add_row(
                "RSI(14)",
                Text(f"{technical.rsi:.1f}  ({technical.rsi_signal})", style=rsi_style),
                "MA5 / MA20",
                f"{technical.ma5:,.0f} / {technical.ma20:,.0f}",
            )
            tech_table.add_row(
                "MACD",
                Text(technical.macd_cross),
                "볼린저밴드",
                Text(technical.bb_signal),
            )
            tech_table.add_row(
                "스토캐스틱",
                Text(technical.stoch_signal),
                "거래량비율",
                Text(f"{technical.volume_ratio:.1f}배  ({technical.volume_signal})", style=vol_style),
            )
            tech_table.add_row(
                "단기추세",
                Text(technical.trend_short,
                     style="red" if "상승" in technical.trend_short else "blue" if "하락" in technical.trend_short else "white"),
                "중기추세",
                Text(technical.trend_mid,
                     style="red" if "상승" in technical.trend_mid else "blue" if "하락" in technical.trend_mid else "white"),
            )
            tech_table.add_row(
                "52주 고점 대비",
                f"{technical.distance_from_52w_high:+.1f}%",
                "52주 저점 대비",
                f"{technical.distance_from_52w_low:+.1f}%",
            )

            console.print("  [bold cyan]◆ 기술적 분석[/bold cyan]")
            console.print(tech_table)

        # ── 기술적 신호 ──
        if technical and technical.signals:
            console.print("  [bold cyan]◆ 주요 신호[/bold cyan]")
            for sig_name, sig_desc, sig_type in technical.signals[:5]:
                style = "red" if sig_type == "buy" else "blue"
                icon = "📈" if sig_type == "buy" else "📉"
                console.print(f"    {icon} [{style}][{sig_name}][/{style}] {sig_desc}")

        # ── 펀더멘털 ──
        if fundamentals:
            per = fundamentals.get("per", 0)
            pbr = fundamentals.get("pbr", 0)
            roe = fundamentals.get("roe", 0)
            mktcap = fundamentals.get("market_cap", "N/A")
            sector = fundamentals.get("sector", "-")
            div_yield = fundamentals.get("dividend_yield", 0)

            console.print("  [bold cyan]◆ 펀더멘털[/bold cyan]")
            console.print(
                f"    시가총액: [bold]{mktcap}[/bold]  |  "
                f"PER: [bold]{per:.1f}배[/bold]  |  "
                f"PBR: {pbr:.1f}배  |  "
                f"ROE: {roe:.1f}%  |  "
                f"배당수익률: {div_yield:.1f}%  |  "
                f"섹터: {sector}"
            )

        # ── 뉴스 분석 ──
        if news:
            sentiment_style = SENTIMENT_STYLE.get(news.sentiment_label, "white")
            console.print("  [bold cyan]◆ 뉴스 분석[/bold cyan]")
            console.print(
                f"    감성: [{sentiment_style}]{news.sentiment_label}[/{sentiment_style}]  "
                f"|  호재 {news.positive_count}건  |  악재 {news.negative_count}건  "
                f"|  키워드: {', '.join(news.key_keywords[:5])}"
            )
            if news.positive_news:
                console.print(f"    [green]📈 호재:[/green] {news.positive_news[0]}")
            if news.negative_news:
                console.print(f"    [red]📉 악재:[/red] {news.negative_news[0]}")

        # ── 투자 의견 ──
        if opinion:
            console.print("  [bold cyan]◆ 투자 의견[/bold cyan]")
            short_s = SIGNAL_STYLE.get(opinion.short_term_signal, "white")
            mid_s = SIGNAL_STYLE.get(opinion.mid_term_signal, "white")
            long_s = SIGNAL_STYLE.get(opinion.long_term_signal, "white")
            console.print(
                f"    단기(1~4주): [{short_s}]{opinion.short_term_signal}[/{short_s}]  "
                f"({opinion.short_term_score:+d}점)  |  "
                f"중기(1~6개월): [{mid_s}]{opinion.mid_term_signal}[/{mid_s}]  "
                f"({opinion.mid_term_score:+d}점)  |  "
                f"장기(1~3년): [{long_s}]{opinion.long_term_signal}[/{long_s}]  "
                f"({opinion.long_term_score:+d}점)"
            )
            if opinion.short_term_rationale:
                console.print(f"    단기 근거: {opinion.short_term_rationale[0]}")
            if opinion.long_term_rationale:
                console.print(f"    장기 근거: {opinion.long_term_rationale[0]}")

            console.print()
            # 종합 요약 패널
            summary_text = opinion.overall_summary
            risk_style = RISK_STYLE.get(opinion.risk_level, "white")
            overall_style = SIGNAL_STYLE.get(opinion.overall_signal, "white")
            console.print(
                Panel(
                    f"[{overall_style}]종합 의견: {opinion.overall_signal} ({opinion.overall_score:+d}점)[/{overall_style}]  |  "
                    f"리스크: [{risk_style}]{opinion.risk_level}[/{risk_style}]\n\n"
                    + summary_text,
                    title=f"[bold]{name} 종합 투자 의견[/bold]",
                    border_style="yellow",
                    padding=(1, 2),
                )
            )
