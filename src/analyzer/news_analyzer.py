"""
뉴스 감성 분석 모듈
- 한국어 금융 뉴스 키워드 기반 감성 분류
- OpenAI GPT 사용 가능 시 AI 기반 요약 및 감성 분석
- 호재 / 악재 뉴스 분류 및 요약
"""

from dataclasses import dataclass, field


@dataclass
class NewsAnalysisResult:
    total_count: int = 0
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    sentiment_score: float = 0.0  # -1.0 ~ 1.0
    sentiment_label: str = "중립"
    positive_news: list = field(default_factory=list)
    negative_news: list = field(default_factory=list)
    key_keywords: list = field(default_factory=list)
    summary: str = ""


# 한국 금융 뉴스 호재/악재 키워드
POSITIVE_KEYWORDS = [
    "급등", "상승", "호실적", "흑자", "매출 증가", "순이익 증가", "영업이익 증가",
    "신규 계약", "계약 체결", "수주", "신제품", "출시", "FDA 승인", "허가",
    "투자 유치", "증자", "배당", "자사주 매입", "목표주가 상향", "매수 추천",
    "실적 개선", "성장", "확대", "신고가", "돌파", "반등", "강세", "호조",
    "파트너십", "협약", "특허", "기술 수출", "글로벌 진출", "수출 증가",
    "어닝서프라이즈", "예상 상회", "컨센서스 상회", "호재", "긍정", "기대",
    "AI", "반도체 호황", "수요 증가", "점유율 확대",
]

NEGATIVE_KEYWORDS = [
    "급락", "하락", "적자", "손실", "매출 감소", "영업손실", "실적 악화",
    "리콜", "소송", "피소", "제재", "규제", "조사", "압수수색", "횡령",
    "목표주가 하향", "매도 추천", "투자의견 하향", "신저가", "붕괴",
    "우려", "악화", "부진", "실망", "하회", "어닝쇼크", "예상 하회",
    "구조조정", "감원", "폐업", "파산", "회생", "불확실성", "리스크",
    "대규모 손실", "충당금", "상각", "취소", "계약 해지", "악재",
    "반도체 불황", "수요 감소", "재고 과잉", "경쟁 심화",
]


class NewsAnalyzer:
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

    def analyze(self, stock: dict, news_list: list[dict]) -> NewsAnalysisResult:
        result = NewsAnalysisResult()
        result.total_count = len(news_list)

        if not news_list:
            result.summary = "수집된 뉴스가 없습니다."
            return result

        # 각 뉴스 감성 분류
        classified = []
        for article in news_list:
            title = article.get("title", "")
            content = article.get("content", "")
            full_text = title + " " + content

            sentiment, score, matched_keywords = self._classify_sentiment(full_text)
            classified.append({
                **article,
                "sentiment": sentiment,
                "score": score,
                "keywords": matched_keywords,
            })

        # 집계
        pos = [a for a in classified if a["sentiment"] == "positive"]
        neg = [a for a in classified if a["sentiment"] == "negative"]
        neu = [a for a in classified if a["sentiment"] == "neutral"]

        result.positive_count = len(pos)
        result.negative_count = len(neg)
        result.neutral_count = len(neu)

        total = result.total_count
        result.sentiment_score = round(
            (result.positive_count - result.negative_count) / total, 3
        )
        result.sentiment_label = self._score_to_label(result.sentiment_score)

        result.positive_news = [a["title"] for a in pos[:5]]
        result.negative_news = [a["title"] for a in neg[:5]]

        # 주요 키워드 추출
        all_keywords = []
        for a in classified:
            all_keywords.extend(a.get("keywords", []))
        from collections import Counter
        kw_counts = Counter(all_keywords)
        result.key_keywords = [kw for kw, _ in kw_counts.most_common(8)]

        # 요약 생성
        if self._ai_client:
            result.summary = self._ai_summary(stock, classified)
        else:
            result.summary = self._rule_based_summary(stock, result, classified)

        return result

    def _classify_sentiment(self, text: str) -> tuple[str, float, list]:
        pos_score = 0
        neg_score = 0
        matched = []

        for kw in POSITIVE_KEYWORDS:
            if kw in text:
                pos_score += 1
                matched.append(kw)

        for kw in NEGATIVE_KEYWORDS:
            if kw in text:
                neg_score += 1
                matched.append(kw)

        if pos_score > neg_score:
            return "positive", pos_score / (pos_score + neg_score + 1e-9), matched
        elif neg_score > pos_score:
            return "negative", -neg_score / (pos_score + neg_score + 1e-9), matched
        return "neutral", 0.0, matched

    def _score_to_label(self, score: float) -> str:
        if score >= 0.4:
            return "매우 긍정적"
        if score >= 0.15:
            return "긍정적"
        if score >= -0.15:
            return "중립"
        if score >= -0.4:
            return "부정적"
        return "매우 부정적"

    def _rule_based_summary(
        self, stock: dict, result: NewsAnalysisResult, classified: list
    ) -> str:
        name = stock.get("name", "해당 종목")
        lines = [f"[{name}] 뉴스 감성 분석 결과"]

        if result.positive_count > result.negative_count:
            lines.append(
                f"최근 뉴스는 전반적으로 긍정적입니다 "
                f"(호재 {result.positive_count}건 / 악재 {result.negative_count}건)."
            )
        elif result.negative_count > result.positive_count:
            lines.append(
                f"최근 뉴스는 전반적으로 부정적입니다 "
                f"(악재 {result.negative_count}건 / 호재 {result.positive_count}건)."
            )
        else:
            lines.append(
                f"호재와 악재 뉴스가 혼재되어 있습니다 "
                f"(호재 {result.positive_count}건 / 악재 {result.negative_count}건)."
            )

        if result.key_keywords:
            lines.append(f"주요 키워드: {', '.join(result.key_keywords[:5])}")

        if result.positive_news:
            lines.append(f"대표 호재: {result.positive_news[0]}")
        if result.negative_news:
            lines.append(f"대표 악재: {result.negative_news[0]}")

        return " | ".join(lines)

    def _ai_summary(self, stock: dict, classified: list) -> str:
        name = stock.get("name", "해당 종목")
        titles = [a.get("title", "") for a in classified[:10]]
        news_text = "\n".join(f"- {t}" for t in titles if t)

        prompt = (
            f"다음은 '{name}' 주식의 최근 뉴스 제목 목록입니다:\n\n"
            f"{news_text}\n\n"
            "위 뉴스를 바탕으로:\n"
            "1. 호재 뉴스 2-3줄 요약\n"
            "2. 악재 뉴스 2-3줄 요약\n"
            "3. 전반적인 뉴스 감성 평가 (1-2문장)\n"
            "한국어로 간결하게 작성해주세요."
        )

        try:
            resp = self._ai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.3,
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            return self._rule_based_summary(stock, NewsAnalysisResult(), classified)
