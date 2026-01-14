"""
工具函數模組

功能：
- 日誌管理
- 延遲控制
- 重試裝飾器
- 簽名生成（X-Sign）
- 通用工具函數
"""

import time
import random
import hashlib
import logging
import functools
from datetime import datetime
from typing import Callable, Any, Optional
import asyncio


# ============== 日誌管理 ==============

def setup_logger(
    name: str = "xhs_scraper",
    log_file: str = "scraper.log",
    level: int = logging.INFO
) -> logging.Logger:
    """
    設置日誌記錄器
    
    Args:
        name: 日誌記錄器名稱
        log_file: 日誌文件路徑
        level: 日誌級別
    
    Returns:
        配置好的 Logger 對象
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 避免重複添加 handler
    if logger.handlers:
        return logger
    
    # 文件 handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(level)
    
    # 控制台 handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    
    # 格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


# 創建默認日誌記錄器
logger = setup_logger()


# ============== 延遲控制 ==============

def random_delay(min_seconds: float = 1.0, max_seconds: float = 3.0):
    """
    隨機延遲
    
    Args:
        min_seconds: 最小延遲秒數
        max_seconds: 最大延遲秒數
    """
    delay = random.uniform(min_seconds, max_seconds)
    logger.debug(f"延遲 {delay:.2f} 秒")
    time.sleep(delay)


async def async_random_delay(min_seconds: float = 1.0, max_seconds: float = 3.0):
    """異步隨機延遲"""
    delay = random.uniform(min_seconds, max_seconds)
    logger.debug(f"異步延遲 {delay:.2f} 秒")
    await asyncio.sleep(delay)


def human_like_delay():
    """
    模擬人類行為的延遲
    包含隨機的額外停頓
    """
    # 基礎延遲
    base_delay = random.uniform(1.5, 3.0)
    
    # 10% 機率有額外長停頓（模擬閱讀）
    if random.random() < 0.1:
        base_delay += random.uniform(3.0, 8.0)
    
    # 20% 機率有短停頓
    elif random.random() < 0.2:
        base_delay += random.uniform(0.5, 1.5)
    
    time.sleep(base_delay)


# ============== 重試裝飾器 ==============

def retry(
    max_attempts: int = 3,
    delay: float = 2.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    重試裝飾器
    
    Args:
        max_attempts: 最大重試次數
        delay: 初始延遲時間
        backoff: 延遲增長因子
        exceptions: 需要捕獲的異常類型
    
    Usage:
        @retry(max_attempts=3, delay=2.0)
        def my_function():
            ...
    """
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
                    logger.warning(
                        f"函數 {func.__name__} 第 {attempt}/{max_attempts} 次嘗試失敗: {e}"
                    )
                    
                    if attempt < max_attempts:
                        logger.info(f"等待 {current_delay:.1f} 秒後重試...")
                        time.sleep(current_delay)
                        current_delay *= backoff
            
            logger.error(f"函數 {func.__name__} 在 {max_attempts} 次嘗試後仍然失敗")
            raise last_exception
        
        return wrapper
    return decorator


def async_retry(
    max_attempts: int = 3,
    delay: float = 2.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """異步重試裝飾器"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            current_delay = delay
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    logger.warning(
                        f"異步函數 {func.__name__} 第 {attempt}/{max_attempts} 次嘗試失敗: {e}"
                    )
                    
                    if attempt < max_attempts:
                        logger.info(f"等待 {current_delay:.1f} 秒後重試...")
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
            
            logger.error(f"異步函數 {func.__name__} 在 {max_attempts} 次嘗試後仍然失敗")
            raise last_exception
        
        return wrapper
    return decorator


# ============== 簽名生成 ==============

class XhsSignature:
    """
    小紅書簽名生成器
    
    注意：小紅書的簽名算法可能隨時更新
    這裡提供基礎框架，實際使用時可能需要根據逆向結果調整
    """
    
    @staticmethod
    def generate_x_sign(url: str, data: str = "", a1: str = "") -> str:
        """
        生成 X-Sign 簽名
        
        小紅書的 X-Sign 算法是動態的，通常需要：
        1. 從頁面 JS 中提取算法
        2. 使用 execjs 執行
        3. 或者使用 playwright 直接執行頁面 JS
        
        這裡提供一個佔位實現
        """
        # 基礎簽名邏輯（示例）
        timestamp = str(int(time.time() * 1000))
        sign_str = f"{url}{data}{timestamp}{a1}"
        
        # MD5 哈希（實際算法更複雜）
        md5_hash = hashlib.md5(sign_str.encode()).hexdigest()
        
        return f"X{md5_hash}"
    
    @staticmethod
    def generate_xs(a1: str, timestamp: str = None) -> str:
        """生成 X-S 簽名"""
        if timestamp is None:
            timestamp = str(int(time.time() * 1000))
        
        # 示例實現
        raw = f"{a1}{timestamp}"
        return hashlib.md5(raw.encode()).hexdigest()
    
    @staticmethod
    def generate_xt(timestamp: str = None) -> str:
        """生成 X-T 時間戳"""
        if timestamp is None:
            timestamp = str(int(time.time() * 1000))
        return timestamp


# ============== 文本處理工具 ==============

def clean_text(text: str) -> str:
    """清理文本，去除特殊字符"""
    if not text:
        return ""
    
    # 去除零寬字符
    text = text.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')
    
    # 去除其他不可見字符
    text = ''.join(char for char in text if char.isprintable() or char in '\n\t')
    
    return text.strip()


def extract_numbers(text: str) -> list[int]:
    """從文本中提取數字"""
    import re
    numbers = re.findall(r'\d+', text)
    return [int(n) for n in numbers]


def format_number(num: int) -> str:
    """格式化數字顯示（如 10000 -> 1萬）"""
    if num >= 10000:
        return f"{num/10000:.1f}萬"
    elif num >= 1000:
        return f"{num/1000:.1f}千"
    return str(num)


def parse_engagement_text(text: str) -> int:
    """
    解析互動數文本
    如 "1.2萬" -> 12000, "999" -> 999
    """
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


# ============== URL 處理 ==============

def extract_note_id(url: str) -> Optional[str]:
    """從 URL 中提取筆記 ID"""
    import re
    
    patterns = [
        r'/explore/([a-f0-9]+)',
        r'/discovery/item/([a-f0-9]+)',
        r'note_id=([a-f0-9]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None


def extract_user_id(url: str) -> Optional[str]:
    """從 URL 中提取用戶 ID"""
    import re
    
    patterns = [
        r'/user/profile/([a-f0-9]+)',
        r'user_id=([a-f0-9]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None


def build_search_url(keyword: str, page: int = 1, sort: str = "general") -> str:
    """構建搜索 URL"""
    from urllib.parse import quote
    
    base_url = "https://www.xiaohongshu.com/search_result"
    encoded_keyword = quote(keyword)
    
    # sort: general(綜合), time_descending(最新), popularity_descending(最熱)
    sort_map = {
        "general": "general",
        "new": "time_descending",
        "hot": "popularity_descending"
    }
    
    sort_param = sort_map.get(sort, "general")
    
    return f"{base_url}?keyword={encoded_keyword}&source=web_search_result_notes&page={page}&sort={sort_param}"


# ============== 進度顯示 ==============

class ProgressBar:
    """簡單的進度條"""
    
    def __init__(self, total: int, desc: str = ""):
        self.total = total
        self.current = 0
        self.desc = desc
        self.start_time = time.time()
    
    def update(self, n: int = 1):
        """更新進度"""
        self.current += n
        self._display()
    
    def _display(self):
        """顯示進度"""
        if self.total == 0:
            return
        
        percent = self.current / self.total * 100
        elapsed = time.time() - self.start_time
        
        # 預估剩餘時間
        if self.current > 0:
            eta = elapsed / self.current * (self.total - self.current)
            eta_str = f"ETA: {eta:.0f}s"
        else:
            eta_str = "ETA: --"
        
        bar_length = 30
        filled = int(bar_length * self.current / self.total)
        bar = '█' * filled + '░' * (bar_length - filled)
        
        print(f"\r{self.desc} [{bar}] {percent:.1f}% ({self.current}/{self.total}) {eta_str}", end="", flush=True)
        
        if self.current >= self.total:
            print()  # 換行
    
    def finish(self):
        """完成"""
        self.current = self.total
        self._display()


# ============== 時間工具 ==============

def timestamp_to_datetime(ts: int) -> datetime:
    """時間戳轉日期時間"""
    if ts > 10000000000:  # 毫秒
        ts = ts / 1000
    return datetime.fromtimestamp(ts)


def datetime_to_timestamp(dt: datetime) -> int:
    """日期時間轉時間戳（毫秒）"""
    return int(dt.timestamp() * 1000)


def get_today_str() -> str:
    """獲取今天日期字符串"""
    return datetime.now().strftime("%Y%m%d")


# ============== Cookie 處理 ==============

def parse_cookie_string(cookie_str: str) -> dict:
    """將 cookie 字符串解析為字典"""
    cookies = {}
    for item in cookie_str.split(';'):
        item = item.strip()
        if '=' in item:
            key, value = item.split('=', 1)
            cookies[key.strip()] = value.strip()
    return cookies


def dict_to_cookie_string(cookies: dict) -> str:
    """將字典轉換為 cookie 字符串"""
    return '; '.join(f"{k}={v}" for k, v in cookies.items())


def extract_a1_from_cookie(cookie_str: str) -> Optional[str]:
    """從 cookie 中提取 a1 值"""
    cookies = parse_cookie_string(cookie_str)
    return cookies.get('a1')


if __name__ == "__main__":
    # 測試工具函數
    print("測試工具函數")
    
    # 測試數字解析
    print(f"解析 '1.2萬': {parse_engagement_text('1.2萬')}")
    print(f"解析 '999': {parse_engagement_text('999')}")
    
    # 測試 URL 提取
    url = "https://www.xiaohongshu.com/explore/abc123def"
    print(f"從 URL 提取筆記 ID: {extract_note_id(url)}")
    
    # 測試進度條
    print("\n測試進度條:")
    bar = ProgressBar(10, "處理中")
    for i in range(10):
        time.sleep(0.1)
        bar.update()
    
    # 測試重試裝飾器
    @retry(max_attempts=3, delay=0.5)
    def test_retry():
        import random
        if random.random() < 0.7:
            raise ValueError("模擬錯誤")
        return "成功"
    
    print("\n測試重試裝飾器:")
    try:
        result = test_retry()
        print(f"結果: {result}")
    except ValueError as e:
        print(f"最終失敗: {e}")
