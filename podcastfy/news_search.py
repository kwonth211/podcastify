"""
News Search Module

This module provides functionality to search for the latest news articles
using multiple methods:
1. Gemini's google_search_retrieval (recommended - most up-to-date)
2. Google Custom Search API (fallback)

Gemini's google_search_retrieval is preferred as it provides real-time
search results directly from Google's search infrastructure.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class NewsArticle:
    """Represents a news article from search results."""
    title: str
    url: str
    snippet: str
    published_date: Optional[str] = None
    source: Optional[str] = None


class GeminiNewsSearch:
    """
    Real-time news search using Gemini's google_search tool.
    
    This is the recommended method as it provides the most up-to-date
    search results directly from Google's search infrastructure.
    
    Requires:
    - GEMINI_API_KEY: Google Gemini API Key
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Gemini News Search.
        
        Args:
            api_key: Gemini API Key. If not provided, reads from GEMINI_API_KEY env var.
        """
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        
        if not self.api_key:
            raise ValueError("Gemini API Key is required. Set GEMINI_API_KEY environment variable.")
        
        from google import genai
        self.client = genai.Client(api_key=self.api_key)
    
    def search_news(
        self,
        query: str,
        language: str = "ko",
        num_results: int = 5
    ) -> Tuple[str, List[Dict[str, str]]]:
        """
        Search for the latest news using Gemini's google_search tool.
        
        This method provides real-time search results, making it ideal
        for getting the most up-to-date news.
        
        Args:
            query: Search query (e.g., "정치 뉴스", "AI 관련 뉴스")
            language: Language code (ko, en, ja, zh)
            num_results: Target number of results (approximate)
        
        Returns:
            Tuple of (generated content string, list of source URLs)
        """
        try:
            from google.genai import types
            
            # Build language-specific prompt
            lang_prompts = {
                "ko": f"""오늘의 최신 {query} 뉴스를 검색해서 자세히 요약해주세요.
                
요구사항:
- 가장 최근 뉴스 {num_results}개 정도를 찾아주세요
- 각 뉴스의 핵심 내용을 상세히 설명해주세요
- 출처(언론사)와 날짜를 가능하면 포함해주세요
- 뉴스의 맥락과 배경도 설명해주세요""",
                
                "en": f"""Search for the latest {query} news and summarize in detail.

Requirements:
- Find approximately {num_results} most recent news articles
- Explain the key points of each news item in detail
- Include sources and dates when possible
- Provide context and background""",
                
                "ja": f"""今日の最新{query}ニュースを検索して詳しく要約してください。

要件:
- 最新のニュース約{num_results}件を探してください
- 各ニュースの要点を詳しく説明してください
- 出典と日付を可能な限り含めてください""",
                
                "zh": f"""搜索最新的{query}新闻并详细总结。

要求:
- 找到大约{num_results}条最新新闻
- 详细解释每条新闻的要点
- 尽可能包括来源和日期"""
            }
            
            prompt = lang_prompts.get(language, lang_prompts["en"])
            
            logger.info(f"Searching news with Gemini: {query}")
            
            # Use google_search tool for real-time search
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                )
            )
            
            # Extract content
            content = response.text
            
            # Try to extract grounding metadata (sources)
            sources = []
            try:
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                        grounding = candidate.grounding_metadata
                        if hasattr(grounding, 'grounding_chunks') and grounding.grounding_chunks:
                            for chunk in grounding.grounding_chunks:
                                if hasattr(chunk, 'web'):
                                    sources.append({
                                        "title": getattr(chunk.web, 'title', ''),
                                        "url": getattr(chunk.web, 'uri', '')
                                    })
            except Exception as e:
                logger.warning(f"Could not extract grounding sources: {e}")
            
            logger.info(f"Found {len(sources)} sources from Gemini search")
            return content, sources
            
        except Exception as e:
            logger.error(f"Error searching news with Gemini: {str(e)}")
            raise
    
    def get_news_content(
        self,
        query: str,
        language: str = "ko",
        num_results: int = 5
    ) -> str:
        """
        Get news content as a single string for podcast generation.
        
        Args:
            query: Search query
            language: Language code
            num_results: Target number of results
        
        Returns:
            Combined news content string
        """
        content, sources = self.search_news(query, language, num_results)
        return content


class GoogleNewsSearch:
    """
    Google Custom Search API wrapper for searching news articles.
    
    Note: This is a fallback option. Use GeminiNewsSearch for more
    up-to-date results.
    
    Requires:
    - GOOGLE_API_KEY: Google API Key
    - GOOGLE_CSE_ID: Google Custom Search Engine ID
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        cse_id: Optional[str] = None
    ):
        """
        Initialize the Google News Search client.
        
        Args:
            api_key: Google API Key. If not provided, reads from GOOGLE_API_KEY env var.
            cse_id: Custom Search Engine ID. If not provided, reads from GOOGLE_CSE_ID env var.
        """
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        self.cse_id = cse_id or os.environ.get("GOOGLE_CSE_ID")
        
        if not self.api_key:
            raise ValueError("Google API Key is required. Set GOOGLE_API_KEY environment variable.")
        if not self.cse_id:
            raise ValueError("Google CSE ID is required. Set GOOGLE_CSE_ID environment variable.")
        
        from googleapiclient.discovery import build
        self.service = build("customsearch", "v1", developerKey=self.api_key)
    
    def search_news(
        self,
        query: str,
        language: str = "ko",
        num_results: int = 5,
        date_restrict: str = "d1",
        sort_by_date: bool = True
    ) -> List[NewsArticle]:
        """
        Search for news articles using Google Custom Search API.
        
        Note: Results may be delayed by Google's indexing time.
        
        Args:
            query: Search query (e.g., "정치 뉴스", "AI 관련 뉴스")
            language: Language code (ko, en, ja, zh)
            num_results: Number of results to return (max 10 per request)
            date_restrict: Date restriction (d1=1day, d7=7days, w1=1week, m1=1month)
            sort_by_date: Whether to sort results by date (most recent first)
        
        Returns:
            List of NewsArticle objects containing news information
        """
        try:
            # Build the search query with news context
            search_query = f"{query} 뉴스" if language == "ko" else f"{query} news"
            
            # Build search parameters
            search_params = {
                "q": search_query,
                "cx": self.cse_id,
                "num": min(num_results, 10),
                "dateRestrict": date_restrict,
                "lr": f"lang_{language}",
            }
            
            if sort_by_date:
                search_params["sort"] = "date"
            
            logger.info(f"Searching news with Custom Search: {search_query}")
            
            result = self.service.cse().list(**search_params).execute()
            
            articles = []
            items = result.get("items", [])
            
            for item in items:
                article = NewsArticle(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    published_date=item.get("pagemap", {}).get("metatags", [{}])[0].get("article:published_time"),
                    source=item.get("displayLink", "")
                )
                articles.append(article)
            
            logger.info(f"Found {len(articles)} news articles")
            return articles
            
        except Exception as e:
            logger.error(f"Error searching news: {str(e)}")
            raise
    
    def get_news_urls(
        self,
        query: str,
        language: str = "ko",
        num_results: int = 5,
        date_restrict: str = "d1"
    ) -> List[str]:
        """
        Get a list of news URLs for the given query.
        
        Args:
            query: Search query
            language: Language code
            num_results: Number of results to return
            date_restrict: Date restriction
        
        Returns:
            List of news article URLs
        """
        articles = self.search_news(
            query=query,
            language=language,
            num_results=num_results,
            date_restrict=date_restrict
        )
        return [article.url for article in articles]


# Query templates for common news categories
NEWS_CATEGORIES = {
    "politics": {
        "ko": "정치",
        "en": "politics",
        "ja": "政治",
        "zh": "政治"
    },
    "economy": {
        "ko": "경제",
        "en": "economy",
        "ja": "経済",
        "zh": "经济"
    },
    "technology": {
        "ko": "기술 IT",
        "en": "technology",
        "ja": "テクノロジー",
        "zh": "科技"
    },
    "ai": {
        "ko": "인공지능 AI",
        "en": "artificial intelligence AI",
        "ja": "人工知能 AI",
        "zh": "人工智能 AI"
    },
    "sports": {
        "ko": "스포츠",
        "en": "sports",
        "ja": "スポーツ",
        "zh": "体育"
    },
    "entertainment": {
        "ko": "연예",
        "en": "entertainment",
        "ja": "エンターテインメント",
        "zh": "娱乐"
    },
    "world": {
        "ko": "국제 세계",
        "en": "world international",
        "ja": "国際",
        "zh": "国际"
    },
    "china": {
        "ko": "중국",
        "en": "China",
        "ja": "中国",
        "zh": "中国"
    }
}


def get_category_query(category: str, language: str = "ko") -> str:
    """
    Get the localized query string for a news category.
    
    Args:
        category: Category key (politics, economy, technology, etc.)
        language: Language code
    
    Returns:
        Localized query string for the category
    """
    if category.lower() in NEWS_CATEGORIES:
        return NEWS_CATEGORIES[category.lower()].get(language, NEWS_CATEGORIES[category.lower()]["en"])
    return category


def get_news_searcher(method: str = "gemini") -> Any:
    """
    Factory function to get the appropriate news searcher.
    
    Args:
        method: Search method ("gemini" or "custom_search")
    
    Returns:
        News searcher instance
    """
    if method == "gemini":
        return GeminiNewsSearch()
    elif method == "custom_search":
        return GoogleNewsSearch()
    else:
        raise ValueError(f"Unknown search method: {method}")


if __name__ == "__main__":
    # Test the module
    logging.basicConfig(level=logging.INFO)
    
    print("Testing Gemini News Search (Real-time):")
    print("=" * 50)
    
    try:
        searcher = GeminiNewsSearch()
        content, sources = searcher.search_news("경제", language="ko", num_results=5)
        
        print("\n📰 News Content:")
        print(content)
        
        if sources:
            print("\n🔗 Sources:")
            for source in sources:
                print(f"  - {source.get('title', 'Unknown')}: {source.get('url', '')}")
        else:
            print("\n(출처 정보는 응답 텍스트에 포함되어 있습니다)")
            
    except Exception as e:
        print(f"Error: {e}")
