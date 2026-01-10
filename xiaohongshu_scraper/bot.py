#!/usr/bin/env python3
"""
Telegram Bot 模組

功能：
- 手機遠程控制爬蟲
- 接收爬取結果
- 查詢進度

使用方法：
1. 在 @BotFather 創建 Bot，獲取 Token
2. 設置環境變量: export TELEGRAM_BOT_TOKEN=your_token
3. 運行: python bot.py
"""

import os
import asyncio
import logging
from datetime import datetime
from pathlib import Path

# Telegram Bot 依賴
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import (
        Application, CommandHandler, CallbackQueryHandler,
        ContextTypes, MessageHandler, filters
    )
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("請安裝 python-telegram-bot: pip install python-telegram-bot")

from config import Config
from checkpoint import CheckpointManager, SupplierCache
from exporter import export_suppliers

# 配置日誌
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 全局變量
config = Config()
checkpoint = CheckpointManager()
cache = SupplierCache()
scraper_task = None


class TelegramBot:
    """Telegram Bot 控制器"""
    
    def __init__(self, token: str):
        self.token = token
        self.app = None
        self.authorized_users = set()  # 授權用戶 ID
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """開始命令"""
        user_id = update.effective_user.id
        
        welcome_text = """
🔍 **小紅書童裝供應商爬蟲 Bot**

歡迎使用！以下是可用命令：

📋 **基本命令**
/search <關鍵字> - 開始搜索
/status - 查看爬取狀態
/stop - 停止爬取
/result - 獲取最新結果

⚙️ **設置命令**
/setpages <數量> - 設置每個關鍵字最大頁數
/setmax <數量> - 設置最大供應商數量
/keywords - 查看/設置關鍵字列表

📊 **數據命令**
/stats - 統計信息
/top5 - 查看 Top 5 供應商
/export - 導出數據文件

💡 **快速開始**
發送: /search 童裝代理
        """
        
        await update.message.reply_text(
            welcome_text, 
            parse_mode='Markdown'
        )
        
        # 記錄用戶
        self.authorized_users.add(user_id)
        logger.info(f"用戶 {user_id} 開始使用 Bot")
    
    async def search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """開始搜索"""
        global scraper_task
        
        # 獲取關鍵字
        if context.args:
            keywords = context.args
        else:
            keywords = config.search.keywords[:3]  # 默認前3個
        
        await update.message.reply_text(
            f"🚀 開始搜索...\n\n"
            f"關鍵字: {', '.join(keywords)}\n"
            f"最大頁數: {config.search.max_pages_per_keyword}\n"
            f"最大供應商: {config.search.max_authors}\n\n"
            f"⏳ 預計需要 5-30 分鐘，完成後會通知你"
        )
        
        # 啟動爬蟲任務
        scraper_task = asyncio.create_task(
            self._run_scraper(update, keywords)
        )
    
    async def _run_scraper(self, update: Update, keywords: list):
        """運行爬蟲（後台任務）"""
        try:
            from scraper import PlaywrightScraper, PLAYWRIGHT_AVAILABLE
            
            if not PLAYWRIGHT_AVAILABLE:
                await update.message.reply_text(
                    "❌ Playwright 未安裝，無法運行爬蟲\n"
                    "請在服務器上運行: pip install playwright && playwright install chromium"
                )
                return
            
            scraper = PlaywrightScraper(config)
            suppliers = await scraper.run(keywords)
            
            # 發送結果
            if suppliers:
                # 導出文件
                excel_path = export_suppliers(
                    suppliers, 
                    format='excel',
                    output_dir='output'
                )
                
                # 發送摘要
                summary = self._generate_summary(suppliers)
                await update.message.reply_text(summary, parse_mode='Markdown')
                
                # 發送文件
                if Path(excel_path).exists():
                    await update.message.reply_document(
                        document=open(excel_path, 'rb'),
                        filename=Path(excel_path).name,
                        caption="📊 完整數據文件"
                    )
            else:
                await update.message.reply_text(
                    "😅 沒有找到符合條件的供應商\n"
                    "建議：嘗試其他關鍵字或降低過濾閾值"
                )
                
        except asyncio.CancelledError:
            await update.message.reply_text("⏹ 爬取已停止")
        except Exception as e:
            logger.error(f"爬取出錯: {e}")
            await update.message.reply_text(f"❌ 爬取出錯: {e}")
    
    def _generate_summary(self, suppliers: list) -> str:
        """生成結果摘要"""
        from models import SupplierType
        
        with_wechat = sum(1 for s in suppliers if s.primary_contact and '微信' in s.primary_contact)
        
        # 類型統計
        type_counts = {}
        for s in suppliers:
            type_name = s.supplier_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        # Top 5
        top_5 = sorted(suppliers, key=lambda s: s.quality_score, reverse=True)[:5]
        top_5_text = "\n".join([
            f"{i}. **{s.author.nickname}** ({s.quality_score:.0f}分)\n"
            f"   📱 {s.primary_contact or '無聯絡方式'}"
            for i, s in enumerate(top_5, 1)
        ])
        
        return f"""
✅ **爬取完成！**

📊 **統計數據**
• 總供應商數: {len(suppliers)}
• 有微信聯絡方式: {with_wechat}

📦 **類型分佈**
{chr(10).join([f'• {k}: {v}' for k, v in type_counts.items()])}

🏆 **Top 5 供應商**
{top_5_text}

💾 文件已準備好，正在發送...
        """
    
    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """查看狀態"""
        global scraper_task
        
        if scraper_task and not scraper_task.done():
            # 爬蟲正在運行
            checkpoint.load()
            stats = checkpoint.get_stats()
            
            status_text = f"""
⏳ **爬取進行中...**

📊 當前進度:
• 關鍵字: {stats['keywords_processed']}/{stats['keywords_total']}
• 當前: {stats['current_keyword']}
• 頁碼: {stats['current_page']}
• 已處理筆記: {stats['notes_processed']}
• 已處理作者: {stats['authors_processed']}
• 發現供應商: {stats['suppliers_found']}
            """
        else:
            # 沒有運行中的任務
            if cache.suppliers:
                status_text = f"""
✅ **上次爬取已完成**

📊 結果:
• 供應商數量: {len(cache.suppliers)}

使用 /result 獲取結果
或 /search 開始新的搜索
                """
            else:
                status_text = """
💤 **當前沒有運行中的任務**

使用 /search <關鍵字> 開始搜索
例如: /search 童裝代理
                """
        
        await update.message.reply_text(status_text, parse_mode='Markdown')
    
    async def stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """停止爬取"""
        global scraper_task
        
        if scraper_task and not scraper_task.done():
            scraper_task.cancel()
            checkpoint.pause()
            await update.message.reply_text(
                "⏹ 正在停止爬取...\n"
                "進度已保存，可使用 /resume 繼續"
            )
        else:
            await update.message.reply_text("沒有正在運行的任務")
    
    async def result(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """獲取結果"""
        # 檢查輸出目錄
        output_dir = Path('output')
        if not output_dir.exists():
            await update.message.reply_text("還沒有結果文件")
            return
        
        # 找最新的文件
        excel_files = list(output_dir.glob('*.xlsx'))
        if not excel_files:
            await update.message.reply_text("還沒有結果文件")
            return
        
        latest_file = max(excel_files, key=lambda f: f.stat().st_mtime)
        
        await update.message.reply_document(
            document=open(latest_file, 'rb'),
            filename=latest_file.name,
            caption=f"📊 最新結果: {latest_file.name}"
        )
    
    async def top5(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """查看 Top 5"""
        cache.load()
        
        if not cache.suppliers:
            await update.message.reply_text("還沒有數據，請先運行 /search")
            return
        
        # 排序
        sorted_suppliers = sorted(
            cache.suppliers, 
            key=lambda s: s.get('quality_score', 0), 
            reverse=True
        )[:5]
        
        text = "🏆 **Top 5 供應商**\n\n"
        
        for i, s in enumerate(sorted_suppliers, 1):
            text += f"{i}. **{s.get('nickname', '未知')}**\n"
            text += f"   評分: {s.get('quality_score', 0):.0f}\n"
            text += f"   類型: {s.get('supplier_type', '未知')}\n"
            text += f"   聯絡: {s.get('primary_contact', '無')}\n"
            text += f"   [主頁]({s.get('profile_url', '')})\n\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
    
    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """統計信息"""
        cache.load()
        
        if not cache.suppliers:
            await update.message.reply_text("還沒有數據")
            return
        
        suppliers = cache.suppliers
        
        # 統計
        with_wechat = sum(1 for s in suppliers if s.get('primary_contact') and '微信' in s.get('primary_contact', ''))
        avg_score = sum(s.get('quality_score', 0) for s in suppliers) / len(suppliers)
        
        text = f"""
📊 **統計信息**

• 總供應商數: {len(suppliers)}
• 平均評分: {avg_score:.1f}
• 有微信: {with_wechat} ({with_wechat/len(suppliers)*100:.0f}%)

📈 評分分佈:
• 高分(70+): {sum(1 for s in suppliers if s.get('quality_score', 0) >= 70)}
• 中分(40-70): {sum(1 for s in suppliers if 40 <= s.get('quality_score', 0) < 70)}
• 低分(<40): {sum(1 for s in suppliers if s.get('quality_score', 0) < 40)}
        """
        
        await update.message.reply_text(text, parse_mode='Markdown')
    
    async def setpages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """設置最大頁數"""
        if not context.args:
            await update.message.reply_text(
                f"當前設置: {config.search.max_pages_per_keyword} 頁\n"
                f"用法: /setpages <數量>"
            )
            return
        
        try:
            pages = int(context.args[0])
            config.search.max_pages_per_keyword = pages
            await update.message.reply_text(f"✅ 已設置最大頁數為 {pages}")
        except ValueError:
            await update.message.reply_text("❌ 請輸入有效數字")
    
    async def setmax(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """設置最大供應商數量"""
        if not context.args:
            await update.message.reply_text(
                f"當前設置: {config.search.max_authors}\n"
                f"用法: /setmax <數量>"
            )
            return
        
        try:
            max_num = int(context.args[0])
            config.search.max_authors = max_num
            await update.message.reply_text(f"✅ 已設置最大供應商數量為 {max_num}")
        except ValueError:
            await update.message.reply_text("❌ 請輸入有效數字")
    
    async def keywords(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """查看/設置關鍵字"""
        if context.args:
            # 設置新關鍵字
            config.search.keywords = list(context.args)
            await update.message.reply_text(
                f"✅ 已更新關鍵字列表:\n" + 
                "\n".join([f"• {kw}" for kw in config.search.keywords])
            )
        else:
            # 顯示當前關鍵字
            await update.message.reply_text(
                "📋 **當前關鍵字列表:**\n\n" +
                "\n".join([f"• {kw}" for kw in config.search.keywords]) +
                "\n\n用法: /keywords <關鍵字1> <關鍵字2> ...",
                parse_mode='Markdown'
            )
    
    async def export_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """導出數據"""
        cache.load()
        
        if not cache.suppliers:
            await update.message.reply_text("沒有數據可導出")
            return
        
        await update.message.reply_text("⏳ 正在導出...")
        
        # 重建 Supplier 對象
        from models import Supplier, Author, SupplierType
        
        suppliers = []
        for data in cache.suppliers:
            author = Author(
                user_id=data.get('user_id', ''),
                nickname=data.get('nickname', ''),
                bio=data.get('bio', ''),
                followers=data.get('followers', 0),
            )
            supplier = Supplier(author=author)
            supplier.quality_score = data.get('quality_score', 0)
            suppliers.append(supplier)
        
        # 導出
        try:
            path = export_suppliers(suppliers, format='excel', output_dir='output')
            await update.message.reply_document(
                document=open(path, 'rb'),
                filename=Path(path).name
            )
        except Exception as e:
            await update.message.reply_text(f"❌ 導出失敗: {e}")
    
    def run(self):
        """運行 Bot"""
        if not TELEGRAM_AVAILABLE:
            print("請先安裝: pip install python-telegram-bot")
            return
        
        # 創建應用
        self.app = Application.builder().token(self.token).build()
        
        # 添加處理器
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.start))
        self.app.add_handler(CommandHandler("search", self.search))
        self.app.add_handler(CommandHandler("status", self.status))
        self.app.add_handler(CommandHandler("stop", self.stop))
        self.app.add_handler(CommandHandler("result", self.result))
        self.app.add_handler(CommandHandler("top5", self.top5))
        self.app.add_handler(CommandHandler("stats", self.stats))
        self.app.add_handler(CommandHandler("setpages", self.setpages))
        self.app.add_handler(CommandHandler("setmax", self.setmax))
        self.app.add_handler(CommandHandler("keywords", self.keywords))
        self.app.add_handler(CommandHandler("export", self.export_cmd))
        
        # 啟動
        print("🤖 Bot 已啟動!")
        print("在 Telegram 中搜索你的 Bot 並發送 /start")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    """主函數"""
    # 從環境變量獲取 Token
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    
    if not token:
        print("請設置環境變量 TELEGRAM_BOT_TOKEN")
        print("export TELEGRAM_BOT_TOKEN=your_bot_token")
        print("\n如何獲取 Token:")
        print("1. 在 Telegram 搜索 @BotFather")
        print("2. 發送 /newbot 創建新 Bot")
        print("3. 複製獲得的 Token")
        return
    
    bot = TelegramBot(token)
    bot.run()


if __name__ == "__main__":
    main()
