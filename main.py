#!/usr/bin/env python3
"""
CTSI Spike Arbitrage Bot
启动命令：python main.py [--dry-run]
"""
import asyncio
import logging
import sys
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

import config

os.makedirs(config.LOG_DIR, exist_ok=True)

# ── 日志配置 ──────────────────────────────────────────────────
def setup_logging():
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    root = logging.getLogger()
    root.setLevel(getattr(logging, config.LOG_LEVEL))

    # 控制台
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # 滚动文件
    fh = RotatingFileHandler(
        os.path.join(config.LOG_DIR, "bot.log"),
        maxBytes=10*1024*1024, backupCount=5, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)

    return logging.getLogger("main")


async def main():
    logger = setup_logging()
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        logger.info("=== DRY RUN MODE (不实际下单) ===")
    else:
        logger.info("=== LIVE TRADING MODE ===")

    if config.API_KEY == "YOUR_API_KEY":
        logger.error("请先在 config.py 填写 API_KEY 和 API_SECRET")
        sys.exit(1)

    from bot import run as run_bot, TradingBot
    from web.dashboard import run_web

    # 如果 dry_run，patch 下单方法
    if dry_run:
        from core.exchange import BinanceREST
        async def _fake_order(*a, **kw):
            logger.info(f"[DRY] place_order args={a} kwargs={kw}")
            return {"orderId": 0, "executedQty": "10", "fills": [{"price": str(config.ORDER_USDT / 0.04)}]}
        BinanceREST.place_limit_order  = _fake_order
        BinanceREST.place_market_order = _fake_order

    logger.info(f"Symbol: {config.SYMBOL}")
    logger.info(f"Poll interval: {config.POLL_INTERVAL_MS}ms")
    logger.info(f"Order size: {config.ORDER_USDT} USDT")
    logger.info(f"Dashboard: http://0.0.0.0:{config.WEB_PORT}")

    web_runner = await run_web()

    try:
        await run_bot()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        await web_runner.cleanup()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
