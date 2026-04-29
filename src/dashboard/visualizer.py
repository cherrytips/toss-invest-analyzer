"""
대시보드 시각화 모듈
- Plotly 기반 인터랙티브 HTML 차트 생성
- 개별 종목 캔들차트 + 기술적 지표
- 섹터별 분포, 등락률 비교, 거래량 추이
- HTML 통합 리포트로 저장
"""

import webbrowser
from pathlib import Path
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from rich.console import Console

console = Console()

SIGNAL_COLORS = {
    "강력매수": "#FF0000",
    "매수": "#FF6B6B",
    "매수우위": "#FFA07A",
    "중립": "#808080",
    "매도우위": "#87CEEB",
    "매도": "#4169E1",
    "강력매도": "#00008B",
}

SENTIMENT_COLORS = {
    "매우 긍정적": "#2ECC71",
    "긍정적": "#58D68D",
    "중립": "#AEB6BF",
    "부정적": "#F1948A",
    "매우 부정적": "#E74C3C",
}


class Visualizer:
    def __init__(self, config):
        self.config = config
        self.output_dir = config.output_dir
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def generate_dashboard(self, results: list[dict]) -> dict:
        """모든 차트를 생성하고 HTML 리포트로 저장"""
        chart_paths = {}

        if not results:
            return chart_paths

        # 개별 종목 차트
        stock_charts_html = []
        for r in results:
            stock = r["stock"]
            ohlcv = r.get("ohlcv")
            technical = r.get("technical")
            if ohlcv is not None and not ohlcv.empty:
                fig = self._create_stock_chart(stock, ohlcv, technical)
                stock_charts_html.append((stock["name"], fig.to_html(full_html=False, include_plotlyjs=False)))

        # 종합 비교 차트
        overview_fig = self._create_overview_chart(results)
        sector_fig = self._create_sector_chart(results)
        score_fig = self._create_score_chart(results)

        # HTML 리포트 생성
        html_path = self._generate_html_report(
            results, stock_charts_html, overview_fig, sector_fig, score_fig
        )
        chart_paths["html_report"] = str(html_path)

        if self.config.open_browser_dashboard and html_path.exists():
            webbrowser.open(html_path.as_uri())
            console.print(f"[green]✓ 대시보드를 브라우저에서 열었습니다: {html_path.name}[/green]")

        return chart_paths

    def _create_stock_chart(self, stock: dict, df: pd.DataFrame, technical) -> go.Figure:
        """개별 종목 캔들차트 + 이동평균 + RSI + MACD + 거래량"""
        name = stock.get("name", "")

        fig = make_subplots(
            rows=4, cols=1,
            shared_xaxes=True,
            row_heights=[0.5, 0.15, 0.2, 0.15],
            vertical_spacing=0.02,
            subplot_titles=[
                f"{name} 주가 차트",
                "거래량",
                "RSI (14)",
                "MACD",
            ],
        )

        # ─── 캔들차트 ────────────────────────────────────────────
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                name="OHLC",
                increasing_line_color="#E74C3C",
                decreasing_line_color="#3498DB",
            ),
            row=1, col=1,
        )

        # 이동평균선
        colors_ma = {"MA5": "#FFD700", "MA20": "#FF8C00", "MA60": "#00CED1", "MA120": "#9370DB"}
        for period, color in [(5, "#FFD700"), (20, "#FF8C00"), (60, "#00CED1"), (120, "#9370DB")]:
            if len(df) >= period:
                ma = df["close"].rolling(period).mean()
                fig.add_trace(
                    go.Scatter(
                        x=df.index, y=ma,
                        name=f"MA{period}",
                        line=dict(color=color, width=1),
                        opacity=0.8,
                    ),
                    row=1, col=1,
                )

        # 볼린저 밴드
        if len(df) >= 20:
            sma20 = df["close"].rolling(20).mean()
            std20 = df["close"].rolling(20).std()
            bb_upper = sma20 + 2 * std20
            bb_lower = sma20 - 2 * std20
            fig.add_trace(
                go.Scatter(
                    x=df.index.tolist() + df.index.tolist()[::-1],
                    y=bb_upper.tolist() + bb_lower.tolist()[::-1],
                    fill="toself",
                    fillcolor="rgba(68,68,255,0.05)",
                    line=dict(color="rgba(68,68,255,0.2)"),
                    name="볼린저밴드",
                    showlegend=True,
                ),
                row=1, col=1,
            )

        # ─── 거래량 ──────────────────────────────────────────────
        colors = ["#E74C3C" if c >= o else "#3498DB" for c, o in zip(df["close"], df["open"])]
        fig.add_trace(
            go.Bar(x=df.index, y=df["volume"], name="거래량", marker_color=colors, opacity=0.7),
            row=2, col=1,
        )
        vol_ma20 = df["volume"].rolling(20).mean()
        fig.add_trace(
            go.Scatter(x=df.index, y=vol_ma20, name="거래량MA20",
                      line=dict(color="#FFA500", width=1)),
            row=2, col=1,
        )

        # ─── RSI ────────────────────────────────────────────────
        import numpy as np
        delta = df["close"].diff()
        gains = delta.where(delta > 0, 0.0)
        losses = -delta.where(delta < 0, 0.0)
        avg_gain = gains.ewm(com=13, adjust=False).mean()
        avg_loss = losses.ewm(com=13, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))

        fig.add_trace(
            go.Scatter(x=df.index, y=rsi, name="RSI(14)",
                      line=dict(color="#8E44AD", width=1.5)),
            row=3, col=1,
        )
        for level, color in [(70, "rgba(231,76,60,0.3)"), (30, "rgba(52,152,219,0.3)")]:
            fig.add_hline(y=level, line_dash="dot", line_color=color, row=3, col=1)

        # ─── MACD ────────────────────────────────────────────────
        ema12 = df["close"].ewm(span=12, adjust=False).mean()
        ema26 = df["close"].ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        hist = macd_line - signal_line

        fig.add_trace(
            go.Scatter(x=df.index, y=macd_line, name="MACD",
                      line=dict(color="#27AE60", width=1.5)),
            row=4, col=1,
        )
        fig.add_trace(
            go.Scatter(x=df.index, y=signal_line, name="Signal",
                      line=dict(color="#E74C3C", width=1, dash="dash")),
            row=4, col=1,
        )
        hist_colors = ["#E74C3C" if v >= 0 else "#3498DB" for v in hist]
        fig.add_trace(
            go.Bar(x=df.index, y=hist, name="MACD Hist", marker_color=hist_colors, opacity=0.6),
            row=4, col=1,
        )

        fig.update_layout(
            title=f"{name} 기술적 분석",
            template="plotly_dark",
            height=700,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis_rangeslider_visible=False,
            margin=dict(l=50, r=50, t=80, b=30),
        )
        fig.update_yaxes(title_text="가격", row=1, col=1)
        fig.update_yaxes(title_text="거래량", row=2, col=1)
        fig.update_yaxes(title_text="RSI", row=3, col=1, range=[0, 100])
        fig.update_yaxes(title_text="MACD", row=4, col=1)

        return fig

    def _create_overview_chart(self, results: list[dict]) -> go.Figure:
        """종목별 등락률 비교 차트"""
        names = []
        changes = []
        colors = []

        for r in results:
            stock = r["stock"]
            technical = r.get("technical")
            change = technical.price_change_1d if technical else stock.get("change_rate", 0)
            names.append(stock.get("name", ""))
            changes.append(round(change, 2))
            colors.append("#E74C3C" if change >= 0 else "#3498DB")

        fig = go.Figure(
            go.Bar(
                x=names,
                y=changes,
                marker_color=colors,
                text=[f"{c:+.2f}%" for c in changes],
                textposition="outside",
            )
        )
        fig.update_layout(
            title="관심종목 당일 등락률",
            template="plotly_dark",
            yaxis_title="등락률 (%)",
            height=350,
            margin=dict(l=50, r=50, t=60, b=80),
            xaxis_tickangle=-30,
        )
        fig.add_hline(y=0, line_dash="solid", line_color="white", line_width=0.5)
        return fig

    def _create_sector_chart(self, results: list[dict]) -> go.Figure:
        """섹터별 분포 파이 차트"""
        sectors = {}
        for r in results:
            sector = r.get("fundamentals", {}).get("sector", "기타") or "기타"
            sectors[sector] = sectors.get(sector, 0) + 1

        fig = go.Figure(
            go.Pie(
                labels=list(sectors.keys()),
                values=list(sectors.values()),
                hole=0.4,
                textposition="inside",
                textinfo="label+percent",
            )
        )
        fig.update_layout(
            title="섹터별 분포",
            template="plotly_dark",
            height=350,
            margin=dict(l=30, r=30, t=60, b=30),
        )
        return fig

    def _create_score_chart(self, results: list[dict]) -> go.Figure:
        """종목별 투자 점수 레이더/바 차트"""
        names, short_scores, mid_scores, long_scores = [], [], [], []

        for r in results:
            opinion = r.get("opinion")
            if opinion:
                names.append(r["stock"].get("name", ""))
                short_scores.append(opinion.short_term_score)
                mid_scores.append(opinion.mid_term_score)
                long_scores.append(opinion.long_term_score)

        fig = go.Figure()
        fig.add_trace(go.Bar(name="단기(1~4주)", x=names, y=short_scores, marker_color="#E74C3C"))
        fig.add_trace(go.Bar(name="중기(1~6개월)", x=names, y=mid_scores, marker_color="#F39C12"))
        fig.add_trace(go.Bar(name="장기(1~3년)", x=names, y=long_scores, marker_color="#27AE60"))

        fig.update_layout(
            title="종목별 투자 점수 (-100 ~ +100)",
            template="plotly_dark",
            barmode="group",
            yaxis_title="점수",
            height=350,
            margin=dict(l=50, r=50, t=60, b=80),
            xaxis_tickangle=-30,
        )
        fig.add_hline(y=0, line_dash="solid", line_color="white", line_width=0.5)
        return fig

    def _generate_html_report(
        self,
        results: list[dict],
        stock_charts: list,
        overview_fig,
        sector_fig,
        score_fig,
    ) -> Path:
        """통합 HTML 리포트 생성"""
        now = datetime.now().strftime("%Y년 %m월 %d일 %H:%M")

        # 종목 카드 HTML
        stock_cards = []
        for r in results:
            stock = r["stock"]
            technical = r.get("technical")
            opinion = r.get("opinion")
            news = r.get("news_analysis")

            if not opinion:
                continue

            signal = opinion.overall_signal
            signal_color = SIGNAL_COLORS.get(signal, "#808080")
            sentiment_color = SENTIMENT_COLORS.get(
                news.sentiment_label if news else "중립", "#AEB6BF"
            )

            current_price = technical.current_price if technical else 0
            change_1d = technical.price_change_1d if technical else 0
            change_icon = "▲" if change_1d >= 0 else "▼"
            change_color = "#E74C3C" if change_1d >= 0 else "#3498DB"

            rsi = technical.rsi if technical else 0
            vol_ratio = technical.volume_ratio if technical else 1

            pos_news = "<br>".join(f"• {n}" for n in (news.positive_news[:3] if news else []))
            neg_news = "<br>".join(f"• {n}" for n in (news.negative_news[:3] if news else []))

            card = f"""
            <div class="stock-card">
                <div class="card-header">
                    <h2>{stock.get('name', '')} <small>({stock.get('code', '')})</small></h2>
                    <div class="signal-badge" style="background:{signal_color};">{signal}</div>
                </div>
                <div class="price-row">
                    <span class="current-price">{current_price:,.0f}원</span>
                    <span class="change" style="color:{change_color};">
                        {change_icon} {abs(change_1d):.2f}%
                    </span>
                </div>
                <div class="metrics-grid">
                    <div class="metric"><label>RSI</label><span>{rsi:.1f}</span></div>
                    <div class="metric"><label>거래량비율</label><span>{vol_ratio:.1f}x</span></div>
                    <div class="metric"><label>단기</label><span>{opinion.short_term_signal}</span></div>
                    <div class="metric"><label>중기</label><span>{opinion.mid_term_signal}</span></div>
                    <div class="metric"><label>장기</label><span>{opinion.long_term_signal}</span></div>
                    <div class="metric"><label>리스크</label><span>{opinion.risk_level}</span></div>
                </div>
                <div class="news-section">
                    <div class="news-positive">
                        <h4>📈 호재</h4>
                        <p>{pos_news if pos_news else "해당 없음"}</p>
                    </div>
                    <div class="news-negative">
                        <h4>📉 악재</h4>
                        <p>{neg_news if neg_news else "해당 없음"}</p>
                    </div>
                </div>
                <div class="summary-box">{opinion.overall_summary.replace(chr(10), '<br>')}</div>
            </div>
            """
            stock_cards.append(card)

        stock_cards_html = "\n".join(stock_cards)

        # 종목별 차트 탭
        chart_tabs = ""
        chart_contents = ""
        for i, (name, chart_html) in enumerate(stock_charts):
            active = "active" if i == 0 else ""
            chart_tabs += f'<button class="tab-btn {active}" onclick="showTab({i})">{name}</button>'
            display = "block" if i == 0 else "none"
            chart_contents += f'<div class="tab-content" id="tab-{i}" style="display:{display};">{chart_html}</div>'

        html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>토스증권 관심종목 분석 리포트 - {now}</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0D1117; color: #C9D1D9; font-family: 'Segoe UI', sans-serif; }}
  .header {{ background: linear-gradient(135deg, #1A56DB, #0D4A8A); padding: 30px 40px; }}
  .header h1 {{ font-size: 2em; color: white; margin-bottom: 5px; }}
  .header .timestamp {{ color: rgba(255,255,255,0.7); font-size: 0.9em; }}
  .container {{ max-width: 1400px; margin: 0 auto; padding: 30px 20px; }}
  .section-title {{ font-size: 1.4em; color: #58A6FF; margin: 30px 0 15px; border-left: 4px solid #1A56DB; padding-left: 12px; }}
  .charts-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px; }}
  .chart-box {{ background: #161B22; border-radius: 12px; padding: 15px; border: 1px solid #30363D; }}
  .chart-box-full {{ background: #161B22; border-radius: 12px; padding: 15px; border: 1px solid #30363D; margin-bottom: 20px; }}
  .stocks-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); gap: 20px; margin-bottom: 30px; }}
  .stock-card {{ background: #161B22; border-radius: 12px; padding: 20px; border: 1px solid #30363D; }}
  .card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }}
  .card-header h2 {{ font-size: 1.2em; color: #E6EDF3; }}
  .card-header small {{ color: #8B949E; font-size: 0.7em; }}
  .signal-badge {{ padding: 5px 14px; border-radius: 20px; font-weight: bold; color: white; font-size: 0.9em; }}
  .price-row {{ margin-bottom: 15px; }}
  .current-price {{ font-size: 1.6em; font-weight: bold; color: #E6EDF3; }}
  .change {{ font-size: 1.1em; margin-left: 12px; font-weight: bold; }}
  .metrics-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 15px; }}
  .metric {{ background: #21262D; border-radius: 8px; padding: 8px 10px; text-align: center; }}
  .metric label {{ display: block; font-size: 0.72em; color: #8B949E; margin-bottom: 3px; }}
  .metric span {{ font-size: 0.9em; color: #E6EDF3; font-weight: 500; }}
  .news-section {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; }}
  .news-positive {{ background: rgba(46,204,113,0.1); border: 1px solid rgba(46,204,113,0.3); border-radius: 8px; padding: 12px; }}
  .news-negative {{ background: rgba(231,76,60,0.1); border: 1px solid rgba(231,76,60,0.3); border-radius: 8px; padding: 12px; }}
  .news-positive h4 {{ color: #2ECC71; margin-bottom: 6px; font-size: 0.85em; }}
  .news-negative h4 {{ color: #E74C3C; margin-bottom: 6px; font-size: 0.85em; }}
  .news-positive p, .news-negative p {{ font-size: 0.78em; color: #C9D1D9; line-height: 1.5; }}
  .summary-box {{ background: #21262D; border-radius: 8px; padding: 12px; font-size: 0.82em; line-height: 1.6; color: #C9D1D9; border-left: 3px solid #1A56DB; }}
  .tab-container {{ background: #161B22; border-radius: 12px; padding: 15px; border: 1px solid #30363D; }}
  .tab-nav {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 15px; }}
  .tab-btn {{ background: #21262D; color: #C9D1D9; border: 1px solid #30363D; padding: 7px 14px; border-radius: 8px; cursor: pointer; font-size: 0.85em; transition: all 0.2s; }}
  .tab-btn.active, .tab-btn:hover {{ background: #1A56DB; color: white; border-color: #1A56DB; }}
  .footer {{ text-align: center; padding: 30px; color: #8B949E; font-size: 0.85em; border-top: 1px solid #30363D; margin-top: 20px; }}
</style>
</head>
<body>
<div class="header">
  <h1>📊 토스증권 관심종목 분석 리포트</h1>
  <div class="timestamp">분석 시점: {now} | 종목 수: {len(results)}개</div>
</div>
<div class="container">

  <div class="section-title">📈 시장 개요</div>
  <div class="charts-grid">
    <div class="chart-box">{overview_fig.to_html(full_html=False, include_plotlyjs=False)}</div>
    <div class="chart-box">{sector_fig.to_html(full_html=False, include_plotlyjs=False)}</div>
  </div>

  <div class="section-title">🎯 투자 점수 분석</div>
  <div class="chart-box-full">{score_fig.to_html(full_html=False, include_plotlyjs=False)}</div>

  <div class="section-title">💼 종목별 상세 분석</div>
  <div class="stocks-grid">{stock_cards_html}</div>

  <div class="section-title">📉 기술적 분석 차트</div>
  <div class="tab-container">
    <div class="tab-nav">{chart_tabs}</div>
    {chart_contents}
  </div>

</div>
<div class="footer">
  토스증권 관심종목 분석 도구 | 본 리포트는 참고용이며 투자 결정의 최종 책임은 투자자 본인에게 있습니다.
</div>
<script>
function showTab(idx) {{
  document.querySelectorAll('.tab-content').forEach((el, i) => {{
    el.style.display = i === idx ? 'block' : 'none';
  }});
  document.querySelectorAll('.tab-btn').forEach((btn, i) => {{
    btn.classList.toggle('active', i === idx);
  }});
}}
</script>
</body>
</html>"""

        report_path = self.output_dir / f"report_{self.timestamp}.html"
        report_path.write_text(html, encoding="utf-8")
        console.print(f"[green]✓ HTML 리포트 저장: {report_path.name}[/green]")

        # latest.html 심볼릭 복사 (윈도우 호환)
        latest_path = self.output_dir / "latest.html"
        latest_path.write_text(html, encoding="utf-8")

        return latest_path
