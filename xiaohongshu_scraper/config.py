"""
小紅書爬蟲配置管理模組

功能：
- Cookie 管理（支持多帳號輪換）
- Proxy 代理配置
- 搜索關鍵字設定
- 反爬參數配置
- 過濾規則設定
"""

import os
import json
import random
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProxyConfig:
    """代理配置"""
    enabled: bool = False
    # 代理池列表，格式: ["http://user:pass@ip:port", ...]
    pool: list[str] = field(default_factory=list)
    # 當前使用的代理索引
    current_index: int = 0
    
    def get_proxy(self) -> Optional[str]:
        """獲取一個代理，支持輪換"""
        if not self.enabled or not self.pool:
            return None
        proxy = self.pool[self.current_index % len(self.pool)]
        self.current_index += 1
        return proxy
    
    def get_random_proxy(self) -> Optional[str]:
        """隨機獲取代理"""
        if not self.enabled or not self.pool:
            return None
        return random.choice(self.pool)


@dataclass 
class CookieConfig:
    """Cookie 配置 - 支持多帳號"""
    # Cookie 字符串列表（多帳號輪換用）
    cookies: list[str] = field(default_factory=list)
    current_index: int = 0
    
    def get_cookie(self) -> Optional[str]:
        """獲取當前 cookie"""
        if not self.cookies:
            return None
        return self.cookies[self.current_index % len(self.cookies)]
    
    def rotate(self) -> str:
        """輪換到下一個 cookie"""
        self.current_index += 1
        return self.get_cookie()
    
    def add_cookie(self, cookie: str):
        """添加新的 cookie"""
        if cookie and cookie not in self.cookies:
            self.cookies.append(cookie)


@dataclass
class AntiDetectConfig:
    """反反爬配置"""
    # 請求延遲範圍（秒）
    min_delay: float = 2.0
    max_delay: float = 5.0
    
    # 翻頁額外延遲
    page_delay_min: float = 3.0
    page_delay_max: float = 8.0
    
    # 作者頁訪問延遲
    author_delay_min: float = 2.0
    author_delay_max: float = 4.0
    
    # 最大重試次數
    max_retries: int = 3
    
    # 重試延遲
    retry_delay: float = 5.0
    
    # User-Agent 池
    user_agents: list[str] = field(default_factory=lambda: [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ])
    
    def get_random_ua(self) -> str:
        """獲取隨機 User-Agent"""
        return random.choice(self.user_agents)
    
    def get_random_delay(self) -> float:
        """獲取隨機延遲時間"""
        return random.uniform(self.min_delay, self.max_delay)
    
    def get_page_delay(self) -> float:
        """獲取翻頁延遲"""
        return random.uniform(self.page_delay_min, self.page_delay_max)


@dataclass
class FilterConfig:
    """過濾規則配置"""
    # 最小互動數閾值
    min_likes: int = 50
    min_comments: int = 5
    min_collects: int = 10
    
    # 必須包含的招商關鍵詞（筆記內容）
    supplier_keywords: list[str] = field(default_factory=lambda: [
        "代理", "招商", "一件代發", "批發", "工廠直供", "源頭廠家",
        "誠招", "加盟", "合作", "拿貨", "檔口", "批發價",
        "支持代發", "免費代理", "零風險", "無需囤貨", "一手貨源"
    ])
    
    # 聯絡方式關鍵詞
    contact_keywords: list[str] = field(default_factory=lambda: [
        "微信", "wx", "vx", "v信", "威信", "➕", "加我", 
        "私信", "薇", "徽", "围", "VX", "WX"
    ])
    
    # 供應商類型判斷關鍵詞
    factory_keywords: list[str] = field(default_factory=lambda: [
        "工廠", "廠家", "生產", "自有工廠", "源頭", "檔口", "批發市場"
    ])
    
    brand_keywords: list[str] = field(default_factory=lambda: [
        "品牌", "原創", "設計師", "自主品牌", "獨立設計"
    ])
    
    # 排除關鍵詞（過濾掉買家/消費者）
    exclude_keywords: list[str] = field(default_factory=lambda: [
        "求推薦", "哪裡買", "求鏈接", "好物分享", "開箱", "測評"
    ])


@dataclass
class SearchConfig:
    """搜索配置"""
    # 搜索關鍵字列表
    keywords: list[str] = field(default_factory=lambda: [
        "童裝代理",
        "童裝一件代發 2026",
        "韓版童裝批發招商",
        "童裝廠家直供",
        "童裝源頭工廠",
        "童裝批發 一手貨源",
        "嬰童裝代理",
        "童裝誠招代理",
    ])
    
    # 每個關鍵字最大爬取頁數
    max_pages_per_keyword: int = 10
    
    # 每頁筆記數（小紅書默認約20條）
    notes_per_page: int = 20
    
    # 最大爬取作者數
    max_authors: int = 200
    
    # 排序方式: general(綜合), hot(最熱), new(最新)
    sort_type: str = "general"


class Config:
    """主配置類"""
    
    # 小紅書 API 基礎 URL
    BASE_URL = "https://www.xiaohongshu.com"
    SEARCH_URL = "https://www.xiaohongshu.com/search_result"
    API_URL = "https://edith.xiaohongshu.com"
    
    # 數據保存路徑
    OUTPUT_DIR = Path("output")
    CHECKPOINT_FILE = Path("checkpoint.json")
    LOG_FILE = Path("scraper.log")
    
    def __init__(self, config_file: Optional[str] = None):
        self.proxy = ProxyConfig()
        self.cookie = CookieConfig()
        self.anti_detect = AntiDetectConfig()
        self.filter = FilterConfig()
        self.search = SearchConfig()
        
        # 確保輸出目錄存在
        self.OUTPUT_DIR.mkdir(exist_ok=True)
        
        # 如果有配置文件，加載它
        if config_file and Path(config_file).exists():
            self.load_from_file(config_file)
    
    def load_from_file(self, filepath: str):
        """從 JSON 文件加載配置"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 加載 Cookie
        if 'cookies' in data:
            for cookie in data['cookies']:
                self.cookie.add_cookie(cookie)
        
        # 加載代理
        if 'proxies' in data:
            self.proxy.pool = data['proxies']
            self.proxy.enabled = bool(data['proxies'])
        
        # 加載搜索關鍵字
        if 'keywords' in data:
            self.search.keywords = data['keywords']
        
        # 加載過濾配置
        if 'filter' in data:
            filter_data = data['filter']
            if 'min_likes' in filter_data:
                self.filter.min_likes = filter_data['min_likes']
            if 'min_comments' in filter_data:
                self.filter.min_comments = filter_data['min_comments']
    
    def save_to_file(self, filepath: str):
        """保存配置到 JSON 文件"""
        data = {
            'cookies': self.cookie.cookies,
            'proxies': self.proxy.pool,
            'keywords': self.search.keywords,
            'filter': {
                'min_likes': self.filter.min_likes,
                'min_comments': self.filter.min_comments,
                'min_collects': self.filter.min_collects,
            }
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get_headers(self) -> dict:
        """生成請求頭"""
        return {
            "User-Agent": self.anti_detect.get_random_ua(),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Origin": self.BASE_URL,
            "Referer": f"{self.BASE_URL}/",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
        }


# 創建默認配置模板
def create_config_template():
    """創建配置文件模板"""
    template = {
        "cookies": [
            "# 在這裡填入你的小紅書 Cookie",
            "# 格式: a]t=xxx; web_session=xxx; ...",
            "# 可以添加多個 Cookie 實現帳號輪換"
        ],
        "proxies": [
            "# 代理格式: http://user:pass@ip:port",
            "# 留空則不使用代理"
        ],
        "keywords": [
            "童裝代理",
            "童裝一件代發 2026",
            "韓版童裝批發招商",
            "童裝廠家直供",
            "童裝源頭工廠"
        ],
        "filter": {
            "min_likes": 50,
            "min_comments": 5,
            "min_collects": 10
        }
    }
    
    config_path = Path("config_template.json")
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(template, f, ensure_ascii=False, indent=2)
    
    print(f"配置模板已創建: {config_path}")
    return config_path


if __name__ == "__main__":
    # 測試配置
    config = Config()
    print("默認搜索關鍵字:", config.search.keywords)
    print("隨機延遲:", config.anti_detect.get_random_delay())
    print("隨機 UA:", config.anti_detect.get_random_ua())
    
    # 創建配置模板
    create_config_template()
