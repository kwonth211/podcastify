"""
Supabase Client Configuration

This module provides a singleton Supabase client for database operations,
authentication, and real-time features.
"""

import os
from typing import Optional
from functools import lru_cache

from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


class SupabaseConfig:
    """Supabase configuration settings."""
    
    def __init__(self):
        self.url: str = os.getenv("SUPABASE_URL", "")
        self.anon_key: str = os.getenv("SUPABASE_ANON_KEY", "")
        self.service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        self.jwt_secret: str = os.getenv("SUPABASE_JWT_SECRET", "")
        
        if not self.url or not self.anon_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_ANON_KEY must be set in environment variables"
            )


@lru_cache()
def get_supabase_config() -> SupabaseConfig:
    """Get cached Supabase configuration."""
    return SupabaseConfig()


def get_supabase_client() -> Client:
    """
    Get Supabase client for regular operations.
    Uses anon key (respects RLS policies).
    """
    config = get_supabase_config()
    return create_client(config.url, config.anon_key)


def get_supabase_admin_client() -> Client:
    """
    Get Supabase admin client for privileged operations.
    Uses service role key (bypasses RLS).
    Use with caution!
    """
    config = get_supabase_config()
    if not config.service_role_key:
        raise ValueError("SUPABASE_SERVICE_ROLE_KEY required for admin operations")
    return create_client(config.url, config.service_role_key)


# Dependency for FastAPI
async def get_db() -> Client:
    """FastAPI dependency for database access."""
    return get_supabase_client()


async def get_admin_db() -> Client:
    """FastAPI dependency for admin database access."""
    return get_supabase_admin_client()
