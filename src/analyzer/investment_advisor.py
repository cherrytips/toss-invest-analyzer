"""
종합 투자 의견 모듈
- 기술적 분석 + 펀더멘털 + 뉴스 감성을 결합
- 단기/중기/장기 투자 의견과 근거 제시
- 10년차 베테랑 증권 분석가 관점의 종합 의견
"""

from dataclasses import dataclass, field
from src.analyzer.technical_analyzer import TechnicalResult
from src.analyzer.news_analyzer import NewsAnalysisResult


@dataclass
class InvestmentOpinion:
    # 단기 (1~4주)
    short_term_signal: str = "중립"
    short_term_score: int = 0
    short_term_rationale: list = field(default_factory=list)

    # 중기 (1~6개월)
    mid_term_signal: str = "중립"
    mid_term_score: int = 0
    mid_term_rationale: list = field(default_factory=list)

    # 장기 (1~3년)
    long_term_signal: str = "중립"
    long_term_score: int = 0
    long_term_rationale: list = field(default_factory=list)

    # 종합
    overall_signal: str = "중립"
    overall_score: int = 0
    overall_summary: str = ""

    # 리스크 레벨
    risk_level: str = "중간"

    # 지지/저항선
    support_price: float = 0.0
    resistance_price: float = 0.0
    target_price_short: float = 0.0


SCORE_TO_SIGNAL = [
    (60, "강력매수"),
    (30, "매수"),
    (10, "매수우위"),
    (-10, "중립"),
    (-30, "매도우위"),
    (-60, "매도"),
    (-100, "강력매도"),
]


def score_to_signal(score: int) -> str:
    for threshold, label in SCORE_TO_SIGNAL:
        if score >= threshold:
            return label
    return "강력매도"


class InvestmentAdvisor:
    def __init__(self, config):
        self.config = config
        self._ai_client = None
        if config.use_ai:
            self._init_ai()

    def _init_ai(self):
        try:
            from openai import OpenAI
            self._ai_client = OpenAI(api_key=self.config.openai_api_key)
        except ImportError:
            pass

    def generate_opinion(
        self,
        stock: dict,
        technical: TechnicalResult,
        news: NewsAnalysisResult,
        fundamentals: dict,
    ) -> InvestmentOpinion:
        opinion = InvestmentOpinion()

        # ── 단기 분석 (모멘텀 + 거래량 + 뉴스) ──────────────────────────
        short_score = 0
        short_rationale = []

        # 기술적 점수 반영 (60%)
        tech_contribution = int(technical.score * 0.6)
        short_score += tech_contribution

        # 뉴스 감성 반영 (40%)
        news_contribution = int(news.sentiment_score * 40)
        short_score += news_contribution

        # 거래량 급증 모멘텀 체크
        if technical.volume_ratio >= 2.0 and technical.price_change_1d > 1.0:
            short_score += 15
            short_rationale.append("거래량 급증 + 당일 강한 상승 → 강한 매수 모멘텀")
        elif technical.volume_ratio >= 2.0 and technical.price_change_1d < -1.0:
            short_score -= 15
            short_rationale.append("거래량 급증 + 당일 강한 하락 → 강한 매도 압력")

        if technical.macd_cross == "골든크로스(매수)":
            short_score += 15
            short_rationale.append("MACD 골든크로스 발생 → 단기 상승 모멘텀 형성")
        elif technical.macd_cross == "데드크로스(매도)":
            short_score -= 15
            short_rationale.append("MACD 데드크로스 발생 → 단기 하락 위험")

        if technical.rsi <= 30:
            short_score += 10
            short_rationale.append(f"RSI {technical.rsi:.0f} - 과매도 진입 → 단기 반등 가능성")
        elif technical.rsi >= 70:
            short_score -= 10
            short_rationale.append(f"RSI {technical.rsi:.0f} - 과매수 진입 → 단기 조정 가능성")

        if not short_rationale:
            short_rationale.append(f"단기 기술적 점수 {technical.score:+d}점, 뉴스 감성 '{news.sentiment_label}'")

        opinion.short_term_score = max(-100, min(100, short_score))
        opinion.short_term_signal = score_to_signal(opinion.short_term_score)
        opinion.short_term_rationale = short_rationale

        # ── 중기 분석 (실적 + 섹터 트렌드 + MA 추세) ──────────────────
        mid_score = 0
        mid_rationale = []

        # 이동평균 추세
        if technical.trend_mid == "강한 상승":
            mid_score += 25
            mid_rationale.append("20일/60일 이동평균 정배열 강한 상승 추세")
        elif technical.trend_mid == "상승":
            mid_score += 12
            mid_rationale.append("중기 이동평균 상승 추세 유지")
        elif technical.trend_mid == "강한 하락":
            mid_score -= 25
            mid_rationale.append("20일/60일 이동평균 역배열 강한 하락 추세")
        elif technical.trend_mid == "하락":
            mid_score -= 12
            mid_rationale.append("중기 이동평균 하락 추세")

        # 실적 성장성
        rev_growth = fundamentals.get("revenue_growth", 0) or 0
        earn_growth = fundamentals.get("earnings_growth", 0) or 0
        if earn_growth > 20:
            mid_score += 20
            mid_rationale.append(f"영업이익 성장률 {earn_growth:.1f}% - 강한 실적 모멘텀")
        elif earn_growth > 5:
            mid_score += 10
            mid_rationale.append(f"영업이익 성장률 {earn_growth:.1f}% - 안정적 성장")
        elif earn_growth < -10:
            mid_score -= 20
            mid_rationale.append(f"영업이익 성장률 {earn_growth:.1f}% - 실적 악화 우려")

        # 뉴스 반영 (30%)
        mid_score += int(news.sentiment_score * 30)

        if not mid_rationale:
            mid_rationale.append(f"중기 추세 '{technical.trend_mid}', 실적 성장률 {earn_growth:.1f}%")

        opinion.mid_term_score = max(-100, min(100, mid_score))
        opinion.mid_term_signal = score_to_signal(opinion.mid_term_score)
        opinion.mid_term_rationale = mid_rationale

        # ── 장기 분석 (펀더멘털 + 산업 구조 + 성장성) ─────────────────
        long_score = 0
        long_rationale = []

        per = fundamentals.get("per", 0) or 0
        pbr = fundamentals.get("pbr", 0) or 0
        roe = fundamentals.get("roe", 0) or 0
        debt_eq = fundamentals.get("debt_to_equity", 0) or 0

        # PER 평가 (섹터별 평균과 비교가 이상적이나 단순 기준 적용)
        if 0 < per <= 12:
            long_score += 15
            long_rationale.append(f"PER {per:.1f} - 저평가 구간, 장기 매력적")
        elif 0 < per <= 20:
            long_score += 8
            long_rationale.append(f"PER {per:.1f} - 적정 밸류에이션")
        elif per > 40:
            long_score -= 15
            long_rationale.append(f"PER {per:.1f} - 고평가 위험, 성장 기대 반영 필수")
        elif per <= 0:
            long_score -= 10
            long_rationale.append("현재 순손실 중 - 흑자 전환 시점 중요")

        # ROE 평가
        if roe >= 20:
            long_score += 20
            long_rationale.append(f"ROE {roe:.1f}% - 우수한 자본 효율성")
        elif roe >= 10:
            long_score += 10
            long_rationale.append(f"ROE {roe:.1f}% - 양호한 수익성")
        elif roe < 0:
            long_score -= 15
            long_rationale.append(f"ROE {roe:.1f}% - 자본 잠식 우려")

        # 부채비율
        if 0 < debt_eq <= 50:
            long_score += 10
            long_rationale.append(f"부채비율 {debt_eq:.0f}% - 안정적 재무구조")
        elif debt_eq > 200:
            long_score -= 10
            long_rationale.append(f"부채비율 {debt_eq:.0f}% - 재무 레버리지 위험")

        # 52주 저점 대비 위치
        if technical.distance_from_52w_low > 0 and technical.distance_from_52w_high < -30:
            long_score += 8
            long_rationale.append(f"52주 고점 대비 {abs(technical.distance_from_52w_high):.0f}% 조정 - 장기 매수 기회 가능")

        if not long_rationale:
            long_rationale.append(f"PER {per:.1f} / PBR {pbr:.1f} / ROE {roe:.1f}% 기준 장기 평가")

        opinion.long_term_score = max(-100, min(100, long_score))
        opinion.long_term_signal = score_to_signal(opinion.long_term_score)
        opinion.long_term_rationale = long_rationale

        # ── 종합 의견 ─────────────────────────────────────────────────
        overall = (
            opinion.short_term_score * 0.3
            + opinion.mid_term_score * 0.35
            + opinion.long_term_score * 0.35
        )
        opinion.overall_score = int(overall)
        opinion.overall_signal = score_to_signal(opinion.overall_score)

        # 리스크 레벨
        beta = fundamentals.get("beta", 1.0) or 1.0
        bb_width = technical.bb_width or 0
        if beta > 1.5 or bb_width > 10:
            opinion.risk_level = "높음"
        elif beta < 0.8 and bb_width < 5:
            opinion.risk_level = "낮음"
        else:
            opinion.risk_level = "중간"

        # 지지/저항선 (볼린저 밴드 기반)
        opinion.support_price = technical.bb_lower
        opinion.resistance_price = technical.bb_upper
        if technical.current_price > 0:
            # 단기 목표주가: 현재가 + ATR(5일) * 2
            opinion.target_price_short = round(
                technical.current_price * (1 + max(0, opinion.short_term_score) / 500), 0
            )

        # 종합 요약
        if self._ai_client:
            opinion.overall_summary = self._ai_summary(stock, technical, news, fundamentals, opinion)
        else:
            opinion.overall_summary = self._rule_based_overall_summary(stock, opinion, technical, fundamentals)

        return opinion

    def _rule_based_overall_summary(
        self,
        stock: dict,
        opinion: InvestmentOpinion,
        technical: TechnicalResult,
        fundamentals: dict,
    ) -> str:
        name = stock.get("name", "해당 종목")
        parts = [
            f"【{name} 종합 분석】",
            f"단기: {opinion.short_term_signal} / 중기: {opinion.mid_term_signal} / 장기: {opinion.long_term_signal}",
        ]

        signal = opinion.overall_signal
        score = opinion.overall_score

        if "매수" in signal:
            if "강력" in signal:
                parts.append(
                    f"현재 기술적·펀더멘털 지표가 모두 긍정적으로 종합 {score:+d}점입니다. "
                    "적극적인 매수 전략을 검토할 시점입니다."
                )
            else:
                parts.append(
                    f"대부분의 지표가 매수 우위를 가리킵니다 (종합 {score:+d}점). "
                    "분할 매수 전략이 유효합니다."
                )
        elif "매도" in signal:
            if "강력" in signal:
                parts.append(
                    f"기술적 지표와 펀더멘털이 모두 부정적으로 종합 {score:+d}점입니다. "
                    "보유 시 손절 라인 확인 후 매도 검토가 필요합니다."
                )
            else:
                parts.append(
                    f"지표가 약세를 나타내고 있습니다 (종합 {score:+d}점). "
                    "비중을 줄이거나 관망하는 전략을 권장합니다."
                )
        else:
            parts.append(
                f"지표가 혼재된 상황입니다 (종합 {score:+d}점). "
                "명확한 방향성이 나타날 때까지 관망을 권장합니다."
            )

        per = fundamentals.get("per", 0) or 0
        roe = fundamentals.get("roe", 0) or 0
        if per > 0:
            parts.append(f"밸류에이션(PER {per:.1f}배 / ROE {roe:.1f}%) 기준 장기적 관점 참고 바랍니다.")

        parts.append(f"리스크 레벨: {opinion.risk_level}")

        return "\n".join(parts)

    def _ai_summary(
        self,
        stock: dict,
        technical: TechnicalResult,
        news: NewsAnalysisResult,
        fundamentals: dict,
        opinion: InvestmentOpinion,
    ) -> str:
        name = stock.get("name", "해당 종목")
        per = fundamentals.get("per", "N/A")
        roe = fundamentals.get("roe", "N/A")

        prompt = (
            f"당신은 10년차 베테랑 증권 분석가입니다.\n\n"
            f"종목: {name}\n"
            f"현재가: {technical.current_price:,.0f}\n"
            f"RSI: {technical.rsi:.1f} ({technical.rsi_signal})\n"
            f"MACD: {technical.macd_cross}\n"
            f"볼린저밴드 위치: {technical.bb_position:.0%}\n"
            f"거래량 비율: {technical.volume_ratio:.1f}배\n"
            f"뉴스 감성: {news.sentiment_label} (호재 {news.positive_count}건, 악재 {news.negative_count}건)\n"
            f"PER: {per} / ROE: {roe}%\n"
            f"단기의견: {opinion.short_term_signal} / 중기: {opinion.mid_term_signal} / 장기: {opinion.long_term_signal}\n\n"
            "위 데이터를 바탕으로 투자 종합 의견을 3~4문장으로 작성해주세요. "
            "구체적인 투자 근거와 주의할 리스크를 포함해주세요. 한국어로 작성해주세요."
        )

        try:
            resp = self._ai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.4,
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            return self._rule_based_overall_summary(stock, opinion, technical, fundamentals)
