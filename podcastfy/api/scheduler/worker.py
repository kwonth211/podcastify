"""
Scheduler Worker for automated podcast generation.

This module provides a simple cron-based scheduler that:
1. Checks for pending schedules every minute
2. Queues podcast generation tasks
3. Updates schedule metadata after runs
"""

import asyncio
import signal
from datetime import datetime
from typing import Optional
from uuid import UUID

from ..db import get_supabase_admin_client
from ..services.schedule_service import ScheduleService
from ..services.credits_service import CreditsService
from ..services.podcast_service import PodcastService
from ..models.podcast import PodcastStatus
from ..utils.logger import get_logger
from .tasks import PodcastGenerationTask

logger = get_logger(__name__)


class SchedulerWorker:
    """
    Worker that processes scheduled podcast generation.
    
    Runs continuously and checks for pending schedules every minute.
    """
    
    def __init__(self):
        self.db = get_supabase_admin_client()
        self.schedule_service = ScheduleService(self.db)
        self.credits_service = CreditsService(self.db)
        self.podcast_service = PodcastService(self.db)
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the scheduler worker."""
        logger.info("Starting scheduler worker...")
        self._running = True
        
        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._handle_signal)
        
        self._task = asyncio.create_task(self._run_loop())
        
        try:
            await self._task
        except asyncio.CancelledError:
            logger.info("Scheduler worker cancelled")
    
    async def stop(self):
        """Stop the scheduler worker."""
        logger.info("Stopping scheduler worker...")
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    def _handle_signal(self):
        """Handle shutdown signals."""
        logger.info("Received shutdown signal")
        self._running = False
        if self._task:
            self._task.cancel()
    
    async def _run_loop(self):
        """Main scheduler loop - runs every minute."""
        while self._running:
            try:
                await self._check_and_execute_schedules()
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
            
            # Wait 60 seconds before next check
            await asyncio.sleep(60)
    
    async def _check_and_execute_schedules(self):
        """Check for pending schedules and execute them."""
        logger.debug("Checking for pending schedules...")
        
        try:
            # Get all schedules that need to run
            pending_schedules = await self.schedule_service.get_pending_schedules(
                limit=100
            )
            
            if not pending_schedules:
                logger.debug("No pending schedules")
                return
            
            logger.info(f"Found {len(pending_schedules)} pending schedules")
            
            for schedule in pending_schedules:
                try:
                    await self._process_schedule(schedule)
                except Exception as e:
                    logger.error(f"Error processing schedule {schedule.id}: {e}")
                    await self.schedule_service.update_schedule_after_run(
                        schedule.id,
                        success=False
                    )
        except Exception as e:
            logger.error(f"Error checking schedules: {e}")
    
    async def _process_schedule(self, schedule):
        """Process a single schedule."""
        logger.info(f"Processing schedule {schedule.id} for user {schedule.user_id}")
        
        # Check and use batch token
        try:
            await self.credits_service.use_batch_token(schedule.user_id)
        except Exception as e:
            logger.warning(f"Failed to use batch token for schedule {schedule.id}: {e}")
            # Deactivate schedule if no tokens
            await self.schedule_service.update_schedule(
                schedule.id,
                {"is_active": False},
            )
            return
        
        # Create podcast record
        podcast = await self.podcast_service.create_podcast(
            user_id=schedule.user_id,
            prompt=schedule.prompt,
            schedule_id=schedule.id,
            metadata={
                "language": schedule.language,
                "tts_model": schedule.tts_model,
                "scheduled_run": True,
            }
        )
        
        # Create job record
        job_id = await self._create_job_record(schedule.id, podcast.id)
        
        # Execute the generation task
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
        
        # Update job and schedule
        await self._update_job_record(job_id, podcast.id, success)
        await self.schedule_service.update_schedule_after_run(
            schedule.id,
            success=success
        )
        
        logger.info(f"Schedule {schedule.id} completed with success={success}")
    
    async def _create_job_record(
        self, 
        schedule_id: UUID, 
        podcast_id: UUID
    ) -> UUID:
        """Create a scheduler job record."""
        result = self.db.table("scheduler_jobs").insert({
            "schedule_id": str(schedule_id),
            "podcast_id": str(podcast_id),
            "status": "processing",
            "started_at": datetime.utcnow().isoformat(),
        }).execute()
        
        return UUID(result.data[0]["id"])
    
    async def _update_job_record(
        self, 
        job_id: UUID, 
        podcast_id: UUID, 
        success: bool
    ):
        """Update scheduler job record."""
        self.db.table("scheduler_jobs").update({
            "status": "completed" if success else "failed",
            "completed_at": datetime.utcnow().isoformat(),
        }).eq("id", str(job_id)).execute()


async def run_scheduler():
    """Entry point for running the scheduler."""
    worker = SchedulerWorker()
    await worker.start()


if __name__ == "__main__":
    asyncio.run(run_scheduler())
