"""
斷點續爬管理模組

功能：
- 保存爬取進度
- 恢復中斷的爬取任務
- 記錄失敗的筆記/作者
- 去重管理
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Set
from dataclasses import dataclass, field, asdict
from utils import logger


@dataclass
class CheckpointData:
    """斷點數據結構"""
    # 任務信息
    task_id: str = ""
    start_time: str = ""
    last_update: str = ""
    
    # 關鍵字進度
    keywords: list[str] = field(default_factory=list)
    current_keyword_index: int = 0
    current_page: int = 1
    
    # 已處理的數據
    processed_note_ids: list[str] = field(default_factory=list)
    processed_author_ids: list[str] = field(default_factory=list)
    
    # 失敗記錄
    failed_note_ids: list[str] = field(default_factory=list)
    failed_author_ids: list[str] = field(default_factory=list)
    
    # 統計信息
    total_notes_found: int = 0
    total_authors_found: int = 0
    total_suppliers_found: int = 0
    
    # 狀態
    status: str = "running"  # running, paused, completed, failed


class CheckpointManager:
    """斷點續爬管理器"""
    
    def __init__(self, checkpoint_file: str = "checkpoint.json"):
        self.checkpoint_file = Path(checkpoint_file)
        self.data = CheckpointData()
        
        # 使用 Set 加速查詢
        self._processed_notes: Set[str] = set()
        self._processed_authors: Set[str] = set()
        self._failed_notes: Set[str] = set()
        self._failed_authors: Set[str] = set()
    
    def init_new_task(self, task_id: str, keywords: list[str]):
        """初始化新任務"""
        self.data = CheckpointData(
            task_id=task_id,
            start_time=datetime.now().isoformat(),
            last_update=datetime.now().isoformat(),
            keywords=keywords,
            current_keyword_index=0,
            current_page=1,
            status="running"
        )
        
        self._processed_notes.clear()
        self._processed_authors.clear()
        self._failed_notes.clear()
        self._failed_authors.clear()
        
        self.save()
        logger.info(f"初始化新任務: {task_id}, 關鍵字數: {len(keywords)}")
    
    def load(self) -> bool:
        """
        加載斷點數據
        
        Returns:
            是否成功加載
        """
        if not self.checkpoint_file.exists():
            logger.info("沒有找到斷點文件")
            return False
        
        try:
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.data = CheckpointData(**data)
            
            # 初始化 Set
            self._processed_notes = set(self.data.processed_note_ids)
            self._processed_authors = set(self.data.processed_author_ids)
            self._failed_notes = set(self.data.failed_note_ids)
            self._failed_authors = set(self.data.failed_author_ids)
            
            logger.info(f"加載斷點成功: 任務 {self.data.task_id}")
            logger.info(f"  - 已處理筆記: {len(self._processed_notes)}")
            logger.info(f"  - 已處理作者: {len(self._processed_authors)}")
            logger.info(f"  - 當前關鍵字: {self.current_keyword}")
            logger.info(f"  - 當前頁碼: {self.data.current_page}")
            
            return True
            
        except Exception as e:
            logger.error(f"加載斷點失敗: {e}")
            return False
    
    def save(self):
        """保存斷點數據"""
        try:
            # 同步 Set 到 list
            self.data.processed_note_ids = list(self._processed_notes)
            self.data.processed_author_ids = list(self._processed_authors)
            self.data.failed_note_ids = list(self._failed_notes)
            self.data.failed_author_ids = list(self._failed_authors)
            
            self.data.last_update = datetime.now().isoformat()
            
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(self.data), f, ensure_ascii=False, indent=2)
            
            logger.debug("斷點數據已保存")
            
        except Exception as e:
            logger.error(f"保存斷點失敗: {e}")
    
    def clear(self):
        """清除斷點數據"""
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
        
        self.data = CheckpointData()
        self._processed_notes.clear()
        self._processed_authors.clear()
        self._failed_notes.clear()
        self._failed_authors.clear()
        
        logger.info("斷點數據已清除")
    
    # ============== 進度管理 ==============
    
    @property
    def current_keyword(self) -> Optional[str]:
        """獲取當前關鍵字"""
        if self.data.current_keyword_index < len(self.data.keywords):
            return self.data.keywords[self.data.current_keyword_index]
        return None
    
    @property
    def is_completed(self) -> bool:
        """是否已完成所有關鍵字"""
        return self.data.current_keyword_index >= len(self.data.keywords)
    
    def advance_keyword(self):
        """前進到下一個關鍵字"""
        self.data.current_keyword_index += 1
        self.data.current_page = 1
        self.save()
        
        if self.current_keyword:
            logger.info(f"切換到關鍵字: {self.current_keyword}")
        else:
            logger.info("所有關鍵字已處理完成")
    
    def advance_page(self):
        """前進到下一頁"""
        self.data.current_page += 1
        self.save()
    
    def set_page(self, page: int):
        """設置當前頁碼"""
        self.data.current_page = page
        self.save()
    
    # ============== 筆記管理 ==============
    
    def is_note_processed(self, note_id: str) -> bool:
        """檢查筆記是否已處理"""
        return note_id in self._processed_notes
    
    def mark_note_processed(self, note_id: str):
        """標記筆記為已處理"""
        self._processed_notes.add(note_id)
        self.data.total_notes_found += 1
    
    def mark_note_failed(self, note_id: str):
        """標記筆記為失敗"""
        self._failed_notes.add(note_id)
    
    def get_failed_notes(self) -> list[str]:
        """獲取失敗的筆記列表"""
        return list(self._failed_notes)
    
    # ============== 作者管理 ==============
    
    def is_author_processed(self, author_id: str) -> bool:
        """檢查作者是否已處理"""
        return author_id in self._processed_authors
    
    def mark_author_processed(self, author_id: str):
        """標記作者為已處理"""
        self._processed_authors.add(author_id)
        self.data.total_authors_found += 1
    
    def mark_author_failed(self, author_id: str):
        """標記作者為失敗"""
        self._failed_authors.add(author_id)
    
    def get_failed_authors(self) -> list[str]:
        """獲取失敗的作者列表"""
        return list(self._failed_authors)
    
    # ============== 供應商管理 ==============
    
    def add_supplier(self):
        """增加供應商計數"""
        self.data.total_suppliers_found += 1
    
    # ============== 狀態管理 ==============
    
    def pause(self):
        """暫停任務"""
        self.data.status = "paused"
        self.save()
        logger.info("任務已暫停")
    
    def resume(self):
        """恢復任務"""
        self.data.status = "running"
        self.save()
        logger.info("任務已恢復")
    
    def complete(self):
        """標記任務完成"""
        self.data.status = "completed"
        self.save()
        logger.info("任務已完成")
    
    def fail(self, reason: str = ""):
        """標記任務失敗"""
        self.data.status = "failed"
        self.save()
        logger.error(f"任務失敗: {reason}")
    
    # ============== 統計信息 ==============
    
    def get_stats(self) -> dict:
        """獲取統計信息"""
        return {
            "task_id": self.data.task_id,
            "status": self.data.status,
            "keywords_total": len(self.data.keywords),
            "keywords_processed": self.data.current_keyword_index,
            "current_keyword": self.current_keyword,
            "current_page": self.data.current_page,
            "notes_processed": len(self._processed_notes),
            "notes_failed": len(self._failed_notes),
            "authors_processed": len(self._processed_authors),
            "authors_failed": len(self._failed_authors),
            "suppliers_found": self.data.total_suppliers_found,
            "start_time": self.data.start_time,
            "last_update": self.data.last_update,
        }
    
    def print_stats(self):
        """打印統計信息"""
        stats = self.get_stats()
        print("\n" + "=" * 50)
        print("爬取進度統計")
        print("=" * 50)
        print(f"任務 ID: {stats['task_id']}")
        print(f"狀態: {stats['status']}")
        print(f"關鍵字進度: {stats['keywords_processed']}/{stats['keywords_total']}")
        print(f"當前關鍵字: {stats['current_keyword']}")
        print(f"當前頁碼: {stats['current_page']}")
        print("-" * 50)
        print(f"已處理筆記: {stats['notes_processed']}")
        print(f"失敗筆記: {stats['notes_failed']}")
        print(f"已處理作者: {stats['authors_processed']}")
        print(f"失敗作者: {stats['authors_failed']}")
        print(f"發現供應商: {stats['suppliers_found']}")
        print("-" * 50)
        print(f"開始時間: {stats['start_time']}")
        print(f"最後更新: {stats['last_update']}")
        print("=" * 50 + "\n")


class SupplierCache:
    """
    供應商緩存
    
    用於在爬取過程中臨時保存供應商數據
    支持增量保存，避免程序中斷時丟失數據
    """
    
    def __init__(self, cache_file: str = "suppliers_cache.json"):
        self.cache_file = Path(cache_file)
        self.suppliers: list[dict] = []
        
        # 加載已有緩存
        self.load()
    
    def load(self):
        """加載緩存"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.suppliers = json.load(f)
                logger.info(f"加載緩存: {len(self.suppliers)} 個供應商")
            except Exception as e:
                logger.error(f"加載緩存失敗: {e}")
                self.suppliers = []
    
    def save(self):
        """保存緩存"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.suppliers, f, ensure_ascii=False, indent=2)
            logger.debug(f"緩存已保存: {len(self.suppliers)} 個供應商")
        except Exception as e:
            logger.error(f"保存緩存失敗: {e}")
    
    def add(self, supplier_data: dict):
        """添加供應商數據"""
        # 檢查是否已存在
        user_id = supplier_data.get('user_id')
        for existing in self.suppliers:
            if existing.get('user_id') == user_id:
                # 更新現有數據
                existing.update(supplier_data)
                self.save()
                return
        
        # 添加新數據
        self.suppliers.append(supplier_data)
        
        # 每添加 10 個保存一次
        if len(self.suppliers) % 10 == 0:
            self.save()
    
    def get_all(self) -> list[dict]:
        """獲取所有供應商數據"""
        return self.suppliers
    
    def clear(self):
        """清除緩存"""
        self.suppliers = []
        if self.cache_file.exists():
            self.cache_file.unlink()
        logger.info("供應商緩存已清除")
    
    def __len__(self) -> int:
        return len(self.suppliers)


if __name__ == "__main__":
    # 測試斷點管理
    print("=== 測試斷點管理 ===")
    
    manager = CheckpointManager("test_checkpoint.json")
    
    # 初始化新任務
    manager.init_new_task(
        task_id="test_001",
        keywords=["童裝代理", "童裝批發", "童裝一件代發"]
    )
    
    # 模擬處理
    manager.mark_note_processed("note_001")
    manager.mark_note_processed("note_002")
    manager.mark_author_processed("author_001")
    manager.add_supplier()
    
    # 前進頁面
    manager.advance_page()
    manager.advance_page()
    
    # 打印統計
    manager.print_stats()
    
    # 測試加載
    print("\n=== 測試加載斷點 ===")
    manager2 = CheckpointManager("test_checkpoint.json")
    manager2.load()
    manager2.print_stats()
    
    # 清理測試文件
    Path("test_checkpoint.json").unlink(missing_ok=True)
    print("\n測試完成")
