"""
數據解析模組

功能：
- 從筆記內容中提取聯絡方式（微信優先）
- 判斷供應商類型（工廠/品牌/代理）
- 解析互動數據
- 過濾高潛力筆記
"""

import re
from typing import Optional
from models import (
    Note, NoteStats, Author, Supplier, 
    ContactInfo, ContactType, SupplierType
)
from config import Config, FilterConfig


class ContactExtractor:
    """聯絡方式提取器"""
    
    # 微信號的正則模式
    WECHAT_PATTERNS = [
        # 明確標識微信
        r'(?:微信|wx|vx|v信|威信|薇信|徽信|➕|加我|私聊)[：:\s]*([a-zA-Z0-9_\-]{5,20})',
        r'(?:微信|wx|vx)[：:\s]*([a-zA-Z][a-zA-Z0-9_\-]{4,19})',
        
        # V + 數字/字母組合
        r'[vV][：:\s]*([a-zA-Z0-9_]{6,20})',
        
        # 常見變體
        r'(?:薇|徽|围|衞)[：:\s]*([a-zA-Z0-9_\-]{5,20})',
        
        # 圖片中的文字提取（需要 OCR，這裡用佔位）
    ]
    
    # 電話號碼模式
    PHONE_PATTERNS = [
        r'(?:電話|手機|tel|phone)[：:\s]*(1[3-9]\d{9})',
        r'(?<!\d)(1[3-9]\d{9})(?!\d)',
    ]
    
    # QQ 號模式
    QQ_PATTERNS = [
        r'[qQ][qQ][：:\s]*(\d{5,12})',
        r'(?:扣扣|口口)[：:\s]*(\d{5,12})',
    ]
    
    # 微信號的排除詞（避免誤匹配）
    WECHAT_EXCLUDE = [
        'xiaohongshu', 'weixin', 'wechat', 'official',
        'service', 'support', 'customer', 'admin'
    ]
    
    def __init__(self, config: Optional[FilterConfig] = None):
        self.config = config or FilterConfig()
    
    def extract_wechat(self, text: str) -> list[ContactInfo]:
        """提取微信號"""
        contacts = []
        text_lower = text.lower()
        
        for pattern in self.WECHAT_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                wechat_id = match.group(1).strip()
                
                # 過濾無效的微信號
                if self._is_valid_wechat(wechat_id):
                    # 計算置信度
                    confidence = self._calculate_wechat_confidence(text, match)
                    
                    contacts.append(ContactInfo(
                        type=ContactType.WECHAT,
                        value=wechat_id,
                        source="content",
                        confidence=confidence
                    ))
        
        # 去重
        seen = set()
        unique_contacts = []
        for c in contacts:
            if c.value.lower() not in seen:
                seen.add(c.value.lower())
                unique_contacts.append(c)
        
        return unique_contacts
    
    def _is_valid_wechat(self, wechat_id: str) -> bool:
        """驗證微信號是否有效"""
        # 長度檢查
        if len(wechat_id) < 5 or len(wechat_id) > 20:
            return False
        
        # 排除詞檢查
        wechat_lower = wechat_id.lower()
        for exclude in self.WECHAT_EXCLUDE:
            if exclude in wechat_lower:
                return False
        
        # 必須包含字母（純數字更可能是電話/QQ）
        if not any(c.isalpha() for c in wechat_id):
            return False
        
        # 格式檢查：字母開頭，只包含字母、數字、下劃線、連字符
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_\-]*$', wechat_id):
            # 放寬：也允許數字開頭但必須有字母
            if not re.match(r'^[a-zA-Z0-9_\-]+$', wechat_id):
                return False
        
        return True
    
    def _calculate_wechat_confidence(self, text: str, match: re.Match) -> float:
        """計算微信號的置信度"""
        confidence = 0.5  # 基礎置信度
        
        # 檢查上下文關鍵詞
        context_start = max(0, match.start() - 20)
        context_end = min(len(text), match.end() + 20)
        context = text[context_start:context_end].lower()
        
        # 有明確的微信標識，提高置信度
        if any(kw in context for kw in ['微信', 'wx', 'vx', 'v信', '威信']):
            confidence += 0.3
        
        # 有「加」「聯繫」等動詞
        if any(kw in context for kw in ['加', '聯繫', '私信', '找我']):
            confidence += 0.1
        
        # 有招商相關詞彙
        if any(kw in context for kw in ['代理', '招商', '合作', '批發']):
            confidence += 0.1
        
        return min(1.0, confidence)
    
    def extract_phone(self, text: str) -> list[ContactInfo]:
        """提取電話號碼"""
        contacts = []
        
        for pattern in self.PHONE_PATTERNS:
            matches = re.finditer(pattern, text)
            for match in matches:
                phone = match.group(1)
                contacts.append(ContactInfo(
                    type=ContactType.PHONE,
                    value=phone,
                    source="content",
                    confidence=0.8
                ))
        
        # 去重
        seen = set()
        return [c for c in contacts if c.value not in seen and not seen.add(c.value)]
    
    def extract_qq(self, text: str) -> list[ContactInfo]:
        """提取 QQ 號"""
        contacts = []
        
        for pattern in self.QQ_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                qq = match.group(1)
                contacts.append(ContactInfo(
                    type=ContactType.QQ,
                    value=qq,
                    source="content",
                    confidence=0.7
                ))
        
        # 去重
        seen = set()
        return [c for c in contacts if c.value not in seen and not seen.add(c.value)]
    
    def extract_all(self, text: str, source: str = "content") -> list[ContactInfo]:
        """提取所有聯絡方式"""
        all_contacts = []
        
        # 優先提取微信
        wechats = self.extract_wechat(text)
        for c in wechats:
            c.source = source
        all_contacts.extend(wechats)
        
        # 提取電話
        phones = self.extract_phone(text)
        for c in phones:
            c.source = source
        all_contacts.extend(phones)
        
        # 提取 QQ
        qqs = self.extract_qq(text)
        for c in qqs:
            c.source = source
        all_contacts.extend(qqs)
        
        return all_contacts


class SupplierClassifier:
    """供應商類型分類器"""
    
    def __init__(self, config: Optional[FilterConfig] = None):
        self.config = config or FilterConfig()
    
    def classify(self, author: Author, notes: list[Note]) -> SupplierType:
        """
        根據作者信息和筆記內容判斷供應商類型
        """
        # 合併所有文本
        all_text = author.bio + " " + " ".join(n.title + " " + n.content for n in notes)
        all_text_lower = all_text.lower()
        
        # 計算各類型的匹配分數
        factory_score = self._count_keywords(all_text_lower, self.config.factory_keywords)
        brand_score = self._count_keywords(all_text_lower, self.config.brand_keywords)
        
        # 簡介中的特殊標識
        bio_lower = author.bio.lower()
        
        # 工廠特徵
        if any(kw in bio_lower for kw in ['工廠', '廠家', '生產', '源頭']):
            factory_score += 5
        
        # 品牌特徵
        if any(kw in bio_lower for kw in ['品牌', '原創', '設計師']):
            brand_score += 5
        
        # 認證信息
        if author.verified:
            verified_lower = author.verified_info.lower()
            if '品牌' in verified_lower:
                brand_score += 3
            if '工廠' in verified_lower or '生產' in verified_lower:
                factory_score += 3
        
        # 判斷類型
        if factory_score >= 3 and factory_score > brand_score:
            return SupplierType.FACTORY
        elif brand_score >= 3 and brand_score > factory_score:
            return SupplierType.BRAND
        elif factory_score > 0 or brand_score > 0:
            return SupplierType.DISTRIBUTOR
        else:
            # 根據筆記風格判斷
            if self._is_likely_individual(author, notes):
                return SupplierType.INDIVIDUAL
            return SupplierType.UNKNOWN
    
    def _count_keywords(self, text: str, keywords: list[str]) -> int:
        """計算關鍵詞匹配數"""
        count = 0
        for kw in keywords:
            count += text.count(kw.lower())
        return count
    
    def _is_likely_individual(self, author: Author, notes: list[Note]) -> bool:
        """判斷是否為個人微商"""
        # 粉絲數適中
        if 100 < author.followers < 10000:
            # 筆記數較多
            if author.notes_count > 20:
                return True
        return False


class NoteFilter:
    """筆記過濾器"""
    
    def __init__(self, config: Optional[FilterConfig] = None):
        self.config = config or FilterConfig()
        self.contact_extractor = ContactExtractor(config)
    
    def is_high_potential(self, note: Note) -> bool:
        """
        判斷是否為高潛力筆記
        
        條件：
        1. 互動數達標
        2. 包含招商關鍵詞
        3. 不包含排除關鍵詞
        """
        # 互動數檢查
        if note.stats.likes < self.config.min_likes:
            return False
        
        if note.stats.comments < self.config.min_comments:
            return False
        
        # 關鍵詞檢查
        text = (note.title + " " + note.content).lower()
        
        # 檢查排除關鍵詞
        for kw in self.config.exclude_keywords:
            if kw.lower() in text:
                return False
        
        # 檢查招商關鍵詞
        has_supplier_keyword = any(
            kw.lower() in text 
            for kw in self.config.supplier_keywords
        )
        
        if not has_supplier_keyword:
            return False
        
        note.has_supplier_keywords = True
        
        return True
    
    def has_contact_info(self, note: Note) -> bool:
        """檢查筆記是否包含聯絡方式"""
        text = note.title + " " + note.content
        
        # 檢查聯絡方式關鍵詞
        has_contact_keyword = any(
            kw.lower() in text.lower()
            for kw in self.config.contact_keywords
        )
        
        if has_contact_keyword:
            note.has_contact = True
            return True
        
        # 嘗試提取實際聯絡方式
        contacts = self.contact_extractor.extract_all(text)
        if contacts:
            note.has_contact = True
            return True
        
        return False
    
    def filter_notes(self, notes: list[Note]) -> list[Note]:
        """過濾筆記列表，返回高潛力筆記"""
        filtered = []
        
        for note in notes:
            if self.is_high_potential(note):
                self.has_contact_info(note)  # 標記是否有聯絡方式
                filtered.append(note)
        
        # 按互動數排序
        filtered.sort(key=lambda n: n.stats.total_engagement, reverse=True)
        
        return filtered


class ResponseParser:
    """
    小紅書 API 響應解析器
    
    處理搜索結果和作者頁的 JSON 數據
    """
    
    @staticmethod
    def parse_search_notes(response_data: dict) -> list[Note]:
        """解析搜索結果中的筆記列表"""
        notes = []
        
        # 處理不同的響應格式
        items = response_data.get('data', {}).get('items', [])
        if not items:
            items = response_data.get('items', [])
        
        for item in items:
            try:
                note_card = item.get('note_card') or item.get('noteCard') or item
                
                note = Note(
                    note_id=item.get('id') or note_card.get('note_id', ''),
                    title=note_card.get('title', '') or note_card.get('display_title', ''),
                    content=note_card.get('desc', '') or note_card.get('description', ''),
                    author_id=note_card.get('user', {}).get('user_id', ''),
                    author_name=note_card.get('user', {}).get('nickname', ''),
                    note_type=note_card.get('type', 'normal'),
                    cover_url=note_card.get('cover', {}).get('url', ''),
                    raw_data=item
                )
                
                # 解析互動數據
                interact_info = note_card.get('interact_info', {})
                note.stats = NoteStats(
                    likes=int(interact_info.get('liked_count', 0) or 0),
                    comments=int(interact_info.get('comment_count', 0) or 0),
                    collects=int(interact_info.get('collected_count', 0) or 0),
                    shares=int(interact_info.get('shared_count', 0) or 0)
                )
                
                # 解析標籤
                tag_list = note_card.get('tag_list', [])
                note.tags = [tag.get('name', '') for tag in tag_list if tag.get('name')]
                
                notes.append(note)
                
            except Exception as e:
                print(f"解析筆記失敗: {e}")
                continue
        
        return notes
    
    @staticmethod
    def parse_author_info(response_data: dict) -> Optional[Author]:
        """解析作者信息"""
        try:
            user_data = response_data.get('data', {}).get('user', {})
            if not user_data:
                user_data = response_data.get('user', {})
            
            if not user_data:
                return None
            
            author = Author(
                user_id=user_data.get('user_id', ''),
                nickname=user_data.get('nickname', ''),
                bio=user_data.get('desc', '') or user_data.get('description', ''),
                followers=int(user_data.get('fans', 0) or user_data.get('fansCount', 0) or 0),
                following=int(user_data.get('follows', 0) or 0),
                notes_count=int(user_data.get('notes', 0) or user_data.get('noteCount', 0) or 0),
                likes_count=int(user_data.get('liked', 0) or user_data.get('likedCount', 0) or 0),
                avatar_url=user_data.get('image', '') or user_data.get('avatar', ''),
                location=user_data.get('location', ''),
                ip_location=user_data.get('ip_location', '') or user_data.get('ipLocation', ''),
                raw_data=user_data
            )
            
            # 認證信息
            if user_data.get('verified'):
                author.verified = True
                author.verified_info = user_data.get('verifyInfo', '') or user_data.get('verify_info', '')
            
            return author
            
        except Exception as e:
            print(f"解析作者信息失敗: {e}")
            return None
    
    @staticmethod
    def parse_note_detail(response_data: dict) -> Optional[Note]:
        """解析筆記詳情"""
        try:
            note_data = response_data.get('data', {}).get('note', {})
            if not note_data:
                note_data = response_data.get('note', {})
            
            if not note_data:
                return None
            
            note = Note(
                note_id=note_data.get('note_id', ''),
                title=note_data.get('title', ''),
                content=note_data.get('desc', ''),
                author_id=note_data.get('user', {}).get('user_id', ''),
                author_name=note_data.get('user', {}).get('nickname', ''),
                raw_data=note_data
            )
            
            # 互動數據
            interact_info = note_data.get('interact_info', {})
            note.stats = NoteStats(
                likes=int(interact_info.get('liked_count', 0) or 0),
                comments=int(interact_info.get('comment_count', 0) or 0),
                collects=int(interact_info.get('collected_count', 0) or 0),
            )
            
            return note
            
        except Exception as e:
            print(f"解析筆記詳情失敗: {e}")
            return None


def build_supplier(author: Author, notes: list[Note], source_keywords: list[str]) -> Supplier:
    """
    構建完整的供應商對象
    
    Args:
        author: 作者信息
        notes: 相關筆記列表
        source_keywords: 來源關鍵字
    
    Returns:
        Supplier 對象
    """
    contact_extractor = ContactExtractor()
    classifier = SupplierClassifier()
    
    # 提取聯絡方式
    all_contacts = []
    
    # 從簡介提取
    bio_contacts = contact_extractor.extract_all(author.bio, source="簡介")
    all_contacts.extend(bio_contacts)
    
    # 從筆記提取
    for note in notes:
        note_contacts = contact_extractor.extract_all(
            note.title + " " + note.content, 
            source=f"筆記:{note.note_id}"
        )
        all_contacts.extend(note_contacts)
    
    # 去重（優先保留高置信度的）
    unique_contacts = []
    seen_values = set()
    all_contacts.sort(key=lambda c: c.confidence, reverse=True)
    for c in all_contacts:
        if c.value.lower() not in seen_values:
            seen_values.add(c.value.lower())
            unique_contacts.append(c)
    
    # 分類供應商類型
    supplier_type = classifier.classify(author, notes)
    
    # 創建供應商對象
    supplier = Supplier(
        author=author,
        supplier_type=supplier_type,
        contacts=unique_contacts,
        notes=notes,
        source_keywords=source_keywords
    )
    
    # 計算品質評分
    supplier.calculate_quality_score()
    
    return supplier


if __name__ == "__main__":
    # 測試解析功能
    
    # 測試聯絡方式提取
    extractor = ContactExtractor()
    
    test_texts = [
        "歡迎咨詢，微信：童裝廠家888",
        "加我vx: kidswear_factory",
        "私信我或者➕V：children123",
        "工廠直供，薇信abc_123，支持一件代發",
        "電話：13800138000，微信同號",
    ]
    
    print("=== 測試聯絡方式提取 ===")
    for text in test_texts:
        contacts = extractor.extract_all(text)
        print(f"\n文本: {text}")
        for c in contacts:
            print(f"  - {c.type.value}: {c.value} (置信度: {c.confidence})")
    
    # 測試供應商分類
    print("\n=== 測試供應商分類 ===")
    classifier = SupplierClassifier()
    
    test_author = Author(
        user_id="test",
        nickname="童裝工廠直營",
        bio="專業童裝生產工廠，源頭廠家，支持批發代發",
        followers=5000,
        notes_count=50
    )
    
    test_notes = [
        Note(
            note_id="1",
            title="工廠直供韓版童裝",
            content="我們是源頭工廠，一手貨源，支持一件代發"
        )
    ]
    
    supplier_type = classifier.classify(test_author, test_notes)
    print(f"供應商類型: {supplier_type.value}")
