"""Schedule service for managing podcast schedules."""

from typing import List, Optional
from uuid import UUID
from datetime import datetime

from supabase import Client

from ..models.schedule import (
    Schedule,
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleResponse,
)
from ..models.subscription import PlanType, PLAN_CONFIGS
from ..utils.exceptions import NotFoundError, ScheduleLimitExceededError
from ..utils.helpers import calculate_next_run
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ScheduleService:
    """Service for schedule operations."""
    
    def __init__(self, db: Client):
        self.db = db
    
    async def get_schedule_by_id(self, schedule_id: UUID) -> Optional[Schedule]:
        """Get schedule by ID."""
        result = self.db.table("schedules").select("*").eq(
            "id", str(schedule_id)
        ).execute()
        
        if not result.data:
            return None
        
        return Schedule(**result.data[0])
    
    async def get_schedules_by_user_id(
        self, 
        user_id: UUID,
        active_only: bool = False
    ) -> List[Schedule]:
        """Get all schedules for a user."""
        query = self.db.table("schedules").select("*").eq(
            "user_id", str(user_id)
        )
        
        if active_only:
            query = query.eq("is_active", True)
        
        result = query.order("created_at", desc=True).execute()
        
        return [Schedule(**row) for row in result.data]
    
    async def get_user_schedule_count(self, user_id: UUID) -> int:
        """Get count of active schedules for a user."""
        result = self.db.table("schedules").select(
            "*", count="exact"
        ).eq("user_id", str(user_id)).eq("is_active", True).execute()
        
        return result.count or 0
    
    async def check_schedule_limit(self, user_id: UUID, plan_id: PlanType) -> bool:
        """Check if user can create more schedules."""
        plan_config = PLAN_CONFIGS.get(plan_id, PLAN_CONFIGS[PlanType.FREE])
        max_schedules = plan_config.max_schedules
        
        if max_schedules == -1:
            return True  # Unlimited
        
        current_count = await self.get_user_schedule_count(user_id)
        return current_count < max_schedules
    
    async def create_schedule(
        self, 
        schedule_data: ScheduleCreate,
        plan_id: PlanType = PlanType.FREE
    ) -> Schedule:
        """Create a new schedule."""
        if not schedule_data.user_id:
            raise ValueError("user_id is required")
        
        # Check schedule limit
        can_create = await self.check_schedule_limit(schedule_data.user_id, plan_id)
        if not can_create:
            plan_config = PLAN_CONFIGS[plan_id]
            current = await self.get_user_schedule_count(schedule_data.user_id)
            raise ScheduleLimitExceededError(
                current=current,
                limit=plan_config.max_schedules,
            )
        
        # Calculate next run time
        next_run = calculate_next_run(
            days=[d.value for d in schedule_data.days],
            time_str=schedule_data.time,
            timezone=schedule_data.timezone,
        )
        
        insert_data = {
            "user_id": str(schedule_data.user_id),
            "name": schedule_data.name,
            "prompt": schedule_data.prompt,
            "days": [d.value for d in schedule_data.days],
            "time": schedule_data.time,
            "timezone": schedule_data.timezone,
            "email": schedule_data.email,
            "language": schedule_data.language,
            "tts_model": schedule_data.tts_model,
            "is_active": schedule_data.is_active,
            "next_run": next_run.isoformat(),
        }
        
        result = self.db.table("schedules").insert(insert_data).execute()
        
        if not result.data:
            raise Exception("Failed to create schedule")
        
        logger.info(f"Created schedule {result.data[0]['id']} for user {schedule_data.user_id}")
        return Schedule(**result.data[0])
    
    async def update_schedule(
        self, 
        schedule_id: UUID, 
        schedule_data: ScheduleUpdate,
        user_id: Optional[UUID] = None
    ) -> Schedule:
        """Update an existing schedule."""
        existing = await self.get_schedule_by_id(schedule_id)
        if not existing:
            raise NotFoundError("Schedule", str(schedule_id))
        
        # Verify ownership if user_id provided
        if user_id and existing.user_id != user_id:
            raise NotFoundError("Schedule", str(schedule_id))
        
        update_data = schedule_data.model_dump(exclude_unset=True)
        
        # Convert days enum to strings if present
        if "days" in update_data and update_data["days"]:
            update_data["days"] = [d.value if hasattr(d, 'value') else d for d in update_data["days"]]
        
        # Recalculate next_run if schedule timing changed
        if any(k in update_data for k in ["days", "time", "timezone", "is_active"]):
            days = update_data.get("days", existing.days)
            time_str = update_data.get("time", existing.time)
            timezone = update_data.get("timezone", existing.timezone)
            is_active = update_data.get("is_active", existing.is_active)
            
            if is_active:
                # Convert days to strings if they're enum values
                day_strings = [d.value if hasattr(d, 'value') else d for d in days]
                next_run = calculate_next_run(
                    days=day_strings,
                    time_str=time_str,
                    timezone=timezone,
                )
                update_data["next_run"] = next_run.isoformat()
            else:
                update_data["next_run"] = None
        
        if not update_data:
            return existing
        
        result = self.db.table("schedules").update(update_data).eq(
            "id", str(schedule_id)
        ).execute()
        
        if not result.data:
            raise NotFoundError("Schedule", str(schedule_id))
        
        logger.info(f"Updated schedule {schedule_id}")
        return Schedule(**result.data[0])
    
    async def delete_schedule(
        self, 
        schedule_id: UUID,
        user_id: Optional[UUID] = None
    ) -> bool:
        """Delete a schedule."""
        existing = await self.get_schedule_by_id(schedule_id)
        if not existing:
            raise NotFoundError("Schedule", str(schedule_id))
        
        # Verify ownership if user_id provided
        if user_id and existing.user_id != user_id:
            raise NotFoundError("Schedule", str(schedule_id))
        
        self.db.table("schedules").delete().eq(
            "id", str(schedule_id)
        ).execute()
        
        logger.info(f"Deleted schedule {schedule_id}")
        return True
    
    async def toggle_schedule(
        self, 
        schedule_id: UUID,
        user_id: Optional[UUID] = None
    ) -> Schedule:
        """Toggle schedule active status."""
        existing = await self.get_schedule_by_id(schedule_id)
        if not existing:
            raise NotFoundError("Schedule", str(schedule_id))
        
        if user_id and existing.user_id != user_id:
            raise NotFoundError("Schedule", str(schedule_id))
        
        new_status = not existing.is_active
        
        update_data = {"is_active": new_status}
        
        if new_status:
            # Recalculate next run
            next_run = calculate_next_run(
                days=[d for d in existing.days],
                time_str=existing.time,
                timezone=existing.timezone,
            )
            update_data["next_run"] = next_run.isoformat()
        else:
            update_data["next_run"] = None
        
        result = self.db.table("schedules").update(update_data).eq(
            "id", str(schedule_id)
        ).execute()
        
        if not result.data:
            raise NotFoundError("Schedule", str(schedule_id))
        
        logger.info(f"Toggled schedule {schedule_id} to {new_status}")
        return Schedule(**result.data[0])
    
    async def get_pending_schedules(self, limit: int = 100) -> List[Schedule]:
        """Get schedules that are due to run."""
        now = datetime.utcnow()
        
        result = self.db.table("schedules").select("*").eq(
            "is_active", True
        ).lte("next_run", now.isoformat()).order(
            "next_run"
        ).limit(limit).execute()
        
        return [Schedule(**row) for row in result.data]
    
    async def update_schedule_after_run(
        self, 
        schedule_id: UUID,
        success: bool = True
    ) -> Schedule:
        """Update schedule after execution."""
        existing = await self.get_schedule_by_id(schedule_id)
        if not existing:
            raise NotFoundError("Schedule", str(schedule_id))
        
        now = datetime.utcnow()
        
        # Calculate next run
        next_run = calculate_next_run(
            days=[d for d in existing.days],
            time_str=existing.time,
            timezone=existing.timezone,
            from_datetime=now,
        )
        
        update_data = {
            "last_run": now.isoformat(),
            "next_run": next_run.isoformat(),
            "run_count": existing.run_count + 1,
        }
        
        if not success:
            update_data["failure_count"] = existing.failure_count + 1
        
        result = self.db.table("schedules").update(update_data).eq(
            "id", str(schedule_id)
        ).execute()
        
        if not result.data:
            raise NotFoundError("Schedule", str(schedule_id))
        
        logger.info(f"Updated schedule {schedule_id} after run (success={success})")
        return Schedule(**result.data[0])
