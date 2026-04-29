"""
주식 데이터 수집 모듈
- yfinance를 통한 OHLCV, 펀더멘털 데이터 수집
- 한국주식 (KOSPI/KOSDAQ) 및 미국주식 지원
- 데이터 캐싱으로 반복 요청 최소화
"""

import json
import time
from pathlib import Path
from datetime import datetime, timedelta

import yfinance as yf
import pandas as pd
import numpy as np
from rich.console import Console

console = Console()

# 코스피/코스닥 주요 종목 코드 (완전한 목록은 아님, 조회 시 두 거래소 모두 시도)
KOSPI_CODES = {
    "005930", "000660", "035420", "005380", "051910",
    "006400", "028260", "012330", "066570", "003550",
    "017670", "034730", "018260", "096770", "086790",
    "032830", "011200", "009150", "000270", "010950",
}


class StockData:
    def __init__(self, config):
        self.config = config
        self.cache_dir = config.cache_dir / "stock_data"
        self.cache_dir.mkdir(exist_ok=True)

    def get_ohlcv(self, stock: dict) -> pd.DataFrame:
        """OHLCV 데이터 반환 (종가, 거래량 포함)"""
        ticker = self._resolve_yf_ticker(stock)
        if not ticker:
            return pd.DataFrame()

        cache_file = self.cache_dir / f"{ticker.replace('.', '_')}_ohlcv.json"

        # 캐시 유효성 확인 (당일 캐시)
        if cache_file.exists():
            mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
            if datetime.now() - mtime < timedelta(hours=4):
                try:
                    data = json.loads(cache_file.read_text(encoding="utf-8"))
                    df = pd.DataFrame(data)
                    df.index = pd.to_datetime(df.index)
                    return df
                except Exception:
                    pass

        try:
            period = f"{self.config.analysis_days}d"
            yf_ticker = yf.Ticker(ticker)
            df = yf_ticker.history(period=period, auto_adjust=True)

            if df.empty:
                return pd.DataFrame()

            df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
            df.columns = ["open", "high", "low", "close", "volume"]
            df.index = df.index.tz_localize(None)

            # 캐시 저장
            cache_data = df.copy()
            cache_data.index = cache_data.index.astype(str)
            cache_file.write_text(
                json.dumps(cache_data.to_dict(), ensure_ascii=False),
                encoding="utf-8",
            )

            # 종목에 ticker 저장
            stock["yf_ticker"] = ticker

            return df

        except Exception as e:
            console.print(f"[dim]OHLCV 수집 오류 ({ticker}): {e}[/dim]")
            return pd.DataFrame()

    def get_fundamentals(self, stock: dict) -> dict:
        """PER, PBR, ROE, 시가총액 등 펀더멘털 정보 반환"""
        ticker = self._resolve_yf_ticker(stock)
        if not ticker:
            return {}

        cache_file = self.cache_dir / f"{ticker.replace('.', '_')}_info.json"

        if cache_file.exists():
            mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
            if datetime.now() - mtime < timedelta(hours=12):
                try:
                    return json.loads(cache_file.read_text(encoding="utf-8"))
                except Exception:
                    pass

        try:
            yf_ticker = yf.Ticker(ticker)
            info = yf_ticker.info

            fundamentals = {
                "market_cap": self._fmt_num(info.get("marketCap")),
                "market_cap_raw": info.get("marketCap"),
                "per": round(info.get("trailingPE", 0) or 0, 2),
                "forward_per": round(info.get("forwardPE", 0) or 0, 2),
                "pbr": round(info.get("priceToBook", 0) or 0, 2),
                "psr": round(info.get("priceToSalesTrailing12Months", 0) or 0, 2),
                "eps": info.get("trailingEps"),
                "roe": round((info.get("returnOnEquity", 0) or 0) * 100, 2),
                "roa": round((info.get("returnOnAssets", 0) or 0) * 100, 2),
                "revenue_growth": round((info.get("revenueGrowth", 0) or 0) * 100, 2),
                "earnings_growth": round((info.get("earningsGrowth", 0) or 0) * 100, 2),
                "debt_to_equity": round(info.get("debtToEquity", 0) or 0, 2),
                "current_ratio": round(info.get("currentRatio", 0) or 0, 2),
                "dividend_yield": round((info.get("dividendYield", 0) or 0) * 100, 2),
                "beta": round(info.get("beta", 1.0) or 1.0, 2),
                "52w_high": info.get("fiftyTwoWeekHigh"),
                "52w_low": info.get("fiftyTwoWeekLow"),
                "avg_volume": info.get("averageVolume"),
                "sector": info.get("sector", ""),
                "industry": info.get("industry", ""),
                "country": info.get("country", ""),
                "currency": info.get("currency", "KRW"),
            }

            cache_file.write_text(
                json.dumps(fundamentals, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            return fundamentals

        except Exception as e:
            console.print(f"[dim]펀더멘털 수집 오류 ({ticker}): {e}[/dim]")
            return {}

    def _resolve_yf_ticker(self, stock: dict) -> str | None:
        """종목 코드를 yfinance 티커로 변환"""
        # 이미 결정된 티커가 있으면 사용
        if stock.get("yf_ticker"):
            return stock["yf_ticker"]

        code = stock.get("code", "")
        market = stock.get("market", "UNKNOWN")

        if not code:
            return None

        if market == "US":
            return code.upper()

        # 한국 주식: KOSPI (.KS) / KOSDAQ (.KQ) 판별
        if len(code) == 6 and code.isdigit():
            # KOSPI 우선 시도
            if code in KOSPI_CODES:
                return f"{code}.KS"
            # 둘 다 시도해서 데이터 있는 쪽 사용
            for suffix in [".KS", ".KQ"]:
                ticker = f"{code}{suffix}"
                try:
                    df = yf.Ticker(ticker).history(period="5d", auto_adjust=True)
                    if not df.empty:
                        stock["yf_ticker"] = ticker
                        return ticker
                except Exception:
                    pass
            return f"{code}.KS"  # 기본값

        return code

    @staticmethod
    def _fmt_num(n) -> str:
        """숫자를 읽기 쉬운 형태로 변환"""
        if n is None:
            return "N/A"
        if n >= 1_000_000_000_000:
            return f"{n / 1_000_000_000_000:.1f}조"
        if n >= 100_000_000:
            return f"{n / 100_000_000:.0f}억"
        if n >= 10_000:
            return f"{n / 10_000:.0f}만"
        return f"{n:,}"
