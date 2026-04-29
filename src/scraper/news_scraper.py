"""
뉴스 스크래퍼
- 네이버 금융에서 종목별 뉴스 수집 (한국주식)
- Yahoo Finance RSS에서 뉴스 수집 (미국주식)
"""

import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from rich.console import Console

console = Console()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class NewsScraper:
    def __init__(self, config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def get_news(self, stock: dict) -> list[dict]:
        """종목의 최신 뉴스 목록 반환"""
        market = stock.get("market", "UNKNOWN")
        code = stock.get("code", "")

        if market == "US":
            return self._get_us_news(code, stock.get("name", ""))
        else:
            return self._get_kr_news(code, stock.get("name", ""))

    def _get_kr_news(self, code: str, name: str) -> list[dict]:
        """네이버 금융에서 한국 주식 뉴스 수집"""
        articles = []
        max_count = self.config.news_count

        try:
            url = f"https://finance.naver.com/item/news_news.naver?code={code}&page=1"
            resp = self.session.get(url, timeout=10)
            resp.encoding = "euc-kr"

            if resp.status_code != 200:
                return self._get_naver_search_news(name, max_count)

            soup = BeautifulSoup(resp.text, "lxml")
            rows = soup.select("table.type5 tr, .type5 tr")

            for row in rows:
                title_el = row.select_one("td.title a, .title a")
                date_el = row.select_one("td.date, .date")
                source_el = row.select_one("td.info, .info")

                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                if not title:
                    continue

                href = title_el.get("href", "")
                link = f"https://finance.naver.com{href}" if href.startswith("/") else href
                date_str = date_el.get_text(strip=True) if date_el else ""
                source = source_el.get_text(strip=True) if source_el else "네이버금융"

                articles.append({
                    "title": title,
                    "link": link,
                    "date": date_str,
                    "source": source,
                    "content": self._fetch_article_summary(link),
                })

                if len(articles) >= max_count:
                    break

            if not articles:
                return self._get_naver_search_news(name, max_count)

        except Exception as e:
            console.print(f"[dim]뉴스 수집 오류 ({code}): {e}[/dim]")
            return self._get_naver_search_news(name, max_count)

        return articles

    def _get_naver_search_news(self, name: str, count: int) -> list[dict]:
        """네이버 뉴스 검색으로 폴백"""
        articles = []
        try:
            url = "https://search.naver.com/search.naver"
            params = {"where": "news", "query": name, "sort": "1"}
            resp = self.session.get(url, params=params, timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")

            news_items = soup.select(".news_area, .list_news .bx")
            for item in news_items[:count]:
                title_el = item.select_one(".news_tit, a.title_link")
                date_el = item.select_one(".info_group span.info, .info .date")
                source_el = item.select_one(".info_group a, .press")

                if not title_el:
                    continue

                articles.append({
                    "title": title_el.get_text(strip=True),
                    "link": title_el.get("href", ""),
                    "date": date_el.get_text(strip=True) if date_el else "",
                    "source": source_el.get_text(strip=True) if source_el else "네이버",
                    "content": "",
                })
        except Exception:
            pass
        return articles

    def _get_us_news(self, ticker: str, name: str) -> list[dict]:
        """Yahoo Finance RSS에서 미국 주식 뉴스 수집"""
        articles = []
        try:
            rss_url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
            resp = self.session.get(rss_url, timeout=10)
            soup = BeautifulSoup(resp.content, "xml")

            items = soup.find_all("item")
            for item in items[: self.config.news_count]:
                title = item.find("title")
                link = item.find("link")
                pub_date = item.find("pubDate")
                source_tag = item.find("source")
                desc = item.find("description")

                articles.append({
                    "title": title.get_text(strip=True) if title else "",
                    "link": link.get_text(strip=True) if link else "",
                    "date": pub_date.get_text(strip=True) if pub_date else "",
                    "source": source_tag.get_text(strip=True) if source_tag else "Yahoo Finance",
                    "content": desc.get_text(strip=True) if desc else "",
                })

        except Exception as e:
            console.print(f"[dim]미국 주식 뉴스 수집 오류 ({ticker}): {e}[/dim]")

        return articles

    def _fetch_article_summary(self, url: str, max_chars: int = 300) -> str:
        """기사 본문 일부 수집 (요약용)"""
        if not url or "finance.naver.com" not in url:
            return ""
        try:
            time.sleep(0.3)  # 과도한 요청 방지
            resp = self.session.get(url, timeout=8)
            resp.encoding = "euc-kr"
            soup = BeautifulSoup(resp.text, "lxml")

            # 기사 본문 셀렉터
            content_el = soup.select_one(
                "#newsct_article, .article_body, #articeBody, .news_article"
            )
            if content_el:
                text = content_el.get_text(separator=" ", strip=True)
                return text[:max_chars] + ("..." if len(text) > max_chars else "")
        except Exception:
            pass
        return ""
