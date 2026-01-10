"""
核心爬蟲模組

功能：
- 使用 Playwright (stealth) 進行瀏覽器自動化
- 搜索筆記、翻頁
- 獲取作者頁信息
- 反反爬處理
"""

import asyncio
import json
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
    print("警告: playwright 未安裝，將使用 requests 備用方案")

import requests
from urllib.parse import quote, urlencode

from config import Config
from models import Note, NoteStats, Author, Supplier
from parser import (
    ResponseParser, NoteFilter, ContactExtractor, 
    SupplierClassifier, build_supplier
)
from checkpoint import CheckpointManager, SupplierCache
from utils import (
    logger, random_delay, async_random_delay, human_like_delay,
    retry, async_retry, ProgressBar, parse_engagement_text
)


class PlaywrightScraper:
    """
    基於 Playwright 的爬蟲
    
    使用 stealth 插件避免被檢測
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        self.checkpoint = CheckpointManager()
        self.cache = SupplierCache()
        self.note_filter = NoteFilter(config.filter)
        
        # 已收集的供應商
        self.suppliers: list[Supplier] = []
    
    async def init_browser(self):
        """初始化瀏覽器"""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright 未安裝，請運行: pip install playwright playwright-stealth")
        
        logger.info("初始化 Playwright 瀏覽器...")
        
        playwright = await async_playwright().start()
        
        # 使用 Chromium
        self.browser = await playwright.chromium.launch(
            headless=True,  # 生產環境用 True
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
            ]
        )
        
        # 創建上下文
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=self.config.anti_detect.get_random_ua(),
            locale='zh-CN',
            timezone_id='Asia/Shanghai',
        )
        
        # 設置 Cookie
        if self.config.cookie.get_cookie():
            await self._set_cookies()
        
        # 創建頁面
        self.page = await self.context.new_page()
        
        # 應用 stealth 插件
        await stealth_async(self.page)
        
        # 設置額外的反檢測措施
        await self._setup_anti_detection()
        
        logger.info("瀏覽器初始化完成")
    
    async def _set_cookies(self):
        """設置 Cookie"""
        cookie_str = self.config.cookie.get_cookie()
        if not cookie_str:
            return
        
        cookies = []
        for item in cookie_str.split(';'):
            item = item.strip()
            if '=' in item:
                name, value = item.split('=', 1)
                cookies.append({
                    'name': name.strip(),
                    'value': value.strip(),
                    'domain': '.xiaohongshu.com',
                    'path': '/'
                })
        
        if cookies:
            await self.context.add_cookies(cookies)
            logger.info(f"已設置 {len(cookies)} 個 Cookie")
    
    async def _setup_anti_detection(self):
        """設置反檢測措施"""
        # 注入 JavaScript 來修改 navigator 屬性
        await self.page.add_init_script("""
            // 覆蓋 webdriver 屬性
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // 覆蓋 plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // 覆蓋 languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en']
            });
            
            // 覆蓋 platform
            Object.defineProperty(navigator, 'platform', {
                get: () => 'Win32'
            });
            
            // 修改 chrome 對象
            window.chrome = {
                runtime: {}
            };
            
            // 覆蓋權限查詢
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
    
    async def close(self):
        """關閉瀏覽器"""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        logger.info("瀏覽器已關閉")
    
    async def search_notes(
        self, 
        keyword: str, 
        max_pages: int = 10,
        sort: str = "general"
    ) -> AsyncGenerator[Note, None]:
        """
        搜索筆記
        
        Args:
            keyword: 搜索關鍵字
            max_pages: 最大頁數
            sort: 排序方式
        
        Yields:
            Note 對象
        """
        logger.info(f"開始搜索關鍵字: {keyword}")
        
        # 構建搜索 URL
        search_url = f"https://www.xiaohongshu.com/search_result?keyword={quote(keyword)}&source=web_search_result_notes"
        
        # 訪問搜索頁面
        await self.page.goto(search_url, wait_until='networkidle')
        await async_random_delay(2, 4)
        
        for page_num in range(1, max_pages + 1):
            logger.info(f"處理第 {page_num}/{max_pages} 頁")
            
            try:
                # 等待筆記列表加載
                await self.page.wait_for_selector(
                    'section.note-item, div.note-item, div[data-v-a264b01a]',
                    timeout=10000
                )
                
                # 提取筆記數據
                notes = await self._extract_notes_from_page()
                
                for note in notes:
                    if not self.checkpoint.is_note_processed(note.note_id):
                        yield note
                
                # 翻頁
                if page_num < max_pages:
                    has_next = await self._scroll_and_load_more()
                    if not has_next:
                        logger.info("沒有更多內容")
                        break
                    
                    await async_random_delay(
                        self.config.anti_detect.page_delay_min,
                        self.config.anti_detect.page_delay_max
                    )
                
            except Exception as e:
                logger.error(f"頁面 {page_num} 處理失敗: {e}")
                continue
    
    async def _extract_notes_from_page(self) -> list[Note]:
        """從當前頁面提取筆記"""
        notes = []
        
        # 嘗試多種選擇器
        selectors = [
            'section.note-item',
            'div.note-item', 
            'div[data-v-a264b01a]',
            'a.cover'
        ]
        
        for selector in selectors:
            elements = await self.page.query_selector_all(selector)
            if elements:
                break
        
        if not elements:
            # 嘗試從頁面 JavaScript 獲取數據
            notes = await self._extract_notes_from_js()
            return notes
        
        for element in elements:
            try:
                # 提取筆記 ID
                href = await element.get_attribute('href')
                if href:
                    note_id_match = re.search(r'/explore/([a-f0-9]+)', href)
                    if note_id_match:
                        note_id = note_id_match.group(1)
                    else:
                        continue
                else:
                    continue
                
                # 提取標題
                title_el = await element.query_selector('.title, .note-title, span.title')
                title = await title_el.inner_text() if title_el else ""
                
                # 提取作者
                author_el = await element.query_selector('.author-name, .name, span.name')
                author_name = await author_el.inner_text() if author_el else ""
                
                # 提取互動數據
                likes_el = await element.query_selector('.like-count, .count, span.count')
                likes_text = await likes_el.inner_text() if likes_el else "0"
                likes = parse_engagement_text(likes_text)
                
                note = Note(
                    note_id=note_id,
                    title=title.strip(),
                    author_name=author_name.strip(),
                    stats=NoteStats(likes=likes)
                )
                
                notes.append(note)
                
            except Exception as e:
                logger.debug(f"提取筆記元素失敗: {e}")
                continue
        
        logger.info(f"從頁面提取到 {len(notes)} 條筆記")
        return notes
    
    async def _extract_notes_from_js(self) -> list[Note]:
        """從頁面 JavaScript 數據中提取筆記"""
        notes = []
        
        try:
            # 嘗試獲取頁面中的初始數據
            data = await self.page.evaluate(r"""
                () => {
                    // 嘗試從 window.__INITIAL_STATE__ 獲取
                    if (window.__INITIAL_STATE__) {
                        return window.__INITIAL_STATE__;
                    }
                    // 嘗試從 script 標籤獲取
                    const scripts = document.querySelectorAll('script');
                    for (const script of scripts) {
                        const text = script.textContent;
                        if (text && text.includes('window.__INITIAL_STATE__')) {
                            const match = text.match(/window.__INITIAL_STATE__\s*=\s*({.*?});/s);
                            if (match) {
                                return JSON.parse(match[1]);
                            }
                        }
                    }
                    return null;
                }
            """)
            
            if data:
                # 解析搜索結果
                search_result = data.get('search', {}).get('notes', {}).get('items', [])
                if not search_result:
                    search_result = data.get('searchResult', {}).get('items', [])
                
                for item in search_result:
                    note_card = item.get('noteCard', item)
                    note = Note(
                        note_id=item.get('id', ''),
                        title=note_card.get('displayTitle', '') or note_card.get('title', ''),
                        content=note_card.get('desc', ''),
                        author_id=note_card.get('user', {}).get('userId', ''),
                        author_name=note_card.get('user', {}).get('nickname', ''),
                        stats=NoteStats(
                            likes=note_card.get('interactInfo', {}).get('likedCount', 0),
                            comments=note_card.get('interactInfo', {}).get('commentCount', 0),
                            collects=note_card.get('interactInfo', {}).get('collectedCount', 0),
                        )
                    )
                    notes.append(note)
                
                logger.info(f"從 JS 數據提取到 {len(notes)} 條筆記")
                
        except Exception as e:
            logger.error(f"從 JS 提取數據失敗: {e}")
        
        return notes
    
    async def _scroll_and_load_more(self) -> bool:
        """滾動頁面加載更多內容"""
        try:
            # 記錄當前筆記數
            initial_count = len(await self.page.query_selector_all('section.note-item, div.note-item'))
            
            # 滾動到底部
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)
            
            # 多次滾動確保加載
            for _ in range(3):
                await self.page.evaluate("window.scrollBy(0, 500)")
                await asyncio.sleep(1)
            
            # 檢查是否有新內容
            new_count = len(await self.page.query_selector_all('section.note-item, div.note-item'))
            
            return new_count > initial_count
            
        except Exception as e:
            logger.error(f"滾動加載失敗: {e}")
            return False
    
    async def get_note_detail(self, note_id: str) -> Optional[Note]:
        """獲取筆記詳情"""
        url = f"https://www.xiaohongshu.com/explore/{note_id}"
        
        try:
            await self.page.goto(url, wait_until='networkidle')
            await async_random_delay(1, 2)
            
            # 嘗試從頁面提取數據
            data = await self.page.evaluate("""
                () => {
                    if (window.__INITIAL_STATE__) {
                        return window.__INITIAL_STATE__.note;
                    }
                    return null;
                }
            """)
            
            if data:
                note_data = data.get('noteDetailMap', {})
                if note_data:
                    first_key = list(note_data.keys())[0]
                    note_info = note_data[first_key].get('note', {})
                    
                    note = Note(
                        note_id=note_id,
                        title=note_info.get('title', ''),
                        content=note_info.get('desc', ''),
                        author_id=note_info.get('user', {}).get('userId', ''),
                        author_name=note_info.get('user', {}).get('nickname', ''),
                        stats=NoteStats(
                            likes=note_info.get('interactInfo', {}).get('likedCount', 0),
                            comments=note_info.get('interactInfo', {}).get('commentCount', 0),
                            collects=note_info.get('interactInfo', {}).get('collectedCount', 0),
                        ),
                        raw_data=note_info
                    )
                    return note
            
            # 備用：從 DOM 提取
            title = await self.page.inner_text('div.title, h1.title') or ""
            content = await self.page.inner_text('div.desc, div.content') or ""
            
            return Note(
                note_id=note_id,
                title=title.strip(),
                content=content.strip()
            )
            
        except Exception as e:
            logger.error(f"獲取筆記詳情失敗 {note_id}: {e}")
            return None
    
    async def get_author_info(self, user_id: str) -> Optional[Author]:
        """獲取作者信息"""
        url = f"https://www.xiaohongshu.com/user/profile/{user_id}"
        
        try:
            await self.page.goto(url, wait_until='networkidle')
            await async_random_delay(
                self.config.anti_detect.author_delay_min,
                self.config.anti_detect.author_delay_max
            )
            
            # 從頁面 JS 獲取數據
            data = await self.page.evaluate("""
                () => {
                    if (window.__INITIAL_STATE__) {
                        return window.__INITIAL_STATE__.user;
                    }
                    return null;
                }
            """)
            
            if data:
                user_info = data.get('userPageData', {})
                basic_info = user_info.get('basicInfo', {})
                interactions = user_info.get('interactions', [])
                
                # 解析互動數據
                followers = 0
                notes_count = 0
                likes_count = 0
                
                for item in interactions:
                    if item.get('type') == 'fans':
                        followers = int(item.get('count', 0))
                    elif item.get('type') == 'notes':
                        notes_count = int(item.get('count', 0))
                    elif item.get('type') == 'liked':
                        likes_count = int(item.get('count', 0))
                
                author = Author(
                    user_id=user_id,
                    nickname=basic_info.get('nickname', ''),
                    bio=basic_info.get('desc', ''),
                    followers=followers,
                    notes_count=notes_count,
                    likes_count=likes_count,
                    avatar_url=basic_info.get('imageb', ''),
                    ip_location=basic_info.get('ipLocation', ''),
                    raw_data=user_info
                )
                
                return author
            
            # 備用：從 DOM 提取
            nickname = await self.page.inner_text('.user-name, .nickname') or ""
            bio = await self.page.inner_text('.user-desc, .desc') or ""
            
            return Author(
                user_id=user_id,
                nickname=nickname.strip(),
                bio=bio.strip()
            )
            
        except Exception as e:
            logger.error(f"獲取作者信息失敗 {user_id}: {e}")
            return None
    
    async def run(self, keywords: list[str] = None) -> list[Supplier]:
        """
        運行爬蟲主流程
        
        Args:
            keywords: 搜索關鍵字列表，為 None 則使用配置中的關鍵字
        
        Returns:
            供應商列表
        """
        keywords = keywords or self.config.search.keywords
        
        # 初始化或恢復任務
        if self.checkpoint.load() and not self.checkpoint.is_completed:
            logger.info("恢復之前的爬取任務")
            # 跳過已處理的關鍵字
            start_index = self.checkpoint.data.current_keyword_index
            keywords = keywords[start_index:]
        else:
            self.checkpoint.init_new_task(
                task_id=f"xhs_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                keywords=keywords
            )
        
        try:
            await self.init_browser()
            
            # 首先訪問首頁，建立 session
            await self.page.goto("https://www.xiaohongshu.com", wait_until='networkidle')
            await async_random_delay(2, 4)
            
            # 處理每個關鍵字
            for keyword in keywords:
                logger.info(f"\n{'='*50}")
                logger.info(f"處理關鍵字: {keyword}")
                logger.info(f"{'='*50}")
                
                # 搜索筆記
                async for note in self.search_notes(
                    keyword,
                    max_pages=self.config.search.max_pages_per_keyword
                ):
                    # 過濾筆記
                    if not self.note_filter.is_high_potential(note):
                        continue
                    
                    # 標記已處理
                    self.checkpoint.mark_note_processed(note.note_id)
                    
                    # 獲取作者信息
                    if note.author_id and not self.checkpoint.is_author_processed(note.author_id):
                        author = await self.get_author_info(note.author_id)
                        
                        if author:
                            self.checkpoint.mark_author_processed(note.author_id)
                            
                            # 構建供應商
                            supplier = build_supplier(author, [note], [keyword])
                            
                            # 保存
                            if supplier.contacts or supplier.quality_score > 30:
                                self.suppliers.append(supplier)
                                self.cache.add(supplier.to_dict())
                                self.checkpoint.add_supplier()
                                
                                logger.info(f"發現供應商: {author.nickname} (評分: {supplier.quality_score})")
                        
                        await async_random_delay(1, 2)
                    
                    # 檢查是否達到最大數量
                    if len(self.suppliers) >= self.config.search.max_authors:
                        logger.info(f"已達到最大供應商數量: {self.config.search.max_authors}")
                        break
                
                # 前進到下一個關鍵字
                self.checkpoint.advance_keyword()
                
                if len(self.suppliers) >= self.config.search.max_authors:
                    break
            
            # 完成
            self.checkpoint.complete()
            self.cache.save()
            
            logger.info(f"\n爬取完成! 共發現 {len(self.suppliers)} 個供應商")
            
        except Exception as e:
            logger.error(f"爬取過程出錯: {e}")
            self.checkpoint.fail(str(e))
            raise
        
        finally:
            await self.close()
            self.checkpoint.print_stats()
        
        return self.suppliers


class RequestsScraper:
    """
    基於 Requests 的備用爬蟲
    
    當 Playwright 不可用時使用
    需要有效的 Cookie 和可能的 X-Sign 簽名
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self.checkpoint = CheckpointManager()
        self.cache = SupplierCache()
        self.note_filter = NoteFilter(config.filter)
        self.suppliers: list[Supplier] = []
        
        self._setup_session()
    
    def _setup_session(self):
        """配置 Session"""
        self.session.headers.update(self.config.get_headers())
        
        # 設置 Cookie
        cookie = self.config.cookie.get_cookie()
        if cookie:
            self.session.headers['Cookie'] = cookie
        
        # 設置代理
        proxy = self.config.proxy.get_proxy()
        if proxy:
            self.session.proxies = {
                'http': proxy,
                'https': proxy
            }
    
    @retry(max_attempts=3, delay=5.0)
    def _request(self, url: str, method: str = 'GET', **kwargs) -> requests.Response:
        """發送請求（帶重試）"""
        # 隨機延遲
        random_delay(
            self.config.anti_detect.min_delay,
            self.config.anti_detect.max_delay
        )
        
        # 更新 User-Agent
        self.session.headers['User-Agent'] = self.config.anti_detect.get_random_ua()
        
        response = self.session.request(method, url, **kwargs)
        response.raise_for_status()
        
        return response
    
    def search_notes_api(self, keyword: str, page: int = 1) -> list[Note]:
        """通過 API 搜索筆記"""
        # 小紅書搜索 API
        api_url = "https://edith.xiaohongshu.com/api/sns/web/v1/search/notes"
        
        params = {
            'keyword': keyword,
            'page': page,
            'page_size': 20,
            'search_id': '',
            'sort': 'general',
            'note_type': 0,
        }
        
        headers = {
            **self.config.get_headers(),
            'Content-Type': 'application/json',
        }
        
        try:
            response = self._request(
                api_url,
                method='POST',
                headers=headers,
                json=params
            )
            
            data = response.json()
            
            if data.get('success'):
                return ResponseParser.parse_search_notes(data)
            else:
                logger.error(f"API 返回錯誤: {data.get('msg')}")
                return []
                
        except Exception as e:
            logger.error(f"搜索 API 請求失敗: {e}")
            return []
    
    def get_author_info_api(self, user_id: str) -> Optional[Author]:
        """通過 API 獲取作者信息"""
        api_url = f"https://edith.xiaohongshu.com/api/sns/web/v1/user/otherinfo"
        
        params = {
            'target_user_id': user_id,
        }
        
        try:
            response = self._request(api_url, params=params)
            data = response.json()
            
            if data.get('success'):
                return ResponseParser.parse_author_info(data)
            else:
                logger.error(f"獲取作者信息失敗: {data.get('msg')}")
                return None
                
        except Exception as e:
            logger.error(f"作者 API 請求失敗: {e}")
            return None
    
    def run(self, keywords: list[str] = None) -> list[Supplier]:
        """運行爬蟲"""
        keywords = keywords or self.config.search.keywords
        
        logger.info("使用 Requests 爬蟲（注意：可能需要處理簽名驗證）")
        
        for keyword in keywords:
            logger.info(f"\n處理關鍵字: {keyword}")
            
            for page in range(1, self.config.search.max_pages_per_keyword + 1):
                notes = self.search_notes_api(keyword, page)
                
                if not notes:
                    break
                
                for note in notes:
                    if self.note_filter.is_high_potential(note):
                        if note.author_id and not self.checkpoint.is_author_processed(note.author_id):
                            author = self.get_author_info_api(note.author_id)
                            
                            if author:
                                self.checkpoint.mark_author_processed(note.author_id)
                                supplier = build_supplier(author, [note], [keyword])
                                
                                if supplier.contacts or supplier.quality_score > 30:
                                    self.suppliers.append(supplier)
                                    self.cache.add(supplier.to_dict())
                                    logger.info(f"發現供應商: {author.nickname}")
                
                random_delay(2, 4)
        
        return self.suppliers


def create_scraper(config: Config = None) -> PlaywrightScraper | RequestsScraper:
    """創建爬蟲實例"""
    config = config or Config()
    
    if PLAYWRIGHT_AVAILABLE:
        return PlaywrightScraper(config)
    else:
        logger.warning("Playwright 不可用，使用 Requests 備用方案")
        return RequestsScraper(config)


if __name__ == "__main__":
    # 測試爬蟲
    import asyncio
    
    async def test():
        config = Config()
        config.search.keywords = ["童裝代理"]
        config.search.max_pages_per_keyword = 2
        config.search.max_authors = 10
        
        scraper = PlaywrightScraper(config)
        suppliers = await scraper.run()
        
        print(f"\n找到 {len(suppliers)} 個供應商")
        for s in suppliers[:5]:
            print(f"  - {s.author.nickname}: {s.quality_score} 分")
    
    asyncio.run(test())
