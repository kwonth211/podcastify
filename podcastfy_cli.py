#!/usr/bin/env python3
"""
Simple CLI wrapper for podcastfy
Usage: python podcastfy_cli.py <url1> [url2] [url3] ...
"""
import sys
from podcastfy.client import generate_podcast

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python podcastfy_cli.py <url1> [url2] [url3] ...")
        sys.exit(1)
    
    urls = sys.argv[1:]
    print(f"Processing {len(urls)} URL(s)...")
    
    try:
        result = generate_podcast(urls=urls, tts_model="edge", longform=True)
        print(f"\n✅ Success! Output: {result}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

