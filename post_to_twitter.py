#!/usr/bin/env python3
"""
Twitter(X) 자동 포스팅 스크립트
데일리 팟캐스트 생성 후 홍보 트윗을 자동으로 올립니다.
"""

import glob
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from zoneinfo import ZoneInfo
import tweepy

# 한국 시간대
KST = ZoneInfo("Asia/Seoul")


def load_topics_from_timeline(timeline_dir: str = "data/transcripts") -> Optional[List[str]]:
    """
    타임라인 파일에서 토픽을 로드합니다.
    
    Args:
        timeline_dir: 타임라인 파일 디렉토리
        
    Returns:
        토픽 리스트 또는 None
    """
    try:
        # 가장 최근 타임라인 파일 찾기 (형식: {timestamp}_timeline_{date}.txt)
        timeline_files = glob.glob(os.path.join(timeline_dir, "*timeline*.txt"))
        if not timeline_files:
            print("⚠️ 타임라인 파일을 찾을 수 없습니다")
            return None
        
        latest_file = max(timeline_files, key=os.path.getmtime)
        print(f"📄 타임라인 파일 로드: {latest_file}")
        
        with open(latest_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 타임라인에서 토픽 추출 (형식: [00:00] 토픽 제목)
        topics = []
        for line in content.split('\n'):
            match = re.match(r'\[[\d:]+\]\s*(.+)', line.strip())
            if match:
                topic = match.group(1).strip()
                if topic:
                    topics.append(topic)
        
        print(f"✅ {len(topics)}개 토픽 추출 완료")
        return topics if topics else None
        
    except Exception as e:
        print(f"⚠️ 타임라인 로드 실패: {e}")
    return None


def create_tweet_message() -> str:
    """
    트윗 메시지를 생성합니다.
    타임라인에서 토픽을 추출하여 포함시킵니다.
    """
    # 한국 시간(KST) 기준으로 날짜 표시
    now_kst = datetime.now(KST)
    today = now_kst.strftime("%-m월 %-d일")
    weekday_kr = ["월", "화", "수", "목", "금", "토", "일"]
    weekday = weekday_kr[now_kst.weekday()]
    
    # 웹사이트 URL (고정)
    website_url = "https://dailynewspod.com"
    hashtags = "#뉴스팟캐스트 #데일리뉴스"
    
    # 타임라인에서 토픽 로드
    topics = load_topics_from_timeline()
    
    if topics:
        # 토픽이 있으면 포함하는 메시지
        header = f"🎙️ {today}({weekday}) 뉴스 팟캐스트\n\n"
        footer = f"\n🔗 {website_url}\n\n{hashtags}"
        
        # 사용 가능한 글자수 계산 (280자 - 헤더 - 푸터)
        available_chars = 280 - len(header) - len(footer) - 10  # 여유분 10자
        
        # 토픽 추가 (글자수 내에서 최대한)
        topic_lines = []
        for topic in topics[:4]:  # 최대 4개
            # 토픽이 너무 길면 자르기
            if len(topic) > 35:
                topic = topic[:32] + "..."
            line = f"• {topic}\n"
            
            # 글자수 체크
            if sum(len(l) for l in topic_lines) + len(line) <= available_chars:
                topic_lines.append(line)
            else:
                break
        
        message = header + "".join(topic_lines) + footer
    else:
        # 토픽이 없으면 기본 메시지
        messages = [
            f"🎙️ {today}({weekday}) 데일리 뉴스가 도착했습니다!\n\n오늘의 주요 뉴스를 팟캐스트로 들어보세요.",
            f"☀️ 좋은 아침이에요! {today}({weekday}) 뉴스 팟캐스트가 준비됐습니다.\n\n출근길에 가볍게 들어보세요 🎧",
            f"📰 {today}({weekday}) 오늘의 뉴스 브리핑!\n\n주요 뉴스를 팟캐스트로 만나보세요.",
        ]
        
        # 날짜 기반으로 메시지 선택 (매일 다른 메시지)
        message_index = now_kst.day % len(messages)
        message = messages[message_index]
        
        # 웹사이트 URL 및 해시태그 추가
        message += f"\n\n🔗 {website_url}\n\n{hashtags}"
    
    return message


def post_to_twitter(message: str) -> dict:
    """
    Twitter API v2를 사용하여 트윗을 게시합니다.
    
    필요한 환경변수:
    - TWITTER_API_KEY
    - TWITTER_API_SECRET
    - TWITTER_ACCESS_TOKEN
    - TWITTER_ACCESS_TOKEN_SECRET
    """
    # 환경변수에서 인증 정보 가져오기
    api_key = os.environ.get("TWITTER_API_KEY")
    api_secret = os.environ.get("TWITTER_API_SECRET")
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
    access_token_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")
    
    # 인증 정보 확인
    missing_keys = []
    if not api_key:
        missing_keys.append("TWITTER_API_KEY")
    if not api_secret:
        missing_keys.append("TWITTER_API_SECRET")
    if not access_token:
        missing_keys.append("TWITTER_ACCESS_TOKEN")
    if not access_token_secret:
        missing_keys.append("TWITTER_ACCESS_TOKEN_SECRET")
    
    if missing_keys:
        print(f"❌ 누락된 환경변수: {', '.join(missing_keys)}")
        return {"success": False, "error": f"Missing environment variables: {missing_keys}"}
    
    try:
        # Twitter API v2 클라이언트 생성
        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret
        )
        
        # 트윗 게시
        response = client.create_tweet(text=message)
        
        tweet_id = response.data["id"]
        print(f"✅ 트윗 게시 성공!")
        print(f"   Tweet ID: {tweet_id}")
        print(f"   URL: https://twitter.com/i/web/status/{tweet_id}")
        
        return {
            "success": True,
            "tweet_id": tweet_id,
            "url": f"https://twitter.com/i/web/status/{tweet_id}"
        }
        
    except tweepy.TweepyException as e:
        print(f"❌ 트윗 게시 실패: {e}")
        return {"success": False, "error": str(e)}


def main():
    """
    메인 함수 - 트윗을 게시합니다.
    """
    # 트윗 메시지 생성
    message = create_tweet_message()
    
    print("=" * 50)
    print("📝 트윗 내용:")
    print("-" * 50)
    print(message)
    print("-" * 50)
    print(f"글자 수: {len(message)}/280")
    print("=" * 50)
    
    # 글자 수 체크 (트위터 제한: 280자)
    if len(message) > 280:
        print("⚠️ 경고: 트윗이 280자를 초과합니다. 메시지를 줄입니다.")
        message = message[:277] + "..."
    
    # 트윗 게시
    result = post_to_twitter(message)
    
    # GitHub Actions output 설정
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output and result.get("success"):
        with open(github_output, "a") as f:
            f.write(f"tweet_url={result.get('url', '')}\n")
            f.write(f"tweet_id={result.get('tweet_id', '')}\n")
    
    # 결과에 따라 exit code 설정
    if result.get("success"):
        sys.exit(0)
    else:
        # 트위터 포스팅 실패해도 전체 워크플로우는 실패하지 않도록 
        # exit(0)으로 처리 (원하면 exit(1)로 변경 가능)
        print("⚠️ 트위터 포스팅에 실패했지만 워크플로우는 계속됩니다.")
        sys.exit(0)


if __name__ == "__main__":
    main()
