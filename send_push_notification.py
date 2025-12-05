#!/usr/bin/env python3
"""
OneSignal 푸시 알림 스크립트
타임라인 파일에서 토픽을 추출하여 푸시 알림에 포함시킵니다.
"""

import glob
import json
import os
import re
import sys
from datetime import datetime
from typing import List, Optional
import urllib.request


def load_topics_from_timeline(timeline_dir: str = "data/transcripts") -> Optional[List[str]]:
    """
    타임라인 파일에서 토픽을 로드합니다.
    """
    try:
        timeline_files = glob.glob(os.path.join(timeline_dir, "*timeline*.txt"))
        if not timeline_files:
            print("⚠️ 타임라인 파일을 찾을 수 없습니다")
            return None
        
        latest_file = max(timeline_files, key=os.path.getmtime)
        print(f"📄 타임라인 파일: {latest_file}")
        
        with open(latest_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        topics = []
        for line in content.split('\n'):
            match = re.match(r'\[[\d:]+\]\s*(.+)', line.strip())
            if match:
                topic = match.group(1).strip()
                if topic:
                    topics.append(topic)
        
        return topics if topics else None
        
    except Exception as e:
        print(f"⚠️ 타임라인 로드 실패: {e}")
    return None


def create_notification_content() -> tuple[str, str]:
    """
    푸시 알림 헤딩과 내용을 생성합니다.
    
    Returns:
        (heading, content) 튜플
    """
    today = datetime.now().strftime("%-m월 %-d일")
    
    topics = load_topics_from_timeline()
    
    heading = f"{today} 뉴스가 도착했어요"
    
    if topics:
        # 토픽 최대 3개, 각 20자 제한 (푸시 알림은 짧아야 함)
        topic_lines = []
        for topic in topics[:3]:
            if len(topic) > 20:
                topic = topic[:17] + "..."
            topic_lines.append(f"• {topic}")
        
        content = "\n".join(topic_lines)
    else:
        content = "오늘의 뉴스 팟캐스트를 들어보세요"
    
    return heading, content


def send_push_notification():
    """
    OneSignal API를 사용하여 푸시 알림을 전송합니다.
    실패해도 워크플로우 전체가 실패하지 않도록 처리합니다.
    """
    app_id = os.environ.get("ONESIGNAL_APP_ID")
    api_key = os.environ.get("ONESIGNAL_REST_API_KEY")
    
    if not app_id or not api_key:
        print("⚠️ ONESIGNAL_APP_ID 또는 ONESIGNAL_REST_API_KEY가 설정되지 않았습니다")
        print("⚠️ 푸시 알림을 건너뜁니다")
        sys.exit(0)  # 워크플로우는 계속 진행
    
    heading, content = create_notification_content()
    
    print("=" * 50)
    print("📱 푸시 알림 내용:")
    print(f"   제목: {heading}")
    print(f"   내용:\n{content}")
    print("=" * 50)
    
    payload = {
        "app_id": app_id,
        "included_segments": ["All"],
        "headings": {"ko": heading, "en": heading},
        "contents": {"ko": content, "en": content},
        "url": "https://dailynewspod.com"
    }
    
    headers = {
        "Authorization": f"Basic {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            "https://onesignal.com/api/v1/notifications",
            data=data,
            headers=headers,
            method="POST"
        )
        
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            print(f"✅ 푸시 알림 전송 성공!")
            print(f"   ID: {result.get('id', 'N/A')}")
            print(f"   수신자: {result.get('recipients', 'N/A')}명")
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"⚠️ 푸시 알림 전송 실패: {e.code}")
        print(f"   에러: {error_body}")
        print("⚠️ 워크플로우는 계속 진행됩니다")
        # sys.exit(0) - 실패해도 워크플로우 계속
    except Exception as e:
        print(f"⚠️ 푸시 알림 전송 실패: {e}")
        print("⚠️ 워크플로우는 계속 진행됩니다")
        # sys.exit(0) - 실패해도 워크플로우 계속


if __name__ == "__main__":
    send_push_notification()
