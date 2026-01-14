# 部署指南 - 多種運行方式

## 🖥️ 方式一：電腦本地運行

```bash
# 安裝依賴
pip install -r requirements.txt
playwright install chromium

# 配置 Cookie
cp config_template.json config.json
# 編輯 config.json 填入 Cookie

# 運行
python main.py
```

---

## 📱 方式二：Telegram Bot（推薦手機用戶）

### 步驟 1：創建 Telegram Bot

1. 打開 Telegram，搜索 `@BotFather`
2. 發送 `/newbot`
3. 按提示設置 Bot 名稱
4. 獲得 Token（類似：`123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`）

### 步驟 2：部署到雲服務器

推薦使用便宜的 VPS：
- Vultr（$5/月）
- DigitalOcean（$4/月）
- AWS Lightsail（$3.5/月）
- 國內：騰訊雲/阿里雲輕量服務器

```bash
# SSH 連接服務器
ssh root@your_server_ip

# 安裝 Python 和依賴
apt update && apt install -y python3 python3-pip

# 下載代碼
git clone https://github.com/your_repo/xiaohongshu_scraper.git
cd xiaohongshu_scraper

# 安裝依賴
pip3 install -r requirements.txt
playwright install chromium
playwright install-deps

# 設置 Token
export TELEGRAM_BOT_TOKEN=your_token_here

# 運行 Bot
python3 bot.py
```

### 步驟 3：後台持續運行

使用 `screen` 或 `systemd`：

```bash
# 使用 screen
screen -S xhs_bot
python3 bot.py
# Ctrl+A+D 退出 screen

# 重新連接
screen -r xhs_bot
```

或創建 systemd 服務：

```bash
# /etc/systemd/system/xhs-bot.service
[Unit]
Description=XHS Supplier Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/xiaohongshu_scraper
Environment=TELEGRAM_BOT_TOKEN=your_token_here
ExecStart=/usr/bin/python3 bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable xhs-bot
systemctl start xhs-bot
```

### 步驟 4：手機使用

打開 Telegram，搜索你的 Bot，發送：

```
/start          - 開始使用
/search 童裝代理  - 開始搜索
/status         - 查看進度
/result         - 獲取結果文件
/top5           - 查看 Top 5
```

---

## ☁️ 方式三：GitHub Actions（免費自動化）

無需服務器，使用 GitHub 免費運行：

### 步驟 1：Fork 倉庫並設置 Secrets

1. Fork 這個倉庫到你的 GitHub
2. 進入 Settings → Secrets → Actions
3. 添加以下 Secrets：
   - `XHS_COOKIE`: 你的小紅書 Cookie
   - `TELEGRAM_BOT_TOKEN`: Bot Token
   - `TELEGRAM_CHAT_ID`: 你的 Telegram ID（可用 @userinfobot 獲取）

### 步驟 2：創建 Workflow

創建 `.github/workflows/scrape.yml`：

```yaml
name: XHS Scraper

on:
  schedule:
    - cron: '0 2 * * *'  # 每天 UTC 2:00（北京 10:00）運行
  workflow_dispatch:  # 手動觸發

jobs:
  scrape:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        playwright install chromium
        playwright install-deps
    
    - name: Run scraper
      env:
        XHS_COOKIE: ${{ secrets.XHS_COOKIE }}
      run: |
        echo '{"cookies": ["'$XHS_COOKIE'"]}' > config.json
        python main.py --max-pages 3 --max-suppliers 50 --format all
    
    - name: Send to Telegram
      env:
        BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
        CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
      run: |
        FILE=$(ls -t output/*.xlsx | head -1)
        curl -F chat_id=$CHAT_ID \
             -F document=@"$FILE" \
             -F caption="📊 今日童裝供應商數據" \
             https://api.telegram.org/bot$BOT_TOKEN/sendDocument
    
    - name: Upload artifacts
      uses: actions/upload-artifact@v4
      with:
        name: scraper-results
        path: output/
```

### 使用方式

- **自動運行**：每天自動執行，結果發送到 Telegram
- **手動觸發**：GitHub Actions 頁面點擊 "Run workflow"

---

## 🐳 方式四：Docker 部署

```dockerfile
# Dockerfile
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt

CMD ["python", "bot.py"]
```

```bash
# 構建和運行
docker build -t xhs-scraper .
docker run -d \
  -e TELEGRAM_BOT_TOKEN=your_token \
  -v $(pwd)/output:/app/output \
  xhs-scraper
```

---

## 📊 各方式對比

| 方式 | 成本 | 難度 | 手機控制 | 推薦場景 |
|-----|------|------|---------|---------|
| 本地運行 | 免費 | ⭐ | ❌ | 偶爾使用 |
| Telegram Bot | $3-5/月 | ⭐⭐ | ✅ | 經常使用 |
| GitHub Actions | 免費 | ⭐⭐ | ⚠️ 有限 | 定時任務 |
| Docker | 依服務器 | ⭐⭐⭐ | ✅ | 專業部署 |

---

## ❓ 常見問題

**Q: 手機能直接運行嗎？**
A: 不能直接運行，但可以通過 Telegram Bot 控制雲端爬蟲。

**Q: 免費方案推薦哪個？**
A: GitHub Actions，每月有 2000 分鐘免費額度。

**Q: 最穩定的方案？**
A: VPS + Telegram Bot，完全自主控制。
