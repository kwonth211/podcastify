#!/usr/bin/env python3
"""
GitHub Actions workflow script for podcast generation
Handles URL processing, podcast generation, and Cloudflare R2 upload
"""
import os
import sys
import glob
from pathlib import Path
from datetime import datetime
from typing import Optional, List
import boto3
from botocore.config import Config
from podcastfy.client import generate_podcast
from podcastfy.utils.config_conversation import load_conversation_config


def load_urls_from_file(filepath: str) -> List[str]:
    """Load URLs from a file, skipping comments and empty lines."""
    urls = []
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    # Handle comma-separated URLs in a single line
                    line_urls = [url.strip() for url in line.split(',') if url.strip()]
                    urls.extend(line_urls)
    return urls


def parse_urls_input(urls_input: str) -> List[str]:
    """Parse URLs from comma-separated string or file path."""
    if not urls_input:
        return []
    
    # Check if it's a file path
    if os.path.exists(urls_input):
        return load_urls_from_file(urls_input)
    
    # Otherwise, treat as comma-separated URLs
    return [url.strip() for url in urls_input.split(',') if url.strip()]


def upload_to_r2(
    file_path: str,
    bucket_name: str = "daily-podcast",
    endpoint_url: str = "https://2d797e9348660f2d5a228739b19cd956.r2.cloudflarestorage.com",
    timestamp: Optional[str] = None
) -> Optional[str]:
    """Upload a file to Cloudflare R2 and return the public URL."""
    # For testing, use hardcoded values (will be moved to secrets later)
    access_key_id = os.environ.get('R2_ACCESS_KEY_ID', '')
    secret_access_key = os.environ.get('R2_SECRET_ACCESS_KEY', '')
    
    if not access_key_id or not secret_access_key:
        print("⚠️  R2 credentials not set. Skipping R2 upload.")
        return None
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return None
    
    try:
        # Configure boto3 for R2
        s3_config = Config(
            signature_version='s3v4',
            region_name='auto'
        )
        
        s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=s3_config
        )
        
        # Prepare file key
        filename = Path(file_path).name
        if timestamp:
            file_key = f"{timestamp}_{filename}"
        else:
            file_key = filename
        
        # Determine content type
        content_type = 'application/octet-stream'
        if filename.endswith('.mp3'):
            content_type = 'audio/mpeg'
        elif filename.endswith('.txt'):
            content_type = 'text/plain'
        
        # Upload file
        s3_client.upload_file(
            file_path,
            bucket_name,
            file_key,
            ExtraArgs={'ContentType': content_type}
        )
        
        # Construct public URL
        # R2 public URL format: https://{account_id}.r2.cloudflarestorage.com/{bucket}/{key}
        # Or use custom domain if configured
        public_url = f"{endpoint_url}/{bucket_name}/{file_key}"
        
        print(f"✅ Successfully uploaded to R2: {file_key}")
        print(f"📎 Bucket: {bucket_name}")
        print(f"📎 Public URL: {public_url}")
        
        return public_url
    except Exception as e:
        print(f"❌ Error uploading to R2: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def find_latest_file(pattern: str) -> Optional[str]:
    """Find the most recently created file matching the pattern."""
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def write_github_output(key: str, value: str):
    """Write to GitHub Actions output file."""
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a') as f:
            f.write(f"{key}={value}\n")


def main():
    """Main workflow function."""
    # Get inputs from environment variables (set by GitHub Actions)
    urls_input = os.environ.get('URLS', '')
    timestamp = os.environ.get('TIMESTAMP', datetime.now().strftime('%Y%m%d_%H%M%S'))
    
    # If no URLs provided, try to load from default file
    if not urls_input:
        default_url_file = 'data/urls/daily_urls.txt'
        if os.path.exists(default_url_file):
            urls = load_urls_from_file(default_url_file)
            print(f"📋 Loaded {len(urls)} URL(s) from {default_url_file}")
        else:
            print("❌ No URLs provided. Skipping generation.")
            sys.exit(0)
    else:
        urls = parse_urls_input(urls_input)
    
    if not urls:
        print("❌ No URLs provided. Skipping generation.")
        sys.exit(0)
    
    # Load config
    try:
        conv_config = load_conversation_config()
        config_dict = conv_config.to_dict()
        default_tts = config_dict.get("text_to_speech", {}).get("default_tts_model", "gemini")
        print(f"📋 Using config from conversation_config.yaml:")
        print(f"   - TTS Model: {default_tts}")
        print(f"   - Max Chunks: {config_dict.get('max_num_chunks', 4)}")
        print(f"   - Min Chunk Size: {config_dict.get('min_chunk_size', 2000)}")
    except Exception as e:
        print(f"⚠️  Warning: Could not load config file, using defaults: {e}")
        default_tts = "gemini"
    
    # Generate podcast
    print(f"\n🎙️  Generating podcast...")
    print(f"   URLs: {len(urls)} URL(s)")
    
    try:
        result = generate_podcast(
            urls=urls,
            tts_model=default_tts,
            longform=True
        )
        
        if not result:
            print("❌ No output file generated")
            sys.exit(1)
        
        print(f"✅ Podcast generated successfully: {result}")
        write_github_output("audio_file", result)
        
        # Upload audio to R2
        r2_url = upload_to_r2(result, timestamp=timestamp)
        if r2_url:
            write_github_output("r2_url", r2_url)
        
        # Upload transcript to R2
        transcript_file = find_latest_file("data/transcripts/*.txt")
        if transcript_file:
            upload_to_r2(transcript_file, timestamp=timestamp)
        
        sys.exit(0)
        
    except Exception as e:
        print(f"❌ Error generating podcast: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

