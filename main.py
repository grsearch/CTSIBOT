#!/usr/bin/env python3
"""启动命令：python main.py [--dry-run] [--live]"""
import asyncio, logging, sys, os
from logging.handlers import RotatingFileHandler
import config

os.makedirs(config.LOG_DIR, exist_ok=True)

def setup_logging():
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s","%H:%M:%S")
    root = logging.getLogger(); root.setLevel(getattr(logging, config.LOG_LEVEL))
    ch = logging.StreamHandler(sys.stdout); ch.setFormatter(fmt); root.addHandler(ch)
    fh = RotatingFileHandler(os.path.join(config.LOG_DIR,"bot.log"),
        maxBytes=10*1024*1024,backupCount=5,encoding="utf-8")
    fh.setFormatter(fmt); root.addHandler(fh)
    return logging.getLogger("main")

async def main():
    logger = setup_logging()

    # 命令行覆盖
    if "--dry-run" in sys.argv: config.DRY_RUN = True
    if "--live"    in sys.argv: config.DRY_RUN = False

    if config.API_KEY == "YOUR_API_KEY":
        logger.error("请先在 config.py 填写 API_KEY / API_SECRET")
        sys.exit(1)

    dry = config.DRY_RUN
    logger.info(f"{'='*50}")
    logger.info(f"模式: {'DRY-RUN 空跑（信号检测，不下单）' if dry else 'LIVE 实盘交易'}")
    logger.info(f"扫描模式: {config.SCAN_MODE}")
    logger.info(f"Dashboard: http://0.0.0.0:{config.WEB_PORT}")
    logger.info(f"{'='*50}")

    if dry:
        # 空跑时 patch 下单接口
        from core.exchange import BinanceREST
        async def _fake(*a,**kw):
            logging.getLogger("dry").info(f"[DRY] order skipped")
            return {"orderId":0,"executedQty":"0","fills":[]}
        BinanceREST.place_limit_order  = _fake
        BinanceREST.place_market_order = _fake

    from web.dashboard import run_web
    from bot import run as run_bot

    web_runner = await run_web()
    try:
        await run_bot()
    except KeyboardInterrupt:
        logger.info("用户中断")
    finally:
        await web_runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
