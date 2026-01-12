"""Helper utilities for the API."""

import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from zoneinfo import ZoneInfo


def generate_request_id() -> str:
    """Generate a unique request ID."""
    return str(uuid.uuid4())


def generate_timestamp_id() -> str:
    """Generate a timestamp-based ID (YYYYMMDD_HHMMSS format)."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def convert_timezone(dt: datetime, from_tz: str, to_tz: str) -> datetime:
    """
    Convert datetime from one timezone to another.
    
    Args:
        dt: Datetime to convert
        from_tz: Source timezone (IANA name)
        to_tz: Target timezone (IANA name)
    
    Returns:
        Datetime in target timezone
    """
    from_zone = ZoneInfo(from_tz)
    to_zone = ZoneInfo(to_tz)
    
    # If datetime is naive, assume it's in from_tz
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=from_zone)
    else:
        dt = dt.astimezone(from_zone)
    
    return dt.astimezone(to_zone)


def calculate_next_run(
    days: List[str],
    time_str: str,
    timezone: str,
    from_datetime: Optional[datetime] = None
) -> datetime:
    """
    Calculate the next run time for a schedule.
    
    Args:
        days: List of days (monday, tuesday, etc.)
        time_str: Time in HH:MM format
        timezone: IANA timezone name
        from_datetime: Calculate from this time (default: now)
    
    Returns:
        Next run datetime in UTC
    """
    day_mapping = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }
    
    # Parse time
    hour, minute = map(int, time_str.split(":"))
    
    # Get current time in user's timezone
    tz = ZoneInfo(timezone)
    if from_datetime is None:
        now = datetime.now(tz)
    else:
        now = from_datetime.astimezone(tz) if from_datetime.tzinfo else from_datetime.replace(tzinfo=tz)
    
    # Convert days to numbers and sort
    schedule_days = sorted([day_mapping[d.lower()] for d in days])
    current_day = now.weekday()
    current_time_minutes = now.hour * 60 + now.minute
    schedule_time_minutes = hour * 60 + minute
    
    # Check if we can run today
    if current_day in schedule_days and current_time_minutes < schedule_time_minutes:
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return next_run.astimezone(ZoneInfo("UTC"))
    
    # Find next scheduled day
    next_day = None
    for day in schedule_days:
        if day > current_day:
            next_day = day
            break
    
    if next_day is None:
        # Wrap to next week
        next_day = schedule_days[0]
        days_until = (next_day - current_day + 7) % 7
        if days_until == 0:
            days_until = 7
    else:
        days_until = next_day - current_day
    
    next_run = now + timedelta(days=days_until)
    next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    return next_run.astimezone(ZoneInfo("UTC"))


def format_duration(seconds: int) -> str:
    """
    Format duration in seconds to human-readable string.
    
    Args:
        seconds: Duration in seconds
    
    Returns:
        Formatted string (e.g., "5:30", "1:23:45")
    """
    if seconds < 0:
        return "0:00"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def format_file_size(bytes_size: int) -> str:
    """
    Format file size in bytes to human-readable string.
    
    Args:
        bytes_size: Size in bytes
    
    Returns:
        Formatted string (e.g., "1.5 MB", "256 KB")
    """
    if bytes_size < 0:
        return "0 B"
    
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    
    return f"{bytes_size:.1f} TB"


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing/replacing invalid characters.
    
    Args:
        filename: Original filename
    
    Returns:
        Sanitized filename
    """
    import re
    # Remove invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove leading/trailing whitespace and dots
    sanitized = sanitized.strip('. ')
    # Limit length
    if len(sanitized) > 200:
        name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
        sanitized = name[:200 - len(ext) - 1] + '.' + ext if ext else name[:200]
    
    return sanitized or "unnamed"
