#!/usr/bin/env python3
"""
Twitter(X) 자동 포스팅 스크립트
데일리 팟캐스트 생성 후 홍보 트윗을 자동으로 올립니다.
"""

import os
import sys
from datetime import datetime
import tweepy


def create_tweet_message() -> str:
    """
    트윗 메시지를 생성합니다.
    """
    today = datetime.now().strftime("%m월 %d일")
    weekday_kr = ["월", "화", "수", "목", "금", "토", "일"]
    weekday = weekday_kr[datetime.now().weekday()]
    
    # 웹사이트 URL (고정)
    website_url = "https://dailynewspod.com"
    
    # 다양한 메시지 템플릿 (랜덤하게 선택 가능)
    messages = [
        f"🎙️ {today}({weekday}) 데일리 뉴스가 도착했습니다!\n\n오늘의 주요 뉴스를 AI 팟캐스트로 들어보세요.",
        f"☀️ 좋은 아침이에요! {today}({weekday}) 뉴스 팟캐스트가 준비됐습니다.\n\n출근길에 가볍게 들어보세요 🎧",
        f"📰 {today}({weekday}) 오늘의 뉴스 브리핑!\n\nAI가 정리한 주요 뉴스를 팟캐스트로 만나보세요.",
    ]
    
    # 날짜 기반으로 메시지 선택 (매일 다른 메시지)
    message_index = datetime.now().day % len(messages)
    message = messages[message_index]
    
    # 웹사이트 URL 추가
    message += f"\n\n🔗 {website_url}"
    
    # 해시태그 추가
    message += "\n\n#데일리뉴스 #AI팟캐스트 #뉴스브리핑"
    
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
