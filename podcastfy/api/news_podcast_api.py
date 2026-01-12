"""
News Podcast API Server

This module provides a REST API for generating podcasts from the latest news articles.
Users can request podcasts based on:
- Custom search prompts (e.g., "정치 뉴스", "AI 관련 뉴스")
- Language preferences
- News recency filters

The API uses Gemini's google_search_retrieval for real-time news search,
then generates a podcast summarizing them.
"""

import os
import shutil
import uuid
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

# .env 파일 자동 로드 (로컬 실행 시)
from dotenv import load_dotenv
import pathlib

# 여러 경로에서 .env 파일 찾기
possible_env_paths = [
    pathlib.Path.cwd() / '.env',
    pathlib.Path(__file__).parent.parent.parent / '.env',
    pathlib.Path('/app/.env'),
]

env_loaded = False
for env_path in possible_env_paths:
    if env_path.exists():
        load_dotenv(env_path)
        env_loaded = True
        break

# Docker에서는 env_file로 이미 주입되므로 경고 불필요

from fastapi import FastAPI, HTTPException, Depends, Security, Request
from fastapi.security import APIKeyHeader
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# API Key 설정
API_KEY = os.getenv("API_KEY", "")
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Security(API_KEY_HEADER)):
    """API 키 검증"""
    if not API_KEY:
        # API_KEY가 설정되지 않으면 인증 비활성화
        return True
    if api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "API key required"}
        )
    return True

from ..news_search import GeminiNewsSearch, GoogleNewsSearch, NEWS_CATEGORIES
from ..client import generate_podcast, get_last_gemini_sources, clear_gemini_sources
from ..utils.config_conversation import load_conversation_config
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


# ============================================================================
# Pydantic Models
# ============================================================================

class Language(str, Enum):
    """Supported languages for podcast generation."""
    KOREAN = "ko"
    ENGLISH = "en"
    JAPANESE = "ja"
    CHINESE = "zh"


class SearchMethod(str, Enum):
    """Available search methods."""
    GEMINI = "gemini"  # Real-time search (recommended)
    CUSTOM_SEARCH = "custom_search"  # Google Custom Search API (fallback)


class DateRestrict(str, Enum):
    """Date restriction for news search (only for custom_search method)."""
    LAST_1_DAY = "d1"
    LAST_3_DAYS = "d3"
    LAST_7_DAYS = "d7"
    LAST_1_WEEK = "w1"
    LAST_1_MONTH = "m1"


class TTSModel(str, Enum):
    """Available TTS models."""
    OPENAI = "openai"
    ELEVENLABS = "elevenlabs"
    EDGE = "edge"
    GEMINI = "gemini"


class NewsPodcastRequest(BaseModel):
    """Request model for news podcast generation."""
    prompt: str = Field(
        ...,
        description="검색 프롬프트 (예: '정치 뉴스', 'AI 관련 뉴스', '중국에서 일어나는 뉴스')",
        examples=["정치뉴스를 요약해줘", "AI 관련 뉴스", "경제 뉴스"]
    )
    language: Language = Field(
        default=Language.KOREAN,
        description="팟캐스트 생성 언어 (ko, en, ja, zh)"
    )
    search_method: SearchMethod = Field(
        default=SearchMethod.GEMINI,
        description="검색 방법 (gemini: 실시간 검색 권장, custom_search: Google CSE)"
    )
    num_articles: int = Field(
        default=5,
        ge=1,
        le=10,
        description="검색할 뉴스 기사 수 (1-10)"
    )
    date_restrict: DateRestrict = Field(
        default=DateRestrict.LAST_1_DAY,
        description="뉴스 검색 기간 제한 (custom_search 방법에서만 사용)"
    )
    tts_model: TTSModel = Field(
        default=TTSModel.GEMINI,
        description="TTS 모델 선택"
    )
    podcast_name: Optional[str] = Field(
        default=None,
        description="팟캐스트 이름 (선택사항)"
    )
    user_instructions: Optional[str] = Field(
        default=None,
        description="추가 지시사항 (선택사항)"
    )
    longform: bool = Field(
        default=False,
        description="긴 형식의 팟캐스트 생성 여부"
    )


class NewsPodcastResponse(BaseModel):
    """Response model for news podcast generation."""
    success: bool
    audio_url: Optional[str] = None
    transcript_url: Optional[str] = None
    news_sources: List[Dict[str, Any]] = Field(default_factory=list)
    message: str = ""
    request_id: str
    search_method: str = ""


class NewsSearchResponse(BaseModel):
    """Response model for news search preview."""
    success: bool
    content: str = ""
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    query: str
    search_method: str


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    timestamp: str
    version: str = "1.0.0"


class CategoryListResponse(BaseModel):
    """Response model for available categories."""
    categories: Dict[str, Dict[str, str]]


# ============================================================================
# FastAPI Application
# ============================================================================

# 프로덕션 환경에서는 docs 비활성화
ENABLE_DOCS = os.getenv("ENABLE_DOCS", "false").lower() == "true"

app = FastAPI(
    title="News Podcast API",
    description="""
실시간 뉴스를 검색하고 팟캐스트로 변환하는 API

## 검색 방법
- **gemini** (권장): Gemini의 google_search_retrieval을 사용한 실시간 검색
- **custom_search**: Google Custom Search API (인덱싱 지연 있음)

## 사용 예시
- 정치뉴스를 요약해줘
- AI 관련 뉴스
- 경제 뉴스
- 중국에서 일어나는 뉴스
""",
    version="1.1.0",
    docs_url="/docs" if ENABLE_DOCS else None,
    redoc_url="/redoc" if ENABLE_DOCS else None,
    openapi_url="/openapi.json" if ENABLE_DOCS else None
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base directory for the project
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

# Temporary directories for generated files
TEMP_AUDIO_DIR = os.path.join(BASE_DIR, "data", "audio", "tmp")
TEMP_TRANSCRIPT_DIR = os.path.join(BASE_DIR, "data", "transcripts")
os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)
os.makedirs(TEMP_TRANSCRIPT_DIR, exist_ok=True)


# ============================================================================
# Helper Functions
# ============================================================================

def get_language_name(lang_code: str) -> str:
    """Convert language code to full name."""
    lang_map = {
        "ko": "Korean",
        "en": "English",
        "ja": "Japanese",
        "zh": "Chinese"
    }
    return lang_map.get(lang_code, "English")


def get_language_config(lang_code: str) -> dict:
    """Get language-specific podcast configuration."""
    # CRITICAL instruction to prevent scratchpad/planning output
    strict_format = """

=== CRITICAL OUTPUT FORMAT RULES ===
1. Your response MUST start IMMEDIATELY with <Person1> tag
2. Output ONLY the dialogue - NO planning, NO scratchpad, NO analysis, NO notes
3. Do NOT write phrases like "(scratchpad)", "Strategy:", "Analysis:", "Key Points:"
4. Do NOT include numbered outlines or topic breakdowns
5. Every line must be inside <Person1> or <Person2> tags
6. Start the dialogue directly without any preamble

WRONG FORMAT (DO NOT DO THIS):
(scratchpad) Planning the conversation...
1. Topic analysis
2. Key points
<Person1>Hello</Person1>

CORRECT FORMAT (DO THIS):
<Person1>Hello and welcome!</Person1>
<Person2>Thanks for having me!</Person2>
"""
    
    configs = {
        "ko": {
            "podcast_name": "뉴스 요약",
            "podcast_tagline": "오늘의 주요 뉴스를 요약해드립니다",
            "user_instructions": "이 팟캐스트는 뉴스를 요약하고 분석하는 프로그램입니다." + strict_format,
            "ending_message": "오늘의 뉴스 요약을 마칩니다. 감사합니다!",
            "topic_suffix": "최신 뉴스",
            "tts_voices": {
                "question": "ko-KR-Chirp3-HD-Charon",
                "answer": "ko-KR-Chirp3-HD-Aoede"
            }
        },
        "en": {
            "podcast_name": "News Summary",
            "podcast_tagline": "Your daily news briefing",
            "user_instructions": "This podcast summarizes and analyzes the latest news." + strict_format,
            "ending_message": "That's all for today's news summary. Thanks for listening!",
            "topic_suffix": "latest news",
            "tts_voices": {
                "question": "en-US-Chirp3-HD-Charon",
                "answer": "en-US-Chirp3-HD-Aoede"
            }
        },
        "ja": {
            "podcast_name": "ニュースまとめ",
            "podcast_tagline": "今日の主要ニュースをお届けします",
            "user_instructions": "このポッドキャストはニュースを要約・分析する番組です。" + strict_format,
            "ending_message": "本日のニュースまとめは以上です。ご視聴ありがとうございました！",
            "topic_suffix": "最新ニュース",
            "tts_voices": {
                "question": "ja-JP-Chirp3-HD-Charon",
                "answer": "ja-JP-Chirp3-HD-Aoede"
            }
        },
        "zh": {
            "podcast_name": "新闻摘要",
            "podcast_tagline": "为您播报今日要闻",
            "user_instructions": "本播客为您总结分析最新新闻。" + strict_format,
            "ending_message": "以上就是今天的新闻摘要，感谢收听！",
            "topic_suffix": "最新新闻",
            "tts_voices": {
                "question": "cmn-CN-Chirp3-HD-Charon",
                "answer": "cmn-CN-Chirp3-HD-Aoede"
            }
        }
    }
    return configs.get(lang_code, configs["en"])


def extract_search_query(prompt: str) -> str:
    """
    Extract the main search query from user prompt.
    
    Examples:
    - "정치뉴스를 요약해줘" -> "정치"
    - "AI 관련 뉴스를 요약해줘" -> "AI"
    - "중국에서 일어나는 뉴스" -> "중국"
    """
    suffixes_to_remove = [
        "뉴스를 요약해줘", "뉴스 요약해줘", "요약해줘", "요약해",
        "뉴스를 알려줘", "뉴스 알려줘", "알려줘",
        "에서 일어나는 뉴스", "관련 뉴스", "뉴스"
    ]
    
    query = prompt.strip()
    for suffix in suffixes_to_remove:
        if query.endswith(suffix):
            query = query[:-len(suffix)].strip()
            break
    
    return query if query else prompt


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint with API information."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat()
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat()
    )


@app.get("/categories", response_model=CategoryListResponse)
async def get_categories(api_key: bool = Depends(verify_api_key)):
    """Get available news categories with localized names."""
    return CategoryListResponse(categories=NEWS_CATEGORIES)


@app.post("/search/preview", response_model=NewsSearchResponse)
async def preview_news_search(request: NewsPodcastRequest, api_key: bool = Depends(verify_api_key)):
    """
    Preview news search results without generating a podcast.
    
    Use this endpoint to see what news content would be used for podcast generation.
    
    - **gemini** method: Returns summarized news content with sources (real-time)
    - **custom_search** method: Returns list of article URLs (may be delayed)
    """
    try:
        search_query = extract_search_query(request.prompt)
        
        if request.search_method == SearchMethod.GEMINI:
            # Use Gemini's real-time search
            searcher = GeminiNewsSearch()
            content, sources = searcher.search_news(
                query=search_query,
                language=request.language.value,
                num_results=request.num_articles
            )
            
            return NewsSearchResponse(
                success=True,
                content=content,
                sources=sources,
                query=search_query,
                search_method="gemini (real-time)"
            )
        else:
            # Use Google Custom Search
            searcher = GoogleNewsSearch()
            articles = searcher.search_news(
                query=search_query,
                language=request.language.value,
                num_results=request.num_articles,
                date_restrict=request.date_restrict.value
            )
            
            sources = [
                {
                    "title": article.title,
                    "url": article.url,
                    "snippet": article.snippet,
                    "source": article.source
                }
                for article in articles
            ]
            
            return NewsSearchResponse(
                success=True,
                content="",
                sources=sources,
                query=search_query,
                search_method="custom_search (indexed)"
            )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def generate_timestamp_id() -> str:
    """Generate a timestamp-based ID (YYYYMMDD_HHMMSS format)."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def save_sources_file(sources: list, prompt: str, timestamp_id: str, lang_code: str):
    """Save news sources to a JSON file."""
    sources_dir = os.path.join(BASE_DIR, "data", "sources")
    os.makedirs(sources_dir, exist_ok=True)
    
    sources_data = {
        "timestamp": datetime.now().isoformat(),
        "prompt": prompt,
        "language": lang_code,
        "sources": sources
    }
    
    sources_file = os.path.join(sources_dir, f"sources_{timestamp_id}.json")
    with open(sources_file, "w", encoding="utf-8") as f:
        json.dump(sources_data, f, ensure_ascii=False, indent=2)
    
    return sources_file


@app.post("/generate", response_model=NewsPodcastResponse)
async def generate_news_podcast(request: NewsPodcastRequest, api_key: bool = Depends(verify_api_key)):
    """
    Generate a podcast from the latest news.
    
    This endpoint:
    1. Searches for news using the selected method (gemini recommended)
    2. Generates a podcast transcript from the news content
    3. Converts the transcript to audio using TTS
    
    ## Search Methods
    - **gemini** (default, recommended): Uses Gemini's google_search_retrieval for real-time news
    - **custom_search**: Uses Google Custom Search API (may have indexing delays)
    
    ## Example Requests
    ```json
    {"prompt": "정치뉴스를 요약해줘", "language": "ko"}
    {"prompt": "AI 관련 뉴스", "language": "ko", "num_articles": 5}
    {"prompt": "경제 뉴스", "language": "ko", "tts_model": "gemini"}
    ```
    """
    request_id = str(uuid.uuid4())
    timestamp_id = generate_timestamp_id()
    
    try:
        search_query = extract_search_query(request.prompt)
        lang_code = request.language.value
        lang_config = get_language_config(lang_code)
        
        # Load and configure conversation settings
        conv_config = load_conversation_config().to_dict()
        conv_config["output_language"] = get_language_name(lang_code)
        
        # Apply language-specific settings
        conv_config["podcast_name"] = request.podcast_name or lang_config["podcast_name"]
        conv_config["podcast_tagline"] = lang_config["podcast_tagline"]
        conv_config["user_instructions"] = lang_config["user_instructions"]
        
        # Set language-specific TTS settings (ending_message must be inside text_to_speech)
        if "text_to_speech" not in conv_config:
            conv_config["text_to_speech"] = {}
        conv_config["text_to_speech"]["ending_message"] = lang_config["ending_message"]
        
        if "gemini" not in conv_config["text_to_speech"]:
            conv_config["text_to_speech"]["gemini"] = {}
        conv_config["text_to_speech"]["gemini"]["default_voices"] = lang_config["tts_voices"]
        
        if request.user_instructions:
            conv_config["user_instructions"] = f"{conv_config['user_instructions']}\n{request.user_instructions}"
        
        news_sources = []
        topic_suffix = lang_config["topic_suffix"]
        
        if request.search_method == SearchMethod.GEMINI:
            # Clear previous sources before generating
            clear_gemini_sources()
            
            # Use Gemini's real-time search with retry logic
            max_retries = 3
            last_error = None
            audio_file = None
            
            for attempt in range(max_retries):
                try:
                    logger.info(f"Generating podcast (attempt {attempt + 1}/{max_retries})")
                    audio_file = generate_podcast(
                        topic=f"{search_query} {topic_suffix}",
                        tts_model=request.tts_model.value,
                        conversation_config=conv_config,
                        longform=request.longform
                    )
                    if audio_file:
                        break  # Success, exit retry loop
                except ValueError as e:
                    last_error = e
                    logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                    if attempt < max_retries - 1:
                        logger.info("Retrying podcast generation...")
                        continue
                except Exception as e:
                    last_error = e
                    logger.error(f"Unexpected error on attempt {attempt + 1}: {str(e)}")
                    break  # Don't retry on unexpected errors
            
            if not audio_file:
                raise ValueError(f"Failed to generate podcast after {max_retries} attempts: {str(last_error)}")
            
            # Get actual sources from Gemini search
            gemini_sources = get_last_gemini_sources()
            news_sources = [
                {"method": "gemini", "query": search_query, "referenced_urls": gemini_sources}
            ]
            
        else:
            # Use Google Custom Search
            searcher = GoogleNewsSearch()
            articles = searcher.search_news(
                query=search_query,
                language=request.language.value,
                num_results=request.num_articles,
                date_restrict=request.date_restrict.value
            )
            
            if not articles:
                return NewsPodcastResponse(
                    success=False,
                    message="검색된 뉴스가 없습니다. 다른 검색어를 시도해주세요.",
                    request_id=request_id,
                    news_sources=[],
                    search_method=request.search_method.value
                )
            
            urls = [article.url for article in articles]
            news_sources = [
                {"title": article.title, "url": article.url, "source": article.source}
                for article in articles
            ]
            
            audio_file = generate_podcast(
                urls=urls,
                tts_model=request.tts_model.value,
                conversation_config=conv_config,
                longform=request.longform
            )
        
        if audio_file and os.path.isfile(audio_file):
            # Extract timestamp from the generated audio filename (e.g., podcast_20260110_153045.mp3)
            audio_basename = os.path.basename(audio_file)
            # Extract timestamp from filename: podcast_YYYYMMDD_HHMMSS.mp3 -> YYYYMMDD_HHMMSS
            import re
            timestamp_match = re.search(r'podcast_(\d{8}_\d{6})\.mp3', audio_basename)
            if timestamp_match:
                file_timestamp = timestamp_match.group(1)
            else:
                file_timestamp = timestamp_id  # fallback to request timestamp
            
            # The audio file is already in the correct location from client.py
            filename = audio_basename
            
            # Transcript and timeline are already saved with the same timestamp by client.py
            transcripts_dir = os.path.join(BASE_DIR, "data", "transcripts")
            transcript_file = os.path.join(transcripts_dir, f"transcript_{file_timestamp}.txt")
            timeline_file = os.path.join(transcripts_dir, f"timeline_{file_timestamp}.txt")
            
            transcript_url = None
            if os.path.exists(transcript_file):
                transcript_url = f"/transcripts/transcript_{file_timestamp}.txt"
            
            # Save news sources to JSON file (use same timestamp as audio/transcript)
            sources_file = save_sources_file(
                sources=news_sources,
                prompt=request.prompt,
                timestamp_id=file_timestamp,
                lang_code=lang_code
            )
            
            return NewsPodcastResponse(
                success=True,
                audio_url=f"/audio/{filename}",
                transcript_url=transcript_url,
                message=f"팟캐스트가 성공적으로 생성되었습니다. ({request.search_method.value} 방법 사용)",
                request_id=request_id,
                news_sources=news_sources,
                search_method=request.search_method.value
            )
        else:
            return NewsPodcastResponse(
                success=False,
                message="팟캐스트 생성에 실패했습니다.",
                request_id=request_id,
                news_sources=news_sources,
                search_method=request.search_method.value
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"팟캐스트 생성 중 오류가 발생했습니다: {str(e)}"
        )


@app.get("/audio/{filename}")
async def serve_audio(filename: str, api_key: bool = Depends(verify_api_key)):
    """Serve generated audio file."""
    file_path = os.path.join(TEMP_AUDIO_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(
        file_path,
        media_type="audio/mpeg",
        filename=filename
    )


@app.delete("/audio/{filename}")
async def delete_audio(filename: str, api_key: bool = Depends(verify_api_key)):
    """Delete a generated audio file."""
    file_path = os.path.join(TEMP_AUDIO_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    os.remove(file_path)
    return {"success": True, "message": "파일이 삭제되었습니다."}


@app.get("/transcripts/{filename}")
async def serve_transcript(filename: str, api_key: bool = Depends(verify_api_key)):
    """Serve transcript file."""
    transcripts_dir = os.path.join(BASE_DIR, "data", "transcripts")
    file_path = os.path.join(transcripts_dir, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(
        file_path,
        media_type="text/plain; charset=utf-8",
        filename=filename
    )


@app.get("/sources/{filename}")
async def serve_sources(filename: str, api_key: bool = Depends(verify_api_key)):
    """Serve news sources JSON file."""
    sources_dir = os.path.join(BASE_DIR, "data", "sources")
    file_path = os.path.join(sources_dir, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(
        file_path,
        media_type="application/json",
        filename=filename
    )


# ============================================================================
# CLI Runner
# ============================================================================

def run_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Run the API server."""
    uvicorn.run(
        "podcastfy.api.news_podcast_api:app",
        host=host,
        port=port,
        reload=reload
    )


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host=host, port=port)
