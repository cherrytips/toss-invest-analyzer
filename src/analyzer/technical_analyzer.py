"""
기술적 분석 모듈
- RSI, MACD, 볼린저밴드, 이동평균, 스토캐스틱 등 주요 지표 계산
- 단기/중기/장기 신호 생성
- 라이브러리 의존 없이 pandas/numpy로 직접 구현
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from enum import Enum


class Signal(Enum):
    STRONG_BUY = "강력매수"
    BUY = "매수"
    NEUTRAL = "중립"
    SELL = "매도"
    STRONG_SELL = "강력매도"


@dataclass
class TechnicalResult:
    # 이동평균
    ma5: float = 0.0
    ma20: float = 0.0
    ma60: float = 0.0
    ma120: float = 0.0
    ema12: float = 0.0
    ema26: float = 0.0

    # RSI
    rsi: float = 50.0
    rsi_signal: str = "중립"

    # MACD
    macd: float = 0.0
    macd_signal_line: float = 0.0
    macd_hist: float = 0.0
    macd_cross: str = "중립"

    # 볼린저 밴드
    bb_upper: float = 0.0
    bb_middle: float = 0.0
    bb_lower: float = 0.0
    bb_position: float = 0.5  # 0~1, 0.5 = 중간
    bb_width: float = 0.0
    bb_signal: str = "중립"

    # 스토캐스틱
    stoch_k: float = 50.0
    stoch_d: float = 50.0
    stoch_signal: str = "중립"

    # 거래량
    volume_ratio: float = 1.0  # 현재 거래량 / 20일 평균
    volume_signal: str = "보통"

    # 가격 위치
    current_price: float = 0.0
    price_change_1d: float = 0.0
    price_change_5d: float = 0.0
    price_change_20d: float = 0.0
    distance_from_52w_high: float = 0.0
    distance_from_52w_low: float = 0.0

    # 추세
    trend_short: str = "횡보"  # 상승/하락/횡보
    trend_mid: str = "횡보"

    # 종합 점수 (-100 ~ +100)
    score: int = 0
    signals: list = field(default_factory=list)


class TechnicalAnalyzer:
    def __init__(self, config):
        self.config = config

    def analyze(self, stock: dict, df: pd.DataFrame) -> TechnicalResult:
        result = TechnicalResult()

        if df is None or df.empty or len(df) < 20:
            return result

        closes = df["close"]
        highs = df["high"]
        lows = df["low"]
        volumes = df["volume"]

        result.current_price = float(closes.iloc[-1])

        # ─── 이동평균 ───────────────────────────────────────────
        result.ma5 = self._safe_ma(closes, 5)
        result.ma20 = self._safe_ma(closes, 20)
        result.ma60 = self._safe_ma(closes, 60)
        result.ma120 = self._safe_ma(closes, 120)
        result.ema12 = float(closes.ewm(span=12, adjust=False).mean().iloc[-1])
        result.ema26 = float(closes.ewm(span=26, adjust=False).mean().iloc[-1])

        # ─── RSI ───────────────────────────────────────────────
        result.rsi = self._calc_rsi(closes, 14)
        result.rsi_signal = self._rsi_signal(result.rsi)

        # ─── MACD ───────────────────────────────────────────────
        macd_line, signal_line, hist = self._calc_macd(closes)
        result.macd = macd_line
        result.macd_signal_line = signal_line
        result.macd_hist = hist
        result.macd_cross = self._macd_cross_signal(closes)

        # ─── 볼린저 밴드 ─────────────────────────────────────────
        bb_upper, bb_mid, bb_lower = self._calc_bb(closes, 20, 2)
        result.bb_upper = bb_upper
        result.bb_middle = bb_mid
        result.bb_lower = bb_lower
        price = result.current_price
        band_range = bb_upper - bb_lower
        result.bb_position = (price - bb_lower) / band_range if band_range > 0 else 0.5
        result.bb_width = round(band_range / bb_mid * 100, 2) if bb_mid > 0 else 0
        result.bb_signal = self._bb_signal(result.bb_position)

        # ─── 스토캐스틱 ──────────────────────────────────────────
        k, d = self._calc_stochastic(highs, lows, closes, 14, 3)
        result.stoch_k = k
        result.stoch_d = d
        result.stoch_signal = self._stoch_signal(k, d)

        # ─── 거래량 분석 ──────────────────────────────────────────
        vol_ma20 = float(volumes.rolling(20).mean().iloc[-1])
        result.volume_ratio = float(volumes.iloc[-1]) / vol_ma20 if vol_ma20 > 0 else 1.0
        result.volume_signal = self._volume_signal(result.volume_ratio)

        # ─── 가격 변화율 ──────────────────────────────────────────
        result.price_change_1d = self._price_change(closes, 1)
        result.price_change_5d = self._price_change(closes, 5)
        result.price_change_20d = self._price_change(closes, 20)

        high_52w = float(highs.rolling(min(252, len(highs))).max().iloc[-1])
        low_52w = float(lows.rolling(min(252, len(lows))).min().iloc[-1])
        result.distance_from_52w_high = round((price - high_52w) / high_52w * 100, 2) if high_52w > 0 else 0
        result.distance_from_52w_low = round((price - low_52w) / low_52w * 100, 2) if low_52w > 0 else 0

        # ─── 추세 판단 ───────────────────────────────────────────
        result.trend_short = self._trend(price, result.ma5, result.ma20)
        result.trend_mid = self._trend(price, result.ma20, result.ma60)

        # ─── 종합 점수 산출 ──────────────────────────────────────
        result.score, result.signals = self._calc_composite_score(result)

        return result

    # ── 지표 계산 유틸리티 ──────────────────────────────────────────

    def _safe_ma(self, s: pd.Series, period: int) -> float:
        if len(s) >= period:
            return float(s.rolling(period).mean().iloc[-1])
        return float(s.mean())

    def _calc_rsi(self, closes: pd.Series, period: int = 14) -> float:
        delta = closes.diff()
        gains = delta.where(delta > 0, 0.0)
        losses = -delta.where(delta < 0, 0.0)
        avg_gain = gains.ewm(com=period - 1, adjust=False).mean()
        avg_loss = losses.ewm(com=period - 1, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return round(float(rsi.iloc[-1]), 2) if not rsi.empty else 50.0

    def _calc_macd(self, closes: pd.Series, fast=12, slow=26, signal=9) -> tuple:
        ema_fast = closes.ewm(span=fast, adjust=False).mean()
        ema_slow = closes.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        hist = macd_line - signal_line
        return (
            round(float(macd_line.iloc[-1]), 4),
            round(float(signal_line.iloc[-1]), 4),
            round(float(hist.iloc[-1]), 4),
        )

    def _macd_cross_signal(self, closes: pd.Series) -> str:
        """최근 MACD 크로스 방향 감지"""
        ema12 = closes.ewm(span=12, adjust=False).mean()
        ema26 = closes.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        sig = macd.ewm(span=9, adjust=False).mean()
        diff = macd - sig
        if len(diff) < 2:
            return "중립"
        if diff.iloc[-2] < 0 and diff.iloc[-1] > 0:
            return "골든크로스(매수)"
        if diff.iloc[-2] > 0 and diff.iloc[-1] < 0:
            return "데드크로스(매도)"
        if diff.iloc[-1] > 0:
            return "상승모멘텀"
        return "하락모멘텀"

    def _calc_bb(self, closes: pd.Series, period=20, std_dev=2) -> tuple:
        sma = closes.rolling(period).mean()
        std = closes.rolling(period).std()
        upper = sma + std_dev * std
        lower = sma - std_dev * std
        return (
            round(float(upper.iloc[-1]), 2),
            round(float(sma.iloc[-1]), 2),
            round(float(lower.iloc[-1]), 2),
        )

    def _calc_stochastic(self, highs, lows, closes, k_period=14, d_period=3) -> tuple:
        low_min = lows.rolling(k_period).min()
        high_max = highs.rolling(k_period).max()
        denom = high_max - low_min
        k = ((closes - low_min) / denom.replace(0, np.nan)) * 100
        d = k.rolling(d_period).mean()
        return round(float(k.iloc[-1]), 2), round(float(d.iloc[-1]), 2)

    def _price_change(self, closes: pd.Series, days: int) -> float:
        if len(closes) <= days:
            return 0.0
        old = closes.iloc[-days - 1]
        new = closes.iloc[-1]
        return round((new - old) / old * 100, 2) if old > 0 else 0.0

    # ── 신호 판단 ─────────────────────────────────────────────────

    def _rsi_signal(self, rsi: float) -> str:
        if rsi >= 80:
            return "극도과매수(매도)"
        if rsi >= 70:
            return "과매수(매도주의)"
        if rsi >= 60:
            return "상승강세"
        if rsi >= 40:
            return "중립"
        if rsi >= 30:
            return "하락약세"
        if rsi >= 20:
            return "과매도(매수주의)"
        return "극도과매도(매수)"

    def _bb_signal(self, position: float) -> str:
        if position >= 0.95:
            return "상단돌파(과매수)"
        if position >= 0.8:
            return "상단권(매도주의)"
        if position >= 0.4:
            return "중립"
        if position >= 0.2:
            return "하단권(매수주의)"
        return "하단이탈(과매도)"

    def _stoch_signal(self, k: float, d: float) -> str:
        if k < 20 and d < 20:
            return "과매도(매수)"
        if k > 80 and d > 80:
            return "과매수(매도)"
        if k > d and k < 50:
            return "반등시작"
        if k < d and k > 50:
            return "하락시작"
        return "중립"

    def _volume_signal(self, ratio: float) -> str:
        if ratio >= 3.0:
            return "폭증(급등락 주의)"
        if ratio >= 2.0:
            return "거래량 급증"
        if ratio >= 1.5:
            return "거래량 증가"
        if ratio >= 0.7:
            return "보통"
        return "거래량 부진"

    def _trend(self, price: float, ma_short: float, ma_long: float) -> str:
        if price > ma_short > ma_long:
            return "강한 상승"
        if price > ma_short:
            return "상승"
        if price < ma_short < ma_long:
            return "강한 하락"
        if price < ma_short:
            return "하락"
        return "횡보"

    def _calc_composite_score(self, r: TechnicalResult) -> tuple[int, list]:
        """기술적 지표를 종합해 -100~+100 점수와 신호 목록 반환"""
        score = 0
        signals = []

        # RSI 점수 (-25 ~ +25)
        if r.rsi <= 20:
            score += 25
            signals.append(("RSI", f"{r.rsi:.0f} - 극도 과매도, 강한 매수신호", "buy"))
        elif r.rsi <= 30:
            score += 15
            signals.append(("RSI", f"{r.rsi:.0f} - 과매도 구간, 매수 고려", "buy"))
        elif r.rsi <= 45:
            score += 5
        elif r.rsi <= 55:
            pass  # 중립
        elif r.rsi <= 70:
            score -= 5
        elif r.rsi <= 80:
            score -= 15
            signals.append(("RSI", f"{r.rsi:.0f} - 과매수 구간, 매도 고려", "sell"))
        else:
            score -= 25
            signals.append(("RSI", f"{r.rsi:.0f} - 극도 과매수, 강한 매도신호", "sell"))

        # MACD 점수 (-20 ~ +20)
        if "골든크로스" in r.macd_cross:
            score += 20
            signals.append(("MACD", "골든크로스 발생 - 강한 매수신호", "buy"))
        elif "데드크로스" in r.macd_cross:
            score -= 20
            signals.append(("MACD", "데드크로스 발생 - 강한 매도신호", "sell"))
        elif "상승" in r.macd_cross:
            score += 10
        elif "하락" in r.macd_cross:
            score -= 10

        # 볼린저밴드 점수 (-15 ~ +15)
        if r.bb_position >= 0.95:
            score -= 15
            signals.append(("볼린저밴드", "상단 돌파 - 과매수 영역", "sell"))
        elif r.bb_position >= 0.8:
            score -= 8
        elif r.bb_position <= 0.05:
            score += 15
            signals.append(("볼린저밴드", "하단 이탈 - 과매도 영역, 반등 가능성", "buy"))
        elif r.bb_position <= 0.2:
            score += 8

        # 이동평균 배열 점수 (-20 ~ +20)
        price = r.current_price
        if price > 0 and r.ma5 > 0 and r.ma20 > 0:
            if price > r.ma5 > r.ma20:
                score += 15
                signals.append(("이동평균", f"정배열 형성 (가격 > MA5 > MA20)", "buy"))
            elif price < r.ma5 < r.ma20:
                score -= 15
                signals.append(("이동평균", "역배열 형성 (가격 < MA5 < MA20)", "sell"))
            elif price > r.ma20:
                score += 8
            elif price < r.ma20:
                score -= 8

        # 스토캐스틱 점수 (-10 ~ +10)
        if "과매도" in r.stoch_signal:
            score += 10
            signals.append(("스토캐스틱", f"K={r.stoch_k:.0f} - 과매도", "buy"))
        elif "과매수" in r.stoch_signal:
            score -= 10
            signals.append(("스토캐스틱", f"K={r.stoch_k:.0f} - 과매수", "sell"))
        elif "반등" in r.stoch_signal:
            score += 5

        # 거래량 점수 (-10 ~ +10)
        if r.volume_ratio >= 2.0 and r.price_change_1d > 0:
            score += 10
            signals.append(("거래량", f"거래량 급증 + 상승 ({r.volume_ratio:.1f}배) - 강한 매수세", "buy"))
        elif r.volume_ratio >= 2.0 and r.price_change_1d < 0:
            score -= 10
            signals.append(("거래량", f"거래량 급증 + 하락 ({r.volume_ratio:.1f}배) - 강한 매도세", "sell"))

        score = max(-100, min(100, score))
        return score, signals
