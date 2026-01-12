"""
Simple cron-based scheduler using APScheduler.

This provides an alternative to the custom worker implementation
using the well-tested APScheduler library.
"""

import asyncio
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..db import get_supabase_admin_client
from ..services.schedule_service import ScheduleService
from ..services.credits_service import CreditsService
from ..services.subscription_service import SubscriptionService
from ..utils.logger import get_logger
from .tasks import PodcastGenerationTask

logger = get_logger(__name__)


class CronScheduler:
    """
    APScheduler-based scheduler for podcast generation.
    
    Features:
    - Checks schedules every minute
    - Resets expired credits daily
    - Processes expired subscriptions daily
    """
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.db = get_supabase_admin_client()
        self.schedule_service = ScheduleService(self.db)
        self.credits_service = CreditsService(self.db)
        self.subscription_service = SubscriptionService(self.db)
    
    def start(self):
        """Start the scheduler with all jobs."""
        logger.info("Starting cron scheduler...")
        
        # Check schedules every minute
        self.scheduler.add_job(
            self._check_schedules,
            CronTrigger(minute="*"),  # Every minute
            id="check_schedules",
            name="Check and execute pending schedules",
            replace_existing=True,
        )
        
        # Reset expired credits daily at midnight
        self.scheduler.add_job(
            self._reset_credits,
            CronTrigger(hour=0, minute=0),  # Every day at 00:00
            id="reset_credits",
            name="Reset expired credits",
            replace_existing=True,
        )
        
        # Process expired subscriptions daily
        self.scheduler.add_job(
            self._process_expired_subscriptions,
            CronTrigger(hour=0, minute=5),  # Every day at 00:05
            id="process_subscriptions",
            name="Process expired subscriptions",
            replace_existing=True,
        )
        
        self.scheduler.start()
        logger.info("Cron scheduler started")
    
    def stop(self):
        """Stop the scheduler."""
        logger.info("Stopping cron scheduler...")
        self.scheduler.shutdown()
        logger.info("Cron scheduler stopped")
    
    async def _check_schedules(self):
        """Check and execute pending schedules."""
        try:
            logger.debug("Checking for pending schedules...")
            
            pending = await self.schedule_service.get_pending_schedules(limit=100)
            
            if not pending:
                return
            
            logger.info(f"Found {len(pending)} pending schedules")
            
            for schedule in pending:
                try:
                    await self._process_schedule(schedule)
                except Exception as e:
                    logger.error(f"Error processing schedule {schedule.id}: {e}")
                    await self.schedule_service.update_schedule_after_run(
                        schedule.id,
                        success=False
                    )
        except Exception as e:
            logger.error(f"Error in schedule check: {e}")
    
    async def _process_schedule(self, schedule):
        """Process a single schedule."""
        from ..services.podcast_service import PodcastService
        
        logger.info(f"Processing schedule {schedule.id}")
        
        # Check batch tokens
        try:
            await self.credits_service.use_batch_token(schedule.user_id)
        except Exception as e:
            logger.warning(f"No batch tokens for schedule {schedule.id}: {e}")
            # Deactivate schedule
            from ..models.schedule import ScheduleUpdate
            await self.schedule_service.update_schedule(
                schedule.id,
                ScheduleUpdate(is_active=False),
            )
            return
        
        # Create podcast
        podcast_service = PodcastService(self.db)
        podcast = await podcast_service.create_podcast(
            user_id=schedule.user_id,
            prompt=schedule.prompt,
            schedule_id=schedule.id,
            metadata={
                "language": schedule.language,
                "tts_model": schedule.tts_model,
                "scheduled_run": True,
            }
        )
        
        # Execute generation
        task = PodcastGenerationTask(
            podcast_id=podcast.id,
            schedule_id=schedule.id,
            user_id=schedule.user_id,
            prompt=schedule.prompt,
            language=schedule.language,
            tts_model=schedule.tts_model,
            email=schedule.email,
        )
        
        success = await task.execute()
        
        # Update schedule
        await self.schedule_service.update_schedule_after_run(
            schedule.id,
            success=success
        )
    
    async def _reset_credits(self):
        """Reset expired credits."""
        try:
            count = await self.credits_service.check_expired_credits()
            logger.info(f"Reset {count} expired credits")
        except Exception as e:
            logger.error(f"Error resetting credits: {e}")
    
    async def _process_expired_subscriptions(self):
        """Process expired subscriptions."""
        try:
            count = await self.subscription_service.check_expired_subscriptions()
            logger.info(f"Processed {count} expired subscriptions")
        except Exception as e:
            logger.error(f"Error processing subscriptions: {e}")


def run_cron_scheduler():
    """Entry point for the cron scheduler."""
    scheduler = CronScheduler()
    scheduler.start()
    
    # Keep running
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        scheduler.stop()


if __name__ == "__main__":
    run_cron_scheduler()
