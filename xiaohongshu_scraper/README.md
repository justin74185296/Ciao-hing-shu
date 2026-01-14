# 小紅書童裝供應商爬蟲

批量找到「童裝代理/一件代發/招商」供應商帳號，用於香港跨境童裝客戶開發。

## 功能特點

- 🔍 **關鍵字搜索**：支持多關鍵字批量搜索
- 📊 **智能過濾**：自動過濾高潛力筆記（互動高 + 含招商詞）
- 📱 **聯絡方式提取**：自動提取微信、電話等聯絡方式
- 🏭 **供應商分類**：自動判斷工廠/品牌/代理類型
- ⭐ **品質評分**：自訂邏輯計算供應商品質分數
- 📈 **Excel 導出**：按優先級排序，格式美化
- 🔄 **斷點續爬**：支持中斷恢復，不丟失進度
- 🛡️ **反反爬**：隨機延遲、UA 輪換、Stealth 模式

## 安裝

### 1. 環境要求

- Python 3.11+
- Chrome/Chromium 瀏覽器

### 2. 安裝依賴

```bash
cd xiaohongshu_scraper
pip install -r requirements.txt

# 安裝 Playwright 瀏覽器
playwright install chromium
```

### 3. 配置

創建配置文件：

```bash
python main.py --init-config
```

編輯 `config_template.json`，填入你的小紅書 Cookie：

```json
{
  "cookies": [
    "a1=xxx; web_session=xxx; ..."
  ],
  "keywords": [
    "童裝代理",
    "童裝一件代發 2026",
    "韓版童裝批發招商"
  ]
}
```

然後重命名為 `config.json`。

### 獲取 Cookie

1. 登錄小紅書網頁版 (xiaohongshu.com)
2. 打開開發者工具 (F12)
3. 切換到 Network 標籤
4. 刷新頁面，找到任意請求
5. 複製 Request Headers 中的 Cookie 值

## 使用方法

### 基本用法

```bash
# 使用默認配置運行
python main.py

# 指定關鍵字
python main.py --keywords "童裝代理" "童裝批發"

# 指定最大頁數和供應商數量
python main.py --max-pages 5 --max-suppliers 100
```

### 高級選項

```bash
# 從斷點恢復
python main.py --resume

# 清除斷點重新開始
python main.py --clear-checkpoint

# 輸出所有格式（Excel + CSV + JSON）
python main.py --format all

# 調試模式（顯示瀏覽器）
python main.py --debug --no-headless
```

### 命令行參數

| 參數 | 說明 | 默認值 |
|------|------|--------|
| `--keywords`, `-k` | 搜索關鍵字列表 | 配置文件中的值 |
| `--config`, `-c` | 配置文件路徑 | config.json |
| `--max-pages`, `-p` | 每個關鍵字的最大頁數 | 10 |
| `--max-suppliers`, `-s` | 最大供應商數量 | 200 |
| `--output`, `-o` | 輸出目錄 | output |
| `--format`, `-f` | 輸出格式 (excel/csv/json/all) | excel |
| `--resume`, `-r` | 從斷點恢復 | - |
| `--debug` | 調試模式 | - |
| `--cookie` | 小紅書 Cookie | - |

## 輸出說明

### Excel 文件結構

- **全部供應商**：所有供應商列表，按評分排序
- **工廠廠家**：判定為工廠的供應商
- **品牌方**：判定為品牌的供應商
- **經銷代理**：判定為代理商的供應商
- **統計分析**：數據統計和圖表

### 欄位說明

| 欄位 | 說明 |
|------|------|
| 排名 | 按品質評分排序的排名 |
| 帳號ID | 小紅書用戶 ID |
| 暱稱 | 用戶暱稱 |
| 品質評分 | 0-100 分，綜合評估供應商品質 |
| 供應商類型 | 工廠/品牌/經銷/個人 |
| 微信/聯絡方式 | 提取到的聯絡方式 |
| 粉絲數 | 帳號粉絲數 |
| 簡介 | 帳號簡介 |
| 最佳筆記連結 | 互動最高的筆記 |
| IP屬地 | 用戶 IP 屬地 |

### 品質評分邏輯

總分 100 分，由以下維度計算：

1. **互動數據 (30分)**：筆記的點讚、評論、收藏
2. **聯絡方式 (25分)**：有微信滿分，有其他方式 15 分
3. **供應商類型 (15分)**：工廠 > 品牌 > 代理 > 個人
4. **帳號活躍度 (15分)**：筆記數量
5. **筆記質量 (15分)**：招商關鍵詞匹配度

## 項目結構

```
xiaohongshu_scraper/
├── main.py          # 主入口程序
├── scraper.py       # 核心爬蟲邏輯
├── parser.py        # 數據解析（提取聯絡方式）
├── models.py        # 數據模型定義
├── config.py        # 配置管理
├── utils.py         # 工具函數
├── checkpoint.py    # 斷點續爬管理
├── exporter.py      # Excel/CSV/JSON 導出
├── requirements.txt # 依賴包
└── README.md        # 說明文檔
```

## 模組說明

### config.py
配置管理模組，包含：
- Cookie 管理（支持多帳號輪換）
- Proxy 代理配置
- 反爬參數（延遲、UA 池）
- 過濾規則（關鍵詞、閾值）

### models.py
數據模型定義：
- `Note`：筆記數據
- `Author`：作者信息
- `Supplier`：供應商完整數據
- `ContactInfo`：聯絡方式

### parser.py
數據解析模組：
- `ContactExtractor`：提取微信/電話/QQ
- `SupplierClassifier`：判斷供應商類型
- `NoteFilter`：過濾高潛力筆記
- `ResponseParser`：解析 API 響應

### scraper.py
核心爬蟲：
- `PlaywrightScraper`：Playwright 瀏覽器自動化
- `RequestsScraper`：Requests 備用方案

### checkpoint.py
斷點續爬：
- 保存爬取進度
- 記錄已處理的筆記/作者
- 支持中斷恢復

### exporter.py
數據導出：
- Excel 格式（推薦）
- CSV 格式
- JSON 格式

## 注意事項

### 法律聲明

⚠️ 本工具僅供學習研究使用，請遵守小紅書的服務條款和相關法律法規。

### 反爬建議

1. **控制頻率**：不要設置過高的頁數和數量
2. **使用 Cookie**：登錄態更穩定
3. **定期更換 Cookie**：Cookie 可能會過期
4. **使用代理**：避免 IP 被封禁

### 常見問題

**Q: 為什麼找不到供應商？**
A: 檢查 Cookie 是否有效，或降低過濾閾值。

**Q: 程序被中斷了怎麼辦？**
A: 使用 `--resume` 參數從斷點恢復。

**Q: 如何提高成功率？**
A: 使用有效的 Cookie，適當增加延遲時間。

## 更新日誌

### v1.0.0 (2026-01)
- 初始版本
- 支持關鍵字搜索
- 支持聯絡方式提取
- 支持 Excel 導出
- 支持斷點續爬

## License

MIT License
