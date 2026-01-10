# 🖥️ 미니맥 셀프 호스팅 가이드

---

## 1. 초기 설정

```bash
# Xcode CLI Tools
xcode-select --install

# Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"

# 필수 도구
brew install git jq
brew install --cask docker
```

---

## 2. Git & SSH 설정

```bash
# Git 설정
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# SSH 키 생성
ssh-keygen -t ed25519 -C "your.email@example.com"
eval "$(ssh-agent -s)"
ssh-add --apple-use-keychain ~/.ssh/id_ed25519

# GitHub에 등록할 공개키 복사
pbcopy < ~/.ssh/id_ed25519.pub
# → https://github.com/settings/keys 에서 등록
```

---

## 3. 프로젝트 설치 & 실행

```bash
# 클론
mkdir -p ~/workspace && cd ~/workspace
git clone git@github.com:YOUR_USERNAME/podcastfy.git
cd podcastfy

# .env 생성
cat > .env << 'EOF'
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
EOF

# 실행
docker-compose up -d

# 확인
curl http://localhost:8000/health
```

---

## 4. 외부 접근 (Cloudflare Tunnel)

```bash
# 설치 & 로그인
brew install cloudflared
cloudflared tunnel login

# 터널 생성
cloudflared tunnel create news-podcast-api

# 설정 (TUNNEL_ID, YOUR_DOMAIN 수정)
mkdir -p ~/.cloudflared
cat > ~/.cloudflared/config.yml << 'EOF'
tunnel: news-podcast-api
credentials-file: /Users/YOUR_USERNAME/.cloudflared/TUNNEL_ID.json
ingress:
  - hostname: api.yourdomain.com
    service: http://localhost:8000
  - service: http_status:404
EOF

# DNS & 서비스 등록
cloudflared tunnel route dns news-podcast-api api.yourdomain.com
sudo cloudflared service install
sudo launchctl start com.cloudflare.cloudflared
```

---

## 5. 서버 최적화 (잠자기 방지)

```bash
sudo pmset -a sleep 0 disksleep 0 displaysleep 0
sudo pmset -a womp 1 autorestart 1
```

---

## 📞 Quick Reference

```bash
# 서버 관리
docker-compose up -d          # 시작
docker-compose down           # 중지
docker-compose logs -f        # 로그
docker-compose up -d --build  # 재빌드

# 업데이트
git pull && docker-compose up -d --build

# 정리
docker system prune -f
find data/audio -name "*.mp3" -mtime +30 -delete
```

---

## 🔗 API 키 발급

- Gemini: https://aistudio.google.com/apikey
- OpenAI: https://platform.openai.com/api-keys

---

_마지막 업데이트: 2026-01-10_
