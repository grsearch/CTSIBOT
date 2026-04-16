"""
主交易循环
REST轮询 → 检测插针 → 风控检查 → 下单 → 监控平仓
"""
import asyncio
import logging
import time
from datetime import datetime

import config
from core.exchange import BinanceREST
from strategy.detector import SpikeDetector, Candle
from strategy.position_manager import PositionManager
from strategy.risk_manager import RiskManager

logger = logging.getLogger(__name__)

STATE = {
    "running":         False,
    "last_price":      0.0,
    "last_tick":       0,
    "signals_found":   0,
    "signals_blocked": 0,
    "detector":        None,
    "positions":       None,
    "risk":            None,
    "errors":          [],
}

BALANCE_UPDATE_INTERVAL = 30


class TradingBot:
    def __init__(self):
        self.ex       = BinanceREST(config.API_KEY, config.API_SECRET, config.BASE_URL)
        self.detector = SpikeDetector(config)
        self.pm       = PositionManager(self.ex, config)
        self.rm       = RiskManager(config)
        self._running = False
        self._last_candle_time = 0
        self._tick_count = 0

        STATE["detector"]  = self.detector
        STATE["positions"] = self.pm
        STATE["risk"]      = self.rm

    async def start(self):
        logger.info("=== CTSI Spike Bot Starting ===")
        await self.pm.init_filters()

        try:
            bal = await self.ex.get_asset_balance(config.QUOTE_ASSET)
            self.rm.update_balance(bal)
            logger.info(f"初始余额: {bal:.2f} {config.QUOTE_ASSET}")
        except Exception as e:
            logger.warning(f"获取余额失败: {e}")

        self._running    = True
        STATE["running"] = True
        logger.info(f"轮询间隔: {config.POLL_INTERVAL_MS}ms | 日亏损上限: {config.DAILY_LOSS_LIMIT_USDT} USDT | 最大回撤: {config.MAX_DRAWDOWN_PCT}%")

        while self._running:
            t0 = time.monotonic()
            try:
                await self._tick()
            except Exception as e:
                err = f"{datetime.now().strftime('%H:%M:%S')} {e}"
                logger.error(f"Tick error: {e}", exc_info=True)
                STATE["errors"].append(err)
                STATE["errors"] = STATE["errors"][-50:]

            elapsed = (time.monotonic() - t0) * 1000
            sleep_ms = max(0, config.POLL_INTERVAL_MS - elapsed)
            await asyncio.sleep(sleep_ms / 1000)

    async def _tick(self):
        self._tick_count += 1

        if self._tick_count % BALANCE_UPDATE_INTERVAL == 0:
            try:
                bal = await self.ex.get_asset_balance(config.QUOTE_ASSET)
                self.rm.update_balance(bal)
            except Exception:
                pass

        klines = await self.ex.get_klines(config.SYMBOL, "1s", config.KLINE_LIMIT)
        if not klines:
            return

        self.detector.update(klines)
        closed = [k for k in klines if k.get("is_closed", True)]
        if not closed:
            return

        latest = closed[-1]
        if latest["open_time"] == self._last_candle_time:
            price = latest["close"]
            STATE["last_price"] = price
            STATE["last_tick"]  = int(time.time())
            await self._monitor_and_record(price)
            return

        self._last_candle_time = latest["open_time"]
        candle = Candle(
            open_time=latest["open_time"],
            open=latest["open"],  high=latest["high"],
            low=latest["low"],    close=latest["close"],
            volume=latest["volume"],
        )

        price = candle.close
        STATE["last_price"] = price
        STATE["last_tick"]  = int(time.time())

        signal = self.detector.detect(candle)
        if signal:
            STATE["signals_found"] += 1
            logger.info(
                f"SPIKE {signal.direction} | score={signal.score} "
                f"tip={signal.spike_tip:.6f} entry={signal.entry_price:.6f} "
                f"tp={signal.take_profit:.6f} sl={signal.stop_loss:.6f} "
                f"recovery={signal.recovery_pct:.1%}"
            )
            can_trade, reason = self.rm.can_trade()
            if can_trade:
                await self.pm.try_open(signal)
            else:
                STATE["signals_blocked"] += 1
                logger.warning(f"风控拦截: {reason}")

        await self._monitor_and_record(price)

    async def _monitor_and_record(self, price: float):
        open_before = {p.id for p in self.pm.open_positions}
        await self.pm.monitor_positions(price)
        open_after = {p.id for p in self.pm.open_positions}
        closed_ids = open_before - open_after
        for pos in self.pm._positions:
            if pos.id in closed_ids and pos.status == "CLOSED":
                self.rm.record_trade(pos.pnl_usdt)

    def stop(self):
        self._running    = False
        STATE["running"] = False
        logger.info("Bot stopped")


async def run():
    bot = TradingBot()
    try:
        await bot.start()
    finally:
        await bot.ex.close()
