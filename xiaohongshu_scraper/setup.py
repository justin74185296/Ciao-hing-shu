#!/usr/bin/env python3
"""
一鍵安裝腳本
運行這個腳本會自動創建所有需要的文件

使用方法：
1. 在電腦上創建一個資料夾
2. 把這個 setup.py 放進去
3. 運行: python setup.py
"""

import os
import subprocess
import sys

# ============== 所有文件內容 ==============

FILES = {}

FILES["requirements.txt"] = '''# 小紅書童裝供應商爬蟲 - 依賴包
playwright>=1.40.0
playwright-stealth>=1.0.6
requests>=2.31.0
openpyxl>=3.1.2
pandas>=2.1.0
'''

FILES["config.json"] = '''{
  "cookies": [
    "在這裡貼上你的小紅書 Cookie"
  ],
  "proxies": [],
  "keywords": [
    "童裝代理",
    "童裝一件代發",
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
'''

FILES["config.py"] = '''"""配置管理模組"""
import os
import json
import random
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class ProxyConfig:
    enabled: bool = False
    pool: list[str] = field(default_factory=list)
    current_index: int = 0
    
    def get_proxy(self) -> Optional[str]:
        if not self.enabled or not self.pool:
            return None
        proxy = self.pool[self.current_index % len(self.pool)]
        self.current_index += 1
        return proxy

@dataclass 
class CookieConfig:
    cookies: list[str] = field(default_factory=list)
    current_index: int = 0
    
    def get_cookie(self) -> Optional[str]:
        if not self.cookies:
            return None
        return self.cookies[self.current_index % len(self.cookies)]
    
    def add_cookie(self, cookie: str):
        if cookie and cookie not in self.cookies:
            self.cookies.append(cookie)

@dataclass
class AntiDetectConfig:
    min_delay: float = 2.0
    max_delay: float = 5.0
    page_delay_min: float = 3.0
    page_delay_max: float = 8.0
    author_delay_min: float = 2.0
    author_delay_max: float = 4.0
    max_retries: int = 3
    retry_delay: float = 5.0
    user_agents: list[str] = field(default_factory=lambda: [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ])
    
    def get_random_ua(self) -> str:
        return random.choice(self.user_agents)
    
    def get_random_delay(self) -> float:
        return random.uniform(self.min_delay, self.max_delay)
    
    def get_page_delay(self) -> float:
        return random.uniform(self.page_delay_min, self.page_delay_max)

@dataclass
class FilterConfig:
    min_likes: int = 50
    min_comments: int = 5
    min_collects: int = 10
    supplier_keywords: list[str] = field(default_factory=lambda: [
        "代理", "招商", "一件代發", "批發", "工廠直供", "源頭廠家",
        "誠招", "加盟", "合作", "拿貨", "檔口", "批發價",
        "支持代發", "免費代理", "零風險", "無需囤貨", "一手貨源"
    ])
    contact_keywords: list[str] = field(default_factory=lambda: [
        "微信", "wx", "vx", "v信", "威信", "➕", "加我", "私信", "薇", "徽"
    ])
    factory_keywords: list[str] = field(default_factory=lambda: [
        "工廠", "廠家", "生產", "自有工廠", "源頭", "檔口"
    ])
    brand_keywords: list[str] = field(default_factory=lambda: [
        "品牌", "原創", "設計師", "自主品牌"
    ])
    exclude_keywords: list[str] = field(default_factory=lambda: [
        "求推薦", "哪裡買", "求鏈接", "好物分享", "開箱", "測評"
    ])

@dataclass
class SearchConfig:
    keywords: list[str] = field(default_factory=lambda: [
        "童裝代理", "童裝一件代發", "韓版童裝批發招商",
        "童裝廠家直供", "童裝源頭工廠"
    ])
    max_pages_per_keyword: int = 10
    notes_per_page: int = 20
    max_authors: int = 200
    sort_type: str = "general"

class Config:
    BASE_URL = "https://www.xiaohongshu.com"
    OUTPUT_DIR = Path("output")
    
    def __init__(self, config_file: Optional[str] = None):
        self.proxy = ProxyConfig()
        self.cookie = CookieConfig()
        self.anti_detect = AntiDetectConfig()
        self.filter = FilterConfig()
        self.search = SearchConfig()
        self.OUTPUT_DIR.mkdir(exist_ok=True)
        
        if config_file and Path(config_file).exists():
            self.load_from_file(config_file)
    
    def load_from_file(self, filepath: str):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if 'cookies' in data:
            for cookie in data['cookies']:
                if not cookie.startswith('#') and not cookie.startswith('在這裡'):
                    self.cookie.add_cookie(cookie)
        if 'keywords' in data:
            self.search.keywords = data['keywords']
        if 'filter' in data:
            filter_data = data['filter']
            if 'min_likes' in filter_data:
                self.filter.min_likes = filter_data['min_likes']
    
    def get_headers(self) -> dict:
        return {
            "User-Agent": self.anti_detect.get_random_ua(),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Origin": self.BASE_URL,
            "Referer": f"{self.BASE_URL}/",
        }
'''

FILES["models.py"] = '''"""數據模型定義"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum

class SupplierType(Enum):
    UNKNOWN = "未知"
    FACTORY = "工廠/廠家"
    BRAND = "品牌方"
    DISTRIBUTOR = "經銷商/代理"
    INDIVIDUAL = "個人微商"

class ContactType(Enum):
    WECHAT = "微信"
    PHONE = "電話"
    QQ = "QQ"
    OTHER = "其他"

@dataclass
class ContactInfo:
    type: ContactType
    value: str
    source: str = ""
    confidence: float = 1.0
    
    def to_dict(self) -> dict:
        return {"type": self.type.value, "value": self.value, "source": self.source, "confidence": self.confidence}

@dataclass
class NoteStats:
    likes: int = 0
    comments: int = 0
    collects: int = 0
    shares: int = 0
    
    @property
    def total_engagement(self) -> int:
        return self.likes + self.comments * 3 + self.collects * 2 + self.shares * 2
    
    def to_dict(self) -> dict:
        return {"likes": self.likes, "comments": self.comments, "collects": self.collects, "total_engagement": self.total_engagement}

@dataclass
class Note:
    note_id: str
    title: str
    content: str = ""
    author_id: str = ""
    author_name: str = ""
    stats: NoteStats = field(default_factory=NoteStats)
    publish_time: Optional[datetime] = None
    crawl_time: datetime = field(default_factory=datetime.now)
    url: str = ""
    tags: list[str] = field(default_factory=list)
    has_contact: bool = False
    has_supplier_keywords: bool = False
    raw_data: dict = field(default_factory=dict)
    
    @property
    def note_url(self) -> str:
        return self.url or f"https://www.xiaohongshu.com/explore/{self.note_id}"
    
    def to_dict(self) -> dict:
        return {
            "note_id": self.note_id, "title": self.title,
            "content": self.content[:200] + "..." if len(self.content) > 200 else self.content,
            "author_id": self.author_id, "author_name": self.author_name,
            "stats": self.stats.to_dict(), "url": self.note_url,
            "has_contact": self.has_contact, "has_supplier_keywords": self.has_supplier_keywords
        }

@dataclass
class Author:
    user_id: str
    nickname: str
    bio: str = ""
    followers: int = 0
    following: int = 0
    notes_count: int = 0
    likes_count: int = 0
    verified: bool = False
    verified_info: str = ""
    avatar_url: str = ""
    location: str = ""
    ip_location: str = ""
    raw_data: dict = field(default_factory=dict)
    
    @property
    def profile_url(self) -> str:
        return f"https://www.xiaohongshu.com/user/profile/{self.user_id}"
    
    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id, "nickname": self.nickname, "bio": self.bio,
            "followers": self.followers, "notes_count": self.notes_count,
            "ip_location": self.ip_location, "profile_url": self.profile_url
        }

@dataclass
class Supplier:
    author: Author
    supplier_type: SupplierType = SupplierType.UNKNOWN
    contacts: list[ContactInfo] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)
    quality_score: float = 0.0
    score_details: dict = field(default_factory=dict)
    source_keywords: list[str] = field(default_factory=list)
    crawl_time: datetime = field(default_factory=datetime.now)
    
    def calculate_quality_score(self) -> float:
        score = 0.0
        details = {}
        
        if self.notes:
            avg_engagement = sum(n.stats.total_engagement for n in self.notes) / len(self.notes)
            engagement_score = min(30, avg_engagement / 100 * 30)
            score += engagement_score
            details['engagement'] = round(engagement_score, 1)
        
        contact_score = 0
        wechat_contacts = [c for c in self.contacts if c.type == ContactType.WECHAT]
        if wechat_contacts:
            contact_score = 25
        elif self.contacts:
            contact_score = 15
        score += contact_score
        details['contact'] = contact_score
        
        type_scores = {SupplierType.FACTORY: 15, SupplierType.BRAND: 12, SupplierType.DISTRIBUTOR: 8, SupplierType.INDIVIDUAL: 5, SupplierType.UNKNOWN: 0}
        type_score = type_scores.get(self.supplier_type, 0)
        score += type_score
        details['supplier_type'] = type_score
        
        activity_score = 0
        if self.author.notes_count >= 50:
            activity_score = 15
        elif self.author.notes_count >= 20:
            activity_score = 10
        elif self.author.notes_count >= 10:
            activity_score = 5
        score += activity_score
        details['activity'] = activity_score
        
        quality_score = 0
        if self.notes:
            supplier_notes = sum(1 for n in self.notes if n.has_supplier_keywords)
            quality_score = min(15, supplier_notes / len(self.notes) * 15)
        score += quality_score
        details['note_quality'] = round(quality_score, 1)
        
        self.quality_score = round(score, 1)
        self.score_details = details
        return self.quality_score
    
    @property
    def primary_contact(self) -> Optional[str]:
        wechat = [c for c in self.contacts if c.type == ContactType.WECHAT]
        if wechat:
            return f"微信: {wechat[0].value}"
        if self.contacts:
            c = self.contacts[0]
            return f"{c.type.value}: {c.value}"
        return None
    
    @property
    def best_note(self) -> Optional[Note]:
        if not self.notes:
            return None
        return max(self.notes, key=lambda n: n.stats.total_engagement)
    
    def to_dict(self) -> dict:
        return {
            "user_id": self.author.user_id, "nickname": self.author.nickname,
            "profile_url": self.author.profile_url, "bio": self.author.bio,
            "followers": self.author.followers, "supplier_type": self.supplier_type.value,
            "quality_score": self.quality_score, "primary_contact": self.primary_contact,
            "all_contacts": [c.to_dict() for c in self.contacts],
            "best_note_url": self.best_note.note_url if self.best_note else None,
            "source_keywords": self.source_keywords, "crawl_time": self.crawl_time.isoformat()
        }
    
    def to_excel_row(self) -> dict:
        best_note = self.best_note
        return {
            "排名": 0, "帳號ID": self.author.user_id, "暱稱": self.author.nickname,
            "主頁連結": self.author.profile_url, "品質評分": self.quality_score,
            "供應商類型": self.supplier_type.value, "微信/聯絡方式": self.primary_contact or "未找到",
            "粉絲數": self.author.followers, "筆記數": self.author.notes_count,
            "簡介": self.author.bio[:100] if self.author.bio else "",
            "最佳筆記連結": best_note.note_url if best_note else "",
            "最佳筆記互動": best_note.stats.total_engagement if best_note else 0,
            "來源關鍵字": ", ".join(self.source_keywords),
            "IP屬地": self.author.ip_location,
            "爬取時間": self.crawl_time.strftime("%Y-%m-%d %H:%M"),
        }
'''

FILES["utils.py"] = '''"""工具函數"""
import time
import random
import logging
import functools
from typing import Callable, Any

def setup_logger(name: str = "xhs_scraper", log_file: str = "scraper.log", level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if logger.handlers:
        return logger
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger

logger = setup_logger()

def random_delay(min_seconds: float = 1.0, max_seconds: float = 3.0):
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)

def retry(max_attempts: int = 3, delay: float = 2.0, backoff: float = 2.0, exceptions: tuple = (Exception,)):
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            current_delay = delay
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    logger.warning(f"函數 {func.__name__} 第 {attempt}/{max_attempts} 次嘗試失敗: {e}")
                    if attempt < max_attempts:
                        time.sleep(current_delay)
                        current_delay *= backoff
            raise last_exception
        return wrapper
    return decorator

def parse_engagement_text(text: str) -> int:
    if not text:
        return 0
    text = text.strip().lower()
    try:
        if '萬' in text or 'w' in text:
            num = float(text.replace('萬', '').replace('w', ''))
            return int(num * 10000)
        elif '千' in text or 'k' in text:
            num = float(text.replace('千', '').replace('k', ''))
            return int(num * 1000)
        else:
            return int(float(text))
    except ValueError:
        return 0

def parse_cookie_string(cookie_str: str) -> dict:
    cookies = {}
    for item in cookie_str.split(';'):
        item = item.strip()
        if '=' in item:
            key, value = item.split('=', 1)
            cookies[key.strip()] = value.strip()
    return cookies
'''

FILES["parser.py"] = '''"""數據解析模組"""
import re
from typing import Optional
from models import Note, NoteStats, Author, Supplier, ContactInfo, ContactType, SupplierType
from config import FilterConfig

class ContactExtractor:
    WECHAT_PATTERNS = [
        r'(?:微信|wx|vx|v信|威信|薇信|徽信)[：:\s]*([a-zA-Z0-9_\-]{5,20})',
        r'(?:微信|wx|vx)[：:\s]*([a-zA-Z][a-zA-Z0-9_\-]{4,19})',
        r'[vV][：:\s]*([a-zA-Z0-9_]{6,20})',
        r'(?:薇|徽|围)[：:\s]*([a-zA-Z0-9_\-]{5,20})',
    ]
    WECHAT_EXCLUDE = ['xiaohongshu', 'weixin', 'wechat', 'official', 'service']
    
    def __init__(self, config: Optional[FilterConfig] = None):
        self.config = config or FilterConfig()
    
    def extract_wechat(self, text: str) -> list[ContactInfo]:
        contacts = []
        for pattern in self.WECHAT_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                wechat_id = match.group(1).strip()
                if self._is_valid_wechat(wechat_id):
                    contacts.append(ContactInfo(type=ContactType.WECHAT, value=wechat_id, source="content", confidence=0.8))
        seen = set()
        return [c for c in contacts if c.value.lower() not in seen and not seen.add(c.value.lower())]
    
    def _is_valid_wechat(self, wechat_id: str) -> bool:
        if len(wechat_id) < 5 or len(wechat_id) > 20:
            return False
        for exclude in self.WECHAT_EXCLUDE:
            if exclude in wechat_id.lower():
                return False
        if not any(c.isalpha() for c in wechat_id):
            return False
        return True
    
    def extract_all(self, text: str, source: str = "content") -> list[ContactInfo]:
        all_contacts = []
        wechats = self.extract_wechat(text)
        for c in wechats:
            c.source = source
        all_contacts.extend(wechats)
        return all_contacts

class SupplierClassifier:
    def __init__(self, config: Optional[FilterConfig] = None):
        self.config = config or FilterConfig()
    
    def classify(self, author: Author, notes: list[Note]) -> SupplierType:
        all_text = author.bio + " " + " ".join(n.title + " " + n.content for n in notes)
        all_text_lower = all_text.lower()
        factory_score = sum(all_text_lower.count(kw.lower()) for kw in self.config.factory_keywords)
        brand_score = sum(all_text_lower.count(kw.lower()) for kw in self.config.brand_keywords)
        bio_lower = author.bio.lower()
        if any(kw in bio_lower for kw in ['工廠', '廠家', '生產', '源頭']):
            factory_score += 5
        if any(kw in bio_lower for kw in ['品牌', '原創', '設計師']):
            brand_score += 5
        if factory_score >= 3 and factory_score > brand_score:
            return SupplierType.FACTORY
        elif brand_score >= 3:
            return SupplierType.BRAND
        elif factory_score > 0 or brand_score > 0:
            return SupplierType.DISTRIBUTOR
        return SupplierType.UNKNOWN

class NoteFilter:
    def __init__(self, config: Optional[FilterConfig] = None):
        self.config = config or FilterConfig()
        self.contact_extractor = ContactExtractor(config)
    
    def is_high_potential(self, note: Note) -> bool:
        if note.stats.likes < self.config.min_likes:
            return False
        if note.stats.comments < self.config.min_comments:
            return False
        text = (note.title + " " + note.content).lower()
        for kw in self.config.exclude_keywords:
            if kw.lower() in text:
                return False
        has_supplier_keyword = any(kw.lower() in text for kw in self.config.supplier_keywords)
        if not has_supplier_keyword:
            return False
        note.has_supplier_keywords = True
        return True
    
    def has_contact_info(self, note: Note) -> bool:
        text = note.title + " " + note.content
        has_contact_keyword = any(kw.lower() in text.lower() for kw in self.config.contact_keywords)
        if has_contact_keyword:
            note.has_contact = True
            return True
        contacts = self.contact_extractor.extract_all(text)
        if contacts:
            note.has_contact = True
            return True
        return False

def build_supplier(author: Author, notes: list[Note], source_keywords: list[str]) -> Supplier:
    contact_extractor = ContactExtractor()
    classifier = SupplierClassifier()
    all_contacts = []
    bio_contacts = contact_extractor.extract_all(author.bio, source="簡介")
    all_contacts.extend(bio_contacts)
    for note in notes:
        note_contacts = contact_extractor.extract_all(note.title + " " + note.content, source=f"筆記")
        all_contacts.extend(note_contacts)
    seen_values = set()
    unique_contacts = []
    for c in sorted(all_contacts, key=lambda x: x.confidence, reverse=True):
        if c.value.lower() not in seen_values:
            seen_values.add(c.value.lower())
            unique_contacts.append(c)
    supplier_type = classifier.classify(author, notes)
    supplier = Supplier(author=author, supplier_type=supplier_type, contacts=unique_contacts, notes=notes, source_keywords=source_keywords)
    supplier.calculate_quality_score()
    return supplier
'''

FILES["checkpoint.py"] = '''"""斷點續爬管理"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Set
from dataclasses import dataclass, field, asdict
from utils import logger

@dataclass
class CheckpointData:
    task_id: str = ""
    start_time: str = ""
    last_update: str = ""
    keywords: list[str] = field(default_factory=list)
    current_keyword_index: int = 0
    current_page: int = 1
    processed_note_ids: list[str] = field(default_factory=list)
    processed_author_ids: list[str] = field(default_factory=list)
    failed_note_ids: list[str] = field(default_factory=list)
    total_suppliers_found: int = 0
    status: str = "running"

class CheckpointManager:
    def __init__(self, checkpoint_file: str = "checkpoint.json"):
        self.checkpoint_file = Path(checkpoint_file)
        self.data = CheckpointData()
        self._processed_notes: Set[str] = set()
        self._processed_authors: Set[str] = set()
    
    def init_new_task(self, task_id: str, keywords: list[str]):
        self.data = CheckpointData(task_id=task_id, start_time=datetime.now().isoformat(), last_update=datetime.now().isoformat(), keywords=keywords, status="running")
        self._processed_notes.clear()
        self._processed_authors.clear()
        self.save()
    
    def load(self) -> bool:
        if not self.checkpoint_file.exists():
            return False
        try:
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.data = CheckpointData(**data)
            self._processed_notes = set(self.data.processed_note_ids)
            self._processed_authors = set(self.data.processed_author_ids)
            return True
        except:
            return False
    
    def save(self):
        self.data.processed_note_ids = list(self._processed_notes)
        self.data.processed_author_ids = list(self._processed_authors)
        self.data.last_update = datetime.now().isoformat()
        with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(self.data), f, ensure_ascii=False, indent=2)
    
    def clear(self):
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
        self.data = CheckpointData()
        self._processed_notes.clear()
        self._processed_authors.clear()
    
    @property
    def current_keyword(self) -> Optional[str]:
        if self.data.current_keyword_index < len(self.data.keywords):
            return self.data.keywords[self.data.current_keyword_index]
        return None
    
    @property
    def is_completed(self) -> bool:
        return self.data.current_keyword_index >= len(self.data.keywords)
    
    def advance_keyword(self):
        self.data.current_keyword_index += 1
        self.data.current_page = 1
        self.save()
    
    def is_note_processed(self, note_id: str) -> bool:
        return note_id in self._processed_notes
    
    def mark_note_processed(self, note_id: str):
        self._processed_notes.add(note_id)
    
    def is_author_processed(self, author_id: str) -> bool:
        return author_id in self._processed_authors
    
    def mark_author_processed(self, author_id: str):
        self._processed_authors.add(author_id)
    
    def add_supplier(self):
        self.data.total_suppliers_found += 1
    
    def pause(self):
        self.data.status = "paused"
        self.save()
    
    def complete(self):
        self.data.status = "completed"
        self.save()
    
    def get_stats(self) -> dict:
        return {
            "task_id": self.data.task_id, "status": self.data.status,
            "keywords_total": len(self.data.keywords),
            "keywords_processed": self.data.current_keyword_index,
            "current_keyword": self.current_keyword,
            "current_page": self.data.current_page,
            "notes_processed": len(self._processed_notes),
            "authors_processed": len(self._processed_authors),
            "suppliers_found": self.data.total_suppliers_found,
        }
    
    def print_stats(self):
        stats = self.get_stats()
        print("\\n" + "=" * 50)
        print(f"任務: {stats['task_id']} | 狀態: {stats['status']}")
        print(f"關鍵字: {stats['keywords_processed']}/{stats['keywords_total']}")
        print(f"供應商: {stats['suppliers_found']}")
        print("=" * 50)

class SupplierCache:
    def __init__(self, cache_file: str = "suppliers_cache.json"):
        self.cache_file = Path(cache_file)
        self.suppliers: list[dict] = []
        self.load()
    
    def load(self):
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.suppliers = json.load(f)
            except:
                self.suppliers = []
    
    def save(self):
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.suppliers, f, ensure_ascii=False, indent=2)
    
    def add(self, supplier_data: dict):
        user_id = supplier_data.get('user_id')
        for existing in self.suppliers:
            if existing.get('user_id') == user_id:
                existing.update(supplier_data)
                self.save()
                return
        self.suppliers.append(supplier_data)
        if len(self.suppliers) % 10 == 0:
            self.save()
'''

FILES["exporter.py"] = '''"""數據導出模組"""
from pathlib import Path
from datetime import datetime
import json

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

from models import Supplier, SupplierType
from utils import logger

class ExcelExporter:
    COLUMN_WIDTHS = {
        '排名': 8, '帳號ID': 20, '暱稱': 18, '主頁連結': 45, '品質評分': 12,
        '供應商類型': 14, '微信/聯絡方式': 25, '粉絲數': 12, '筆記數': 10,
        '簡介': 40, '最佳筆記連結': 45, '最佳筆記互動': 14, '來源關鍵字': 20,
        'IP屬地': 12, '爬取時間': 18,
    }
    
    def __init__(self, output_dir: str = "output"):
        if not OPENPYXL_AVAILABLE:
            raise RuntimeError("openpyxl 未安裝")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def export(self, suppliers: list[Supplier], filename: str = None) -> str:
        if not suppliers:
            return ""
        if not filename:
            filename = f"童裝供應商_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        output_path = self.output_dir / f"{filename}.xlsx"
        suppliers = sorted(suppliers, key=lambda s: s.quality_score, reverse=True)
        
        wb = Workbook()
        ws = wb.active
        ws.title = "全部供應商"
        
        headers = list(self.COLUMN_WIDTHS.keys())
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True)
        
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center')
            ws.column_dimensions[get_column_letter(col)].width = self.COLUMN_WIDTHS[header]
        
        ws.freeze_panes = 'A2'
        
        for row_idx, supplier in enumerate(suppliers, 2):
            row_data = supplier.to_excel_row()
            row_data['排名'] = row_idx - 1
            for col, header in enumerate(headers, 1):
                value = row_data.get(header, '')
                cell = ws.cell(row=row_idx, column=col, value=value)
                if '連結' in header and value:
                    cell.hyperlink = value
                    cell.font = Font(color="0563C1", underline="single")
        
        wb.save(output_path)
        logger.info(f"Excel 已導出: {output_path}")
        return str(output_path)

class JSONExporter:
    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def export(self, suppliers: list[Supplier], filename: str = None) -> str:
        if not suppliers:
            return ""
        if not filename:
            filename = f"童裝供應商_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        output_path = self.output_dir / f"{filename}.json"
        suppliers = sorted(suppliers, key=lambda s: s.quality_score, reverse=True)
        data = {"export_time": datetime.now().isoformat(), "total_count": len(suppliers), "suppliers": [s.to_dict() for s in suppliers]}
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"JSON 已導出: {output_path}")
        return str(output_path)

def export_suppliers(suppliers: list[Supplier], format: str = "excel", output_dir: str = "output", filename: str = None) -> str:
    if format == 'excel' and OPENPYXL_AVAILABLE:
        return ExcelExporter(output_dir).export(suppliers, filename)
    elif format == 'json' or not OPENPYXL_AVAILABLE:
        return JSONExporter(output_dir).export(suppliers, filename)
    return ""
'''

FILES["scraper.py"] = '''"""核心爬蟲模組"""
import asyncio
import re
from typing import Optional, AsyncGenerator
from datetime import datetime
from pathlib import Path

try:
    from playwright.async_api import async_playwright, Page, Browser, BrowserContext
    from playwright_stealth import stealth_async
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from config import Config
from models import Note, NoteStats, Author, Supplier
from parser import NoteFilter, build_supplier
from checkpoint import CheckpointManager, SupplierCache
from utils import logger, parse_engagement_text

async def async_random_delay(min_s: float = 1.0, max_s: float = 3.0):
    import random
    await asyncio.sleep(random.uniform(min_s, max_s))

class PlaywrightScraper:
    def __init__(self, config: Config):
        self.config = config
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.checkpoint = CheckpointManager()
        self.cache = SupplierCache()
        self.note_filter = NoteFilter(config.filter)
        self.suppliers: list[Supplier] = []
    
    async def init_browser(self):
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright 未安裝")
        logger.info("初始化瀏覽器...")
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled', '--no-sandbox'])
        self.context = await self.browser.new_context(viewport={'width': 1920, 'height': 1080}, user_agent=self.config.anti_detect.get_random_ua(), locale='zh-CN')
        if self.config.cookie.get_cookie():
            await self._set_cookies()
        self.page = await self.context.new_page()
        await stealth_async(self.page)
        logger.info("瀏覽器初始化完成")
    
    async def _set_cookies(self):
        cookie_str = self.config.cookie.get_cookie()
        if not cookie_str:
            return
        cookies = []
        for item in cookie_str.split(';'):
            item = item.strip()
            if '=' in item:
                name, value = item.split('=', 1)
                cookies.append({'name': name.strip(), 'value': value.strip(), 'domain': '.xiaohongshu.com', 'path': '/'})
        if cookies:
            await self.context.add_cookies(cookies)
            logger.info(f"已設置 {len(cookies)} 個 Cookie")
    
    async def close(self):
        if self.page: await self.page.close()
        if self.context: await self.context.close()
        if self.browser: await self.browser.close()
    
    async def search_notes(self, keyword: str, max_pages: int = 10) -> AsyncGenerator[Note, None]:
        from urllib.parse import quote
        logger.info(f"搜索關鍵字: {keyword}")
        search_url = f"https://www.xiaohongshu.com/search_result?keyword={quote(keyword)}&source=web_search_result_notes"
        await self.page.goto(search_url, wait_until='networkidle')
        await async_random_delay(2, 4)
        
        for page_num in range(1, max_pages + 1):
            logger.info(f"處理第 {page_num}/{max_pages} 頁")
            try:
                await self.page.wait_for_selector('section.note-item, div.note-item, a.cover', timeout=10000)
                notes = await self._extract_notes_from_page()
                for note in notes:
                    if not self.checkpoint.is_note_processed(note.note_id):
                        yield note
                if page_num < max_pages:
                    await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await async_random_delay(self.config.anti_detect.page_delay_min, self.config.anti_detect.page_delay_max)
            except Exception as e:
                logger.error(f"頁面 {page_num} 處理失敗: {e}")
                continue
    
    async def _extract_notes_from_page(self) -> list[Note]:
        notes = []
        try:
            data = await self.page.evaluate("""() => {
                if (window.__INITIAL_STATE__) return window.__INITIAL_STATE__;
                return null;
            }""")
            if data:
                items = data.get('search', {}).get('notes', {}).get('items', [])
                if not items:
                    items = data.get('searchResult', {}).get('items', [])
                for item in items:
                    note_card = item.get('noteCard', item)
                    note = Note(
                        note_id=item.get('id', ''),
                        title=note_card.get('displayTitle', '') or note_card.get('title', ''),
                        content=note_card.get('desc', ''),
                        author_id=note_card.get('user', {}).get('userId', ''),
                        author_name=note_card.get('user', {}).get('nickname', ''),
                        stats=NoteStats(
                            likes=int(note_card.get('interactInfo', {}).get('likedCount', 0) or 0),
                            comments=int(note_card.get('interactInfo', {}).get('commentCount', 0) or 0),
                            collects=int(note_card.get('interactInfo', {}).get('collectedCount', 0) or 0),
                        )
                    )
                    notes.append(note)
        except Exception as e:
            logger.debug(f"從 JS 提取失敗: {e}")
        logger.info(f"提取到 {len(notes)} 條筆記")
        return notes
    
    async def get_author_info(self, user_id: str) -> Optional[Author]:
        url = f"https://www.xiaohongshu.com/user/profile/{user_id}"
        try:
            await self.page.goto(url, wait_until='networkidle')
            await async_random_delay(self.config.anti_detect.author_delay_min, self.config.anti_detect.author_delay_max)
            data = await self.page.evaluate("""() => {
                if (window.__INITIAL_STATE__) return window.__INITIAL_STATE__.user;
                return null;
            }""")
            if data:
                user_info = data.get('userPageData', {})
                basic_info = user_info.get('basicInfo', {})
                interactions = user_info.get('interactions', [])
                followers, notes_count = 0, 0
                for item in interactions:
                    if item.get('type') == 'fans': followers = int(item.get('count', 0))
                    elif item.get('type') == 'notes': notes_count = int(item.get('count', 0))
                return Author(user_id=user_id, nickname=basic_info.get('nickname', ''), bio=basic_info.get('desc', ''), followers=followers, notes_count=notes_count, ip_location=basic_info.get('ipLocation', ''))
        except Exception as e:
            logger.error(f"獲取作者信息失敗 {user_id}: {e}")
        return None
    
    async def run(self, keywords: list[str] = None) -> list[Supplier]:
        keywords = keywords or self.config.search.keywords
        self.checkpoint.init_new_task(task_id=f"xhs_{datetime.now().strftime('%Y%m%d_%H%M%S')}", keywords=keywords)
        
        try:
            await self.init_browser()
            await self.page.goto("https://www.xiaohongshu.com", wait_until='networkidle')
            await async_random_delay(2, 4)
            
            for keyword in keywords:
                logger.info(f"\\n{'='*50}\\n處理關鍵字: {keyword}\\n{'='*50}")
                async for note in self.search_notes(keyword, max_pages=self.config.search.max_pages_per_keyword):
                    if not self.note_filter.is_high_potential(note):
                        continue
                    self.checkpoint.mark_note_processed(note.note_id)
                    if note.author_id and not self.checkpoint.is_author_processed(note.author_id):
                        author = await self.get_author_info(note.author_id)
                        if author:
                            self.checkpoint.mark_author_processed(note.author_id)
                            supplier = build_supplier(author, [note], [keyword])
                            if supplier.contacts or supplier.quality_score > 30:
                                self.suppliers.append(supplier)
                                self.cache.add(supplier.to_dict())
                                self.checkpoint.add_supplier()
                                logger.info(f"發現供應商: {author.nickname} (評分: {supplier.quality_score})")
                        await async_random_delay(1, 2)
                    if len(self.suppliers) >= self.config.search.max_authors:
                        break
                self.checkpoint.advance_keyword()
                if len(self.suppliers) >= self.config.search.max_authors:
                    break
            
            self.checkpoint.complete()
            self.cache.save()
            logger.info(f"\\n爬取完成! 共發現 {len(self.suppliers)} 個供應商")
        except Exception as e:
            logger.error(f"爬取出錯: {e}")
            raise
        finally:
            await self.close()
            self.checkpoint.print_stats()
        return self.suppliers
'''

FILES["main.py"] = '''#!/usr/bin/env python3
"""小紅書童裝供應商爬蟲 - 主程序"""
import asyncio
import argparse
import sys
from pathlib import Path
from datetime import datetime

from config import Config
from checkpoint import CheckpointManager
from exporter import export_suppliers
from utils import logger

def parse_args():
    parser = argparse.ArgumentParser(description="小紅書童裝供應商爬蟲")
    parser.add_argument('--keywords', '-k', nargs='+', help='搜索關鍵字列表')
    parser.add_argument('--config', '-c', default='config.json', help='配置文件路徑')
    parser.add_argument('--max-pages', '-p', type=int, default=10, help='每個關鍵字最大頁數')
    parser.add_argument('--max-suppliers', '-s', type=int, default=200, help='最大供應商數量')
    parser.add_argument('--output', '-o', default='output', help='輸出目錄')
    parser.add_argument('--format', '-f', choices=['excel', 'json', 'all'], default='excel', help='輸出格式')
    parser.add_argument('--resume', '-r', action='store_true', help='從斷點恢復')
    parser.add_argument('--clear-checkpoint', action='store_true', help='清除斷點')
    parser.add_argument('--cookie', help='小紅書 Cookie')
    return parser.parse_args()

def print_banner():
    print("""
╔═══════════════════════════════════════════════════════╗
║     小紅書童裝供應商爬蟲 v1.0                          ║
║     批量找到代理/一件代發/招商供應商                    ║
╚═══════════════════════════════════════════════════════╝
    """)

async def run_scraper(config: Config) -> list:
    try:
        from scraper import PlaywrightScraper, PLAYWRIGHT_AVAILABLE
        if not PLAYWRIGHT_AVAILABLE:
            print("錯誤: Playwright 未安裝")
            print("請運行: pip install playwright playwright-stealth")
            print("然後運行: playwright install chromium")
            return []
        scraper = PlaywrightScraper(config)
        return await scraper.run()
    except Exception as e:
        logger.error(f"爬取出錯: {e}")
        return []

def main():
    args = parse_args()
    print_banner()
    
    config = Config()
    config_file = Path(args.config)
    if config_file.exists():
        config.load_from_file(str(config_file))
        logger.info(f"已加載配置: {config_file}")
    
    if args.keywords:
        config.search.keywords = args.keywords
    if args.max_pages:
        config.search.max_pages_per_keyword = args.max_pages
    if args.max_suppliers:
        config.search.max_authors = args.max_suppliers
    if args.cookie:
        config.cookie.add_cookie(args.cookie)
    
    config.OUTPUT_DIR = Path(args.output)
    config.OUTPUT_DIR.mkdir(exist_ok=True)
    
    checkpoint = CheckpointManager()
    if args.clear_checkpoint:
        checkpoint.clear()
    
    print(f"\\n搜索關鍵字: {config.search.keywords}")
    print(f"最大頁數: {config.search.max_pages_per_keyword}")
    print(f"最大供應商: {config.search.max_authors}")
    print(f"Cookie: {'已設置' if config.cookie.get_cookie() else '未設置 ⚠️'}\\n")
    
    if not config.cookie.get_cookie():
        print("⚠️  警告: 未設置 Cookie，請先獲取 Cookie！")
        print("   1. 登錄 xiaohongshu.com")
        print("   2. F12 → Network → 複製 Cookie")
        print("   3. 貼到 config.json 文件中\\n")
    
    try:
        input("按 Enter 開始爬取（Ctrl+C 取消）...")
    except KeyboardInterrupt:
        print("\\n已取消")
        return
    
    print("\\n開始爬取...\\n")
    
    try:
        suppliers = asyncio.run(run_scraper(config))
    except KeyboardInterrupt:
        print("\\n用戶中斷")
        return
    
    if suppliers:
        output_files = []
        if args.format in ['excel', 'all']:
            path = export_suppliers(suppliers, format='excel', output_dir=args.output)
            if path: output_files.append(path)
        if args.format in ['json', 'all']:
            path = export_suppliers(suppliers, format='json', output_dir=args.output)
            if path: output_files.append(path)
        
        print(f"\\n✅ 完成! 找到 {len(suppliers)} 個供應商")
        for f in output_files:
            print(f"   📄 {f}")
    else:
        print("\\n未找到供應商，請檢查 Cookie 是否有效")

if __name__ == "__main__":
    main()
'''

# ============== 安裝腳本主邏輯 ==============

def main():
    print("""
╔═══════════════════════════════════════════════════════╗
║     小紅書童裝供應商爬蟲 - 一鍵安裝                     ║
╚═══════════════════════════════════════════════════════╝
    """)
    
    # 創建文件
    print("📁 創建項目文件...")
    for filename, content in FILES.items():
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"   ✓ {filename}")
    
    # 創建 output 目錄
    os.makedirs("output", exist_ok=True)
    print("   ✓ output/")
    
    print("\n📦 安裝 Python 依賴...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", 
            "playwright", "playwright-stealth", "requests", "openpyxl", "pandas"])
        print("   ✓ 依賴安裝完成")
    except:
        print("   ⚠️ 依賴安裝失敗，請手動運行: pip install -r requirements.txt")
    
    print("\n🌐 安裝 Chromium 瀏覽器...")
    try:
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        print("   ✓ 瀏覽器安裝完成")
    except:
        print("   ⚠️ 瀏覽器安裝失敗，請手動運行: playwright install chromium")
    
    print("""
╔═══════════════════════════════════════════════════════╗
║  ✅ 安裝完成！                                         ║
╠═══════════════════════════════════════════════════════╣
║                                                       ║
║  下一步：                                              ║
║  1. 獲取小紅書 Cookie（見下方說明）                     ║
║  2. 編輯 config.json，貼上 Cookie                      ║
║  3. 運行: python main.py                              ║
║                                                       ║
╠═══════════════════════════════════════════════════════╣
║  📌 獲取 Cookie 方法：                                 ║
║  1. 打開 Chrome，訪問 xiaohongshu.com 並登錄           ║
║  2. 按 F12 打開開發者工具                              ║
║  3. 點擊 Network 標籤                                  ║
║  4. 刷新頁面，點擊任意請求                              ║
║  5. 找到 Request Headers → Cookie                     ║
║  6. 複製整串 Cookie 內容                               ║
║                                                       ║
╚═══════════════════════════════════════════════════════╝
    """)

if __name__ == "__main__":
    main()
