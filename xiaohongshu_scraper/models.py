"""
數據模型定義模組

功能：
- 定義筆記（Note）數據結構
- 定義作者（Author）數據結構
- 定義供應商（Supplier）完整數據結構
- 品質評分計算邏輯
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum


class SupplierType(Enum):
    """供應商類型"""
    UNKNOWN = "未知"
    FACTORY = "工廠/廠家"
    BRAND = "品牌方"
    DISTRIBUTOR = "經銷商/代理"
    INDIVIDUAL = "個人微商"


class ContactType(Enum):
    """聯絡方式類型"""
    WECHAT = "微信"
    PHONE = "電話"
    QQ = "QQ"
    OTHER = "其他"


@dataclass
class ContactInfo:
    """聯絡方式"""
    type: ContactType
    value: str
    source: str = ""  # 來源（簡介/筆記/評論）
    confidence: float = 1.0  # 置信度 0-1
    
    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "value": self.value,
            "source": self.source,
            "confidence": self.confidence
        }


@dataclass
class NoteStats:
    """筆記互動數據"""
    likes: int = 0
    comments: int = 0
    collects: int = 0
    shares: int = 0
    
    @property
    def total_engagement(self) -> int:
        """總互動數"""
        return self.likes + self.comments * 3 + self.collects * 2 + self.shares * 2
    
    def to_dict(self) -> dict:
        return {
            "likes": self.likes,
            "comments": self.comments,
            "collects": self.collects,
            "shares": self.shares,
            "total_engagement": self.total_engagement
        }


@dataclass
class Note:
    """小紅書筆記"""
    note_id: str
    title: str
    content: str = ""
    author_id: str = ""
    author_name: str = ""
    
    # 互動數據
    stats: NoteStats = field(default_factory=NoteStats)
    
    # 時間信息
    publish_time: Optional[datetime] = None
    crawl_time: datetime = field(default_factory=datetime.now)
    
    # 筆記類型
    note_type: str = "normal"  # normal/video
    
    # URL
    url: str = ""
    cover_url: str = ""
    
    # 標籤
    tags: list[str] = field(default_factory=list)
    
    # 是否包含聯絡方式
    has_contact: bool = False
    # 是否包含招商關鍵詞
    has_supplier_keywords: bool = False
    
    # 原始數據
    raw_data: dict = field(default_factory=dict)
    
    @property
    def note_url(self) -> str:
        """生成筆記完整 URL"""
        if self.url:
            return self.url
        return f"https://www.xiaohongshu.com/explore/{self.note_id}"
    
    def to_dict(self) -> dict:
        return {
            "note_id": self.note_id,
            "title": self.title,
            "content": self.content[:200] + "..." if len(self.content) > 200 else self.content,
            "author_id": self.author_id,
            "author_name": self.author_name,
            "stats": self.stats.to_dict(),
            "publish_time": self.publish_time.isoformat() if self.publish_time else None,
            "url": self.note_url,
            "tags": self.tags,
            "has_contact": self.has_contact,
            "has_supplier_keywords": self.has_supplier_keywords
        }


@dataclass
class Author:
    """小紅書作者/博主"""
    user_id: str
    nickname: str
    
    # 簡介
    bio: str = ""
    
    # 粉絲數據
    followers: int = 0
    following: int = 0
    notes_count: int = 0
    likes_count: int = 0  # 獲讚數
    
    # 認證信息
    verified: bool = False
    verified_info: str = ""
    
    # 頭像
    avatar_url: str = ""
    
    # 地區
    location: str = ""
    
    # IP 屬地
    ip_location: str = ""
    
    # 原始數據
    raw_data: dict = field(default_factory=dict)
    
    @property
    def profile_url(self) -> str:
        """生成作者主頁 URL"""
        return f"https://www.xiaohongshu.com/user/profile/{self.user_id}"
    
    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "nickname": self.nickname,
            "bio": self.bio,
            "followers": self.followers,
            "notes_count": self.notes_count,
            "verified": self.verified,
            "verified_info": self.verified_info,
            "location": self.location,
            "ip_location": self.ip_location,
            "profile_url": self.profile_url
        }


@dataclass
class Supplier:
    """供應商完整數據（用於最終輸出）"""
    # 基本信息
    author: Author
    
    # 供應商類型
    supplier_type: SupplierType = SupplierType.UNKNOWN
    
    # 聯絡方式列表
    contacts: list[ContactInfo] = field(default_factory=list)
    
    # 相關筆記
    notes: list[Note] = field(default_factory=list)
    
    # 品質評分 (0-100)
    quality_score: float = 0.0
    
    # 評分細項
    score_details: dict = field(default_factory=dict)
    
    # 來源關鍵字
    source_keywords: list[str] = field(default_factory=list)
    
    # 爬取時間
    crawl_time: datetime = field(default_factory=datetime.now)
    
    # 狀態
    status: str = "pending"  # pending/processed/exported
    
    def calculate_quality_score(self) -> float:
        """
        計算供應商品質評分
        
        評分邏輯:
        1. 互動數據 (30分)
        2. 有效聯絡方式 (25分)
        3. 供應商類型 (15分)
        4. 帳號活躍度 (15分)
        5. 筆記質量 (15分)
        """
        score = 0.0
        details = {}
        
        # 1. 互動數據評分 (30分)
        if self.notes:
            avg_engagement = sum(n.stats.total_engagement for n in self.notes) / len(self.notes)
            engagement_score = min(30, avg_engagement / 100 * 30)
            score += engagement_score
            details['engagement'] = round(engagement_score, 1)
        
        # 2. 聯絡方式評分 (25分)
        contact_score = 0
        wechat_contacts = [c for c in self.contacts if c.type == ContactType.WECHAT]
        if wechat_contacts:
            contact_score = 25  # 有微信給滿分
        elif self.contacts:
            contact_score = 15  # 有其他聯絡方式
        score += contact_score
        details['contact'] = contact_score
        
        # 3. 供應商類型評分 (15分)
        type_scores = {
            SupplierType.FACTORY: 15,
            SupplierType.BRAND: 12,
            SupplierType.DISTRIBUTOR: 8,
            SupplierType.INDIVIDUAL: 5,
            SupplierType.UNKNOWN: 0
        }
        type_score = type_scores.get(self.supplier_type, 0)
        score += type_score
        details['supplier_type'] = type_score
        
        # 4. 帳號活躍度評分 (15分)
        activity_score = 0
        if self.author.notes_count >= 50:
            activity_score = 15
        elif self.author.notes_count >= 20:
            activity_score = 10
        elif self.author.notes_count >= 10:
            activity_score = 5
        score += activity_score
        details['activity'] = activity_score
        
        # 5. 筆記質量評分 (15分) - 基於招商關鍵詞匹配
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
        """獲取主要聯絡方式（優先微信）"""
        wechat = [c for c in self.contacts if c.type == ContactType.WECHAT]
        if wechat:
            return f"微信: {wechat[0].value}"
        if self.contacts:
            c = self.contacts[0]
            return f"{c.type.value}: {c.value}"
        return None
    
    @property
    def best_note(self) -> Optional[Note]:
        """獲取最佳筆記（互動最高）"""
        if not self.notes:
            return None
        return max(self.notes, key=lambda n: n.stats.total_engagement)
    
    def to_dict(self) -> dict:
        """轉換為字典格式"""
        return {
            "user_id": self.author.user_id,
            "nickname": self.author.nickname,
            "profile_url": self.author.profile_url,
            "bio": self.author.bio,
            "followers": self.author.followers,
            "supplier_type": self.supplier_type.value,
            "quality_score": self.quality_score,
            "score_details": self.score_details,
            "primary_contact": self.primary_contact,
            "all_contacts": [c.to_dict() for c in self.contacts],
            "notes_count": len(self.notes),
            "best_note_url": self.best_note.note_url if self.best_note else None,
            "best_note_engagement": self.best_note.stats.total_engagement if self.best_note else 0,
            "source_keywords": self.source_keywords,
            "crawl_time": self.crawl_time.isoformat()
        }
    
    def to_excel_row(self) -> dict:
        """轉換為 Excel 行格式"""
        best_note = self.best_note
        return {
            "排名": 0,  # 會在導出時設定
            "帳號ID": self.author.user_id,
            "暱稱": self.author.nickname,
            "主頁連結": self.author.profile_url,
            "品質評分": self.quality_score,
            "供應商類型": self.supplier_type.value,
            "微信/聯絡方式": self.primary_contact or "未找到",
            "粉絲數": self.author.followers,
            "筆記數": self.author.notes_count,
            "簡介": self.author.bio[:100] if self.author.bio else "",
            "最佳筆記連結": best_note.note_url if best_note else "",
            "最佳筆記互動": best_note.stats.total_engagement if best_note else 0,
            "來源關鍵字": ", ".join(self.source_keywords),
            "IP屬地": self.author.ip_location,
            "爬取時間": self.crawl_time.strftime("%Y-%m-%d %H:%M"),
        }


@dataclass
class CrawlProgress:
    """爬取進度"""
    total_keywords: int = 0
    processed_keywords: int = 0
    total_notes: int = 0
    processed_notes: int = 0
    total_authors: int = 0
    processed_authors: int = 0
    failed_notes: list[str] = field(default_factory=list)
    failed_authors: list[str] = field(default_factory=list)
    
    @property
    def keyword_progress(self) -> float:
        if self.total_keywords == 0:
            return 0
        return self.processed_keywords / self.total_keywords * 100
    
    @property
    def note_progress(self) -> float:
        if self.total_notes == 0:
            return 0
        return self.processed_notes / self.total_notes * 100


if __name__ == "__main__":
    # 測試數據模型
    note = Note(
        note_id="test123",
        title="童裝代理招商",
        content="我們是工廠直供，支持一件代發，微信：abc123",
        stats=NoteStats(likes=100, comments=20, collects=50)
    )
    print("筆記:", note.to_dict())
    
    author = Author(
        user_id="author123",
        nickname="童裝工廠小王",
        bio="專業童裝工廠，支持批發代發，微信：factory888",
        followers=5000
    )
    print("\n作者:", author.to_dict())
    
    supplier = Supplier(
        author=author,
        supplier_type=SupplierType.FACTORY,
        contacts=[ContactInfo(ContactType.WECHAT, "factory888", "簡介")],
        notes=[note]
    )
    supplier.calculate_quality_score()
    print("\n供應商評分:", supplier.quality_score)
    print("評分細項:", supplier.score_details)
    print("Excel 行:", supplier.to_excel_row())
