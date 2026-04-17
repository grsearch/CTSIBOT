#!/usr/bin/env python3
"""启动: python main.py [--dry-run] [--live]"""
import asyncio, logging, sys, os
from logging.handlers import RotatingFileHandler
import config

os.makedirs(config.LOG_DIR, exist_ok=True)

def setup_logging():
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S")
    root = logging.getLogger()
    root.setLevel(getattr(logging, config.LOG_LEVEL))
    ch = logging.StreamHandler(sys.stdout); ch.setFormatter(fmt); root.addHandler(ch)
    fh = RotatingFileHandler(
        os.path.join(config.LOG_DIR, "bot.log"),
        maxBytes=10*1024*1024, backupCount=5, encoding="utf-8"
    )
    fh.setFormatter(fmt); root.addHandler(fh)
    return logging.getLogger("main")

async def main():
    logger = setup_logging()

    if "--dry-run" in sys.argv: config.DRY_RUN = True
    if "--live"    in sys.argv: config.DRY_RUN = False

    if config.API_KEY == "YOUR_API_KEY":
        logger.error("请先在 config.py 填写 API_KEY / API_SECRET")
        sys.exit(1)

    dry = config.DRY_RUN
    logger.info("=" * 55)
    logger.info(f"模式: {'DRY-RUN 空跑（信号检测+模拟交易，不实际下单）' if dry else 'LIVE 实盘交易'}")
    logger.info(f"扫描: {config.SCAN_MODE}  |  Dashboard: http://0.0.0.0:{config.WEB_PORT}")
    logger.info("=" * 55)

    if dry:
        from core.exchange import BinanceREST
        _oid = [0]

        async def _fake_market(self_ex, symbol, side, quantity):
            _oid[0] += 1
            try:
                from bot import STATE
                price = STATE.get("prices", {}).get(symbol, 0)
                if price == 0:
                    t = await self_ex._request("GET", "/api/v3/ticker/bookTicker", {"symbol": symbol})
                    price = float(t.get("askPrice", 0) or t.get("bidPrice", 0))
                fill = price * (1.0002 if side == "BUY" else 0.9998)
            except Exception:
                fill = 0.0
            logging.getLogger("dry").info(f"[DRY] MARKET {side} {symbol} qty={quantity:.4f} @ {fill:.8f}")
            return {
                "orderId":      _oid[0],
                "executedQty":  str(quantity),
                "fills":        [{"price": str(fill), "qty": str(quantity)}],
                "status":       "FILLED",
            }

        async def _fake_balance(self_ex, asset):
            return 1000.0 if asset == "USDT" else 0.0

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
