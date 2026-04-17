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
        # 空跑时 patch 下单接口：返回"完全成交"，让仓位管理器记录模拟仓位
        from core.exchange import BinanceREST
        import time as _time

        _order_id = [0]
        async def _fake_limit(self_ex, symbol, side, quantity, price, time_in_force="GTC"):
            _order_id[0] += 1
            qty = quantity
            logging.getLogger("dry").info(
                f"[DRY] {side} {symbol} qty={qty:.4f} @ {price:.8f}")
            return {
                "orderId": _order_id[0],
                "executedQty": str(qty),
                "fills": [{"price": str(price), "qty": str(qty)}],
                "status": "FILLED",
            }
        async def _fake_market(self_ex, symbol, side, quantity):
            _order_id[0] += 1
            qty = quantity
            logging.getLogger("dry").info(
                f"[DRY] MARKET {side} {symbol} qty={qty:.4f}")
            return {
                "orderId": _order_id[0],
                "executedQty": str(qty),
                "fills": [{"price": "0", "qty": str(qty)}],
                "status": "FILLED",
            }
        async def _fake_balance(self_ex, asset):
            if asset == "USDT": return 1000.0
            return 0.0

        BinanceREST.place_limit_order  = _fake_limit
        BinanceREST.place_market_order = _fake_market
        BinanceREST.get_asset_balance  = _fake_balance

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
