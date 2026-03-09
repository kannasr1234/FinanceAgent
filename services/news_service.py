import requests
import logging
from typing import List, Dict, Optional
from datetime import datetime
from .cache_service import CacheService

logger = logging.getLogger(__name__)

class NewsService:
    def __init__(self, cache_service: CacheService):
        self.cache = cache_service
        self.base_url = "https://newsapi.org/v2/everything"
    
    async def fetch_news_headlines(self, ticker: str, max_headlines: int = 3) -> List[Dict]:
        cache_key = f"news_{ticker}"
        cached_news = self.cache.get(cache_key)
        if cached_news:
            return cached_news
        headlines = []
        try:
            headlines = await self._fetch_from_newsapi(ticker, max_headlines)
        except Exception as e:
            logger.debug(f"NewsAPI fetch failed for {ticker}: {e}")
            headlines = await self._fetch_fallback_news(ticker, max_headlines)
        if headlines:
            self.cache.set(cache_key, headlines)
        return headlines
    
    async def _fetch_from_newsapi(self, ticker: str, max_headlines: int) -> List[Dict]:
        api_key = "demo"
        try:
            params = {"q": ticker, "sortBy": "publishedAt", "apiKey": api_key, "pageSize": max_headlines}
            response = requests.get(self.base_url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                headlines = []
                for article in data.get("articles", [])[:max_headlines]:
                    headlines.append({"title": article.get("title", "N/A"), "source": article.get("source", {}).get("name", "Unknown"), "url": article.get("url", "#"), "published_at": article.get("publishedAt", "N/A")})
                return headlines
            else:
                return await self._fetch_fallback_news(ticker, max_headlines)
        except Exception as e:
            logger.debug(f"Error fetching from NewsAPI: {e}")
            return await self._fetch_fallback_news(ticker, max_headlines)
    
    async def _fetch_fallback_news(self, ticker: str, max_headlines: int) -> List[Dict]:
        try:
            return []
        except Exception as e:
            logger.error(f"Fallback news fetch failed for {ticker}: {e}")
            return []
    
    def get_news_summary(self, headlines: List[Dict]) -> str:
        if not headlines:
            return "No recent news available."
        titles = [h.get("title", "") for h in headlines[:2]]
        return " | ".join(titles) if titles else "No recent news available."