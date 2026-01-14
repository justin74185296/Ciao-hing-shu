#!/usr/bin/env python3
"""
小紅書童裝供應商爬蟲 - 主程序

功能：
- 批量搜索童裝代理/一件代發/招商供應商
- 提取聯絡方式（微信優先）
- 按品質評分排序導出 Excel

使用方法：
1. 配置 config.json（Cookie、關鍵字等）
2. 運行: python main.py
3. 或使用命令行參數: python main.py --keywords "童裝代理" "童裝批發"

作者：AI Assistant
版本：1.0.0
"""

import asyncio
import argparse
import sys
from pathlib import Path
from datetime import datetime

# 添加項目路徑
sys.path.insert(0, str(Path(__file__).parent))

from config import Config, create_config_template
from scraper import PlaywrightScraper, RequestsScraper, PLAYWRIGHT_AVAILABLE
from exporter import export_suppliers
from checkpoint import CheckpointManager
from utils import logger, setup_logger


def parse_args():
    """解析命令行參數"""
    parser = argparse.ArgumentParser(
        description="小紅書童裝供應商爬蟲 - 批量找到代理/一件代發/招商供應商",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默認配置運行
  python main.py
  
  # 指定關鍵字
  python main.py --keywords "童裝代理" "童裝批發"
  
  # 指定最大頁數和供應商數量
  python main.py --max-pages 5 --max-suppliers 100
  
  # 從斷點恢復
  python main.py --resume
  
  # 創建配置模板
  python main.py --init-config
        """
    )
    
    # 基本參數
    parser.add_argument(
        '--keywords', '-k',
        nargs='+',
        help='搜索關鍵字列表'
    )
    
    parser.add_argument(
        '--config', '-c',
        default='config.json',
        help='配置文件路徑 (默認: config.json)'
    )
    
    # 爬取控制
    parser.add_argument(
        '--max-pages', '-p',
        type=int,
        default=10,
        help='每個關鍵字的最大爬取頁數 (默認: 10)'
    )
    
    parser.add_argument(
        '--max-suppliers', '-s',
        type=int,
        default=200,
        help='最大爬取供應商數量 (默認: 200)'
    )
    
    # 輸出控制
    parser.add_argument(
        '--output', '-o',
        default='output',
        help='輸出目錄 (默認: output)'
    )
    
    parser.add_argument(
        '--format', '-f',
        choices=['excel', 'csv', 'json', 'all'],
        default='excel',
        help='輸出格式 (默認: excel)'
    )
    
    # 斷點續爬
    parser.add_argument(
        '--resume', '-r',
        action='store_true',
        help='從上次中斷的地方繼續'
    )
    
    parser.add_argument(
        '--clear-checkpoint',
        action='store_true',
        help='清除斷點數據，重新開始'
    )
    
    # 調試
    parser.add_argument(
        '--debug',
        action='store_true',
        help='開啟調試模式'
    )
    
    parser.add_argument(
        '--headless',
        action='store_true',
        default=True,
        help='無頭模式運行瀏覽器 (默認: True)'
    )
    
    parser.add_argument(
        '--no-headless',
        action='store_true',
        help='顯示瀏覽器窗口（調試用）'
    )
    
    # 初始化
    parser.add_argument(
        '--init-config',
        action='store_true',
        help='創建配置文件模板'
    )
    
    # Cookie
    parser.add_argument(
        '--cookie',
        help='小紅書 Cookie（也可在配置文件中設置）'
    )
    
    return parser.parse_args()


def print_banner():
    """打印啟動橫幅"""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║      小紅書童裝供應商爬蟲 v1.0                                  ║
║      Xiaohongshu Children's Clothing Supplier Scraper         ║
║                                                               ║
║      功能：批量找到代理/一件代發/招商供應商                       ║
║      目標：香港跨境童裝客戶開發                                  ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_summary(suppliers: list, output_files: list):
    """打印結果摘要"""
    print("\n" + "=" * 60)
    print("爬取結果摘要")
    print("=" * 60)
    
    if not suppliers:
        print("未找到符合條件的供應商")
        return
    
    print(f"總供應商數: {len(suppliers)}")
    
    # 統計
    with_wechat = sum(1 for s in suppliers if s.primary_contact and '微信' in s.primary_contact)
    high_score = sum(1 for s in suppliers if s.quality_score >= 70)
    
    print(f"有微信聯絡方式: {with_wechat} ({with_wechat/len(suppliers)*100:.1f}%)")
    print(f"高評分供應商(70+): {high_score} ({high_score/len(suppliers)*100:.1f}%)")
    
    # 類型分佈
    from models import SupplierType
    type_counts = {}
    for s in suppliers:
        type_name = s.supplier_type.value
        type_counts[type_name] = type_counts.get(type_name, 0) + 1
    
    print("\n供應商類型分佈:")
    for type_name, count in type_counts.items():
        print(f"  - {type_name}: {count}")
    
    # Top 5
    print("\nTop 5 供應商:")
    top_5 = sorted(suppliers, key=lambda s: s.quality_score, reverse=True)[:5]
    for i, s in enumerate(top_5, 1):
        contact = s.primary_contact or "無聯絡方式"
        print(f"  {i}. {s.author.nickname} (評分: {s.quality_score}) - {contact}")
    
    # 輸出文件
    if output_files:
        print("\n輸出文件:")
        for f in output_files:
            print(f"  - {f}")
    
    print("=" * 60)


async def run_scraper(config: Config, args) -> list:
    """運行爬蟲"""
    # 根據可用性選擇爬蟲
    if PLAYWRIGHT_AVAILABLE:
        logger.info("使用 Playwright 爬蟲")
        scraper = PlaywrightScraper(config)
        suppliers = await scraper.run()
    else:
        logger.info("Playwright 不可用，使用 Requests 備用方案")
        logger.warning("注意：Requests 方案可能需要處理額外的反爬驗證")
        scraper = RequestsScraper(config)
        suppliers = scraper.run()
    
    return suppliers


def main():
    """主函數"""
    args = parse_args()
    
    # 打印橫幅
    print_banner()
    
    # 創建配置模板
    if args.init_config:
        create_config_template()
        print("\n配置模板已創建！請編輯 config_template.json 文件，填入你的 Cookie。")
        print("然後重命名為 config.json 並重新運行程序。")
        return
    
    # 設置日誌級別
    if args.debug:
        setup_logger(level=10)  # DEBUG
    
    # 加載配置
    config = Config()
    
    # 加載配置文件
    config_file = Path(args.config)
    if config_file.exists():
        config.load_from_file(str(config_file))
        logger.info(f"已加載配置文件: {config_file}")
    else:
        logger.warning(f"配置文件不存在: {config_file}")
        logger.info("使用默認配置，建議運行 --init-config 創建配置模板")
    
    # 命令行參數覆蓋
    if args.keywords:
        config.search.keywords = args.keywords
    
    if args.max_pages:
        config.search.max_pages_per_keyword = args.max_pages
    
    if args.max_suppliers:
        config.search.max_authors = args.max_suppliers
    
    if args.cookie:
        config.cookie.add_cookie(args.cookie)
    
    # 設置輸出目錄
    config.OUTPUT_DIR = Path(args.output)
    config.OUTPUT_DIR.mkdir(exist_ok=True)
    
    # 處理斷點
    checkpoint = CheckpointManager()
    
    if args.clear_checkpoint:
        checkpoint.clear()
        logger.info("已清除斷點數據")
    
    if args.resume and checkpoint.load():
        logger.info("從斷點恢復爬取")
    
    # 顯示配置信息
    print("\n當前配置:")
    print(f"  - 搜索關鍵字: {config.search.keywords}")
    print(f"  - 每個關鍵字最大頁數: {config.search.max_pages_per_keyword}")
    print(f"  - 最大供應商數量: {config.search.max_authors}")
    print(f"  - 輸出目錄: {config.OUTPUT_DIR}")
    print(f"  - 輸出格式: {args.format}")
    print(f"  - Cookie 已設置: {'是' if config.cookie.get_cookie() else '否'}")
    print()
    
    # Cookie 檢查
    if not config.cookie.get_cookie():
        logger.warning("警告：未設置 Cookie，部分功能可能受限")
        logger.info("建議：在配置文件中設置有效的小紅書 Cookie")
    
    # 確認開始
    try:
        input("按 Enter 鍵開始爬取（Ctrl+C 取消）...")
    except KeyboardInterrupt:
        print("\n已取消")
        return
    
    # 運行爬蟲
    print("\n開始爬取...\n")
    
    try:
        suppliers = asyncio.run(run_scraper(config, args))
    except KeyboardInterrupt:
        logger.info("\n用戶中斷，正在保存進度...")
        checkpoint.pause()
        print("進度已保存，可使用 --resume 參數繼續")
        return
    except Exception as e:
        logger.error(f"爬取過程出錯: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return
    
    # 導出結果
    if suppliers:
        output_files = []
        
        try:
            if args.format == 'all':
                for fmt in ['excel', 'csv', 'json']:
                    path = export_suppliers(
                        suppliers, 
                        format=fmt, 
                        output_dir=str(config.OUTPUT_DIR)
                    )
                    if path:
                        output_files.append(path)
            else:
                path = export_suppliers(
                    suppliers, 
                    format=args.format,
                    output_dir=str(config.OUTPUT_DIR)
                )
                if path:
                    output_files.append(path)
        except Exception as e:
            logger.error(f"導出失敗: {e}")
            # 嘗試備用格式
            try:
                path = export_suppliers(
                    suppliers, 
                    format='json',
                    output_dir=str(config.OUTPUT_DIR)
                )
                output_files.append(path)
            except:
                pass
        
        # 打印摘要
        print_summary(suppliers, output_files)
    else:
        print("\n未找到符合條件的供應商")
        print("建議：")
        print("  1. 檢查 Cookie 是否有效")
        print("  2. 調整搜索關鍵字")
        print("  3. 降低過濾閾值")


if __name__ == "__main__":
    main()
