"""
Podcast generation tasks for the scheduler.

This module contains the actual podcast generation logic
that is executed when a schedule triggers.
"""

import os
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from ..db import get_supabase_admin_client
from ..services.podcast_service import PodcastService
from ..models.podcast import PodcastStatus
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PodcastGenerationTask:
    """
    Task for generating a podcast.
    
    Encapsulates all the logic for generating a podcast
    from a scheduled job.
    """
    
    podcast_id: UUID
    schedule_id: UUID
    user_id: UUID
    prompt: str
    language: str
    tts_model: str
    email: str
    
    def __post_init__(self):
        self.db = get_supabase_admin_client()
        self.podcast_service = PodcastService(self.db)
    
    async def execute(self) -> bool:
        """
        Execute the podcast generation.
        
        Returns True if successful, False otherwise.
        """
        try:
            logger.info(f"Starting podcast generation for {self.podcast_id}")
            
            # Update status: generating
            await self.podcast_service.update_podcast_status(
                podcast_id=self.podcast_id,
                status=PodcastStatus.GENERATING,
                progress=0,
                current_step="prompting",
            )
            
            # Import generation dependencies
            from ...client import generate_podcast as generate_audio
            from ...utils.config_conversation import load_conversation_config
            
            # Update progress: prompting (10%)
            await self._update_progress(10, "prompting")
            
            # Configure conversation
            conv_config = load_conversation_config().to_dict()
            conv_config["output_language"] = self._get_language_name()
            
            # Apply language-specific settings
            lang_config = self._get_language_config()
            conv_config["podcast_name"] = lang_config.get("podcast_name", "News Summary")
            conv_config["podcast_tagline"] = lang_config.get("podcast_tagline", "")
            conv_config["user_instructions"] = lang_config.get("user_instructions", "")
            
            # Set TTS voices
            if "text_to_speech" not in conv_config:
                conv_config["text_to_speech"] = {}
            conv_config["text_to_speech"]["ending_message"] = lang_config.get("ending_message", "")
            
            if "gemini" not in conv_config["text_to_speech"]:
                conv_config["text_to_speech"]["gemini"] = {}
            conv_config["text_to_speech"]["gemini"]["default_voices"] = lang_config.get("tts_voices", {})
            
            # Update progress: crawling (40%)
            await self._update_progress(40, "crawling")
            
            # Update progress: summarizing (70%)
            await self._update_progress(70, "summarizing")
            
            # Generate the podcast
            topic_suffix = lang_config.get("topic_suffix", "latest news")
            audio_file = generate_audio(
                topic=f"{self.prompt} {topic_suffix}",
                tts_model=self.tts_model,
                conversation_config=conv_config,
                longform=False,
            )
            
            # Update progress: generating audio (90%)
            await self._update_progress(90, "generating")
            
            if audio_file and os.path.isfile(audio_file):
                # Get file info
                filename = os.path.basename(audio_file)
                file_size = os.path.getsize(audio_file)
                
                # Construct URLs
                audio_url = f"/api/v2/podcasts/audio/{filename}"
                
                # Extract timestamp for related files
                import re
                timestamp_match = re.search(r'podcast_(\d{8}_\d{6})\.mp3', filename)
                file_timestamp = timestamp_match.group(1) if timestamp_match else None
                
                transcript_url = None
                sources_url = None
                
                if file_timestamp:
                    transcript_url = f"/api/v2/podcasts/transcripts/transcript_{file_timestamp}.txt"
                    sources_url = f"/api/v2/podcasts/sources/sources_{file_timestamp}.json"
                
                # Complete the podcast
                title = self._generate_title()
                await self.podcast_service.complete_podcast(
                    podcast_id=self.podcast_id,
                    title=title,
                    audio_url=audio_url,
                    transcript_url=transcript_url,
                    sources_url=sources_url,
                    duration=0,  # TODO: Calculate from audio
                    file_size=file_size,
                )
                
                # Send email notification
                await self._send_email_notification(title, audio_url)
                
                logger.info(f"Podcast {self.podcast_id} generated successfully")
                return True
            else:
                await self.podcast_service.fail_podcast(
                    podcast_id=self.podcast_id,
                    error_message="Failed to generate audio file",
                    current_step="generating",
                )
                return False
                
        except Exception as e:
            logger.error(f"Podcast generation failed: {e}")
            await self.podcast_service.fail_podcast(
                podcast_id=self.podcast_id,
                error_message=str(e),
            )
            return False
    
    async def _update_progress(self, progress: int, step: str):
        """Update podcast progress."""
        await self.podcast_service.update_podcast_status(
            podcast_id=self.podcast_id,
            status=PodcastStatus.GENERATING,
            progress=progress,
            current_step=step,
        )
    
    def _get_language_name(self) -> str:
        """Get full language name from code."""
        lang_map = {
            "ko": "Korean",
            "en": "English",
            "ja": "Japanese",
            "zh": "Chinese",
        }
        return lang_map.get(self.language, "English")
    
    def _get_language_config(self) -> dict:
        """Get language-specific configuration."""
        configs = {
            "ko": {
                "podcast_name": "뉴스 요약",
                "podcast_tagline": "오늘의 주요 뉴스를 요약해드립니다",
                "user_instructions": "이 팟캐스트는 뉴스를 요약하고 분석하는 프로그램입니다.",
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
                "user_instructions": "This podcast summarizes and analyzes the latest news.",
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
                "user_instructions": "このポッドキャストはニュースを要約・分析する番組です。",
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
                "user_instructions": "本播客为您总结分析最新新闻。",
                "ending_message": "以上就是今天的新闻摘要，感谢收听！",
                "topic_suffix": "最新新闻",
                "tts_voices": {
                    "question": "cmn-CN-Chirp3-HD-Charon",
                    "answer": "cmn-CN-Chirp3-HD-Aoede"
                }
            }
        }
        return configs.get(self.language, configs["en"])
    
    def _generate_title(self) -> str:
        """Generate a title for the podcast."""
        from datetime import datetime
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        title_templates = {
            "ko": f"뉴스 요약 - {self.prompt[:30]} ({date_str})",
            "en": f"News Summary - {self.prompt[:30]} ({date_str})",
            "ja": f"ニュースまとめ - {self.prompt[:30]} ({date_str})",
            "zh": f"新闻摘要 - {self.prompt[:30]} ({date_str})",
        }
        
        return title_templates.get(self.language, title_templates["en"])
    
    async def _send_email_notification(self, title: str, audio_url: str):
        """Send email notification with podcast link."""
        # TODO: Implement email sending
        # For now, just log
        logger.info(
            f"Would send email to {self.email}: "
            f"Title: {title}, Audio: {audio_url}"
        )
        
        # Example implementation with SendGrid or similar:
        # from sendgrid import SendGridAPIClient
        # from sendgrid.helpers.mail import Mail
        #
        # message = Mail(
        #     from_email='noreply@dailynewspodcast.com',
        #     to_emails=self.email,
        #     subject=f'🎙️ {title}',
        #     html_content=f'''
        #         <h1>🎙️ 오늘의 뉴스 팟캐스트</h1>
        #         <h2>{title}</h2>
        #         <a href="{audio_url}">▶️ 지금 듣기</a>
        #     '''
        # )
        # sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        # sg.send(message)
