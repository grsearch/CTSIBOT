"""
主交易循环 - 多币种版本
"""
import asyncio
import logging
import time
from datetime import datetime
from typing import Dict

import config as cfg_module
from core.exchange import BinanceREST
from core.scanner import SymbolScanner
from strategy.detector import SpikeDetector, Candle
from strategy.position_manager import PositionManager
from strategy.risk_manager import RiskManager

logger = logging.getLogger(__name__)

STATE = {
    "running":          False,
    "dry_run":          False,
    "scan_mode":        "single",
    "symbols_active":   [],
    "prices":           {},
    "last_tick":        0,
    "signals_found":    0,
    "signals_blocked":  0,
    "detectors":        {},
    "positions":        None,
    "risk":             None,
    "errors":           [],
    "diag":             {},
    # 网格搜索状态
    "grid_running":     False,
    "grid_progress":    0,
    "grid_total":       0,
    "grid_results":     [],
    "grid_best":        None,
    "grid_sym_results": {},
    "grid_log":         [],
    # 实时参数快照
    "live_config":      {},
}

BALANCE_UPDATE_INTERVAL = 30


def _snapshot_config() -> dict:
    keys = [
        "SCAN_MODE", "SYMBOL", "SYMBOL_LIST",
        "SPIKE_RATIO", "SPIKE_VS_ATR", "ATR_PERIOD", "RECOVERY_RATIO", "MIN_SPIKE_PIPS",
        "ORDER_USDT", "MAX_OPEN_ORDERS",
        "TP_RATIO", "SL_RATIO", "MAX_HOLD_SECONDS",
        "MA_PERIOD", "TREND_FILTER", "POLL_INTERVAL_MS",
        "DAILY_LOSS_LIMIT_USDT", "MAX_DRAWDOWN_PCT",
        "MAX_CONSECUTIVE_LOSSES", "MAX_DAILY_TRADES",
        "AUTO_MIN_GAIN_PCT", "AUTO_MIN_VOLUME_USDT", "AUTO_MAX_SYMBOLS", "AUTO_REFRESH_SEC",
        "DRY_RUN",
    ]
    return {k: getattr(cfg_module, k, None) for k in keys}


class SymbolWorker:
    """每个币种一个 worker，独立检测器"""
    def __init__(self, symbol: str, exchange: BinanceREST,
                 pm: PositionManager, rm: RiskManager):
        self.symbol   = symbol
        self.ex       = exchange
        self.pm       = pm
        self.rm       = rm
        self.detector = SpikeDetector(cfg_module)
        self._last_candle_time = 0
        STATE["detectors"][symbol] = self.detector

    async def tick(self):
        klines = await self.ex.get_klines(self.symbol, "1s", cfg_module.KLINE_LIMIT)
        if not klines:
            return

        self.detector.update(klines)
        closed = [k for k in klines if k.get("is_closed", True)]
        if not closed:
            return

        latest = closed[-1]
        price  = latest["close"]
        STATE["prices"][self.symbol] = price

        if latest["open_time"] == self._last_candle_time:
            await self._monitor(price)
            return

        self._last_candle_time = latest["open_time"]
        candle = Candle(
            open_time=latest["open_time"],
            open=latest["open"],  high=latest["high"],
            low=latest["low"],    close=latest["close"],
            volume=latest["volume"],
        )

        # 诊断数据（用最近处理的币更新）
        atr   = self.detector._atr_cache
        lower = candle.lower_wick
        upper = candle.upper_wick
        body  = max(candle.body, candle.range * 0.01)
        STATE["diag"] = {
            "symbol":          self.symbol,
            "last_open":       candle.open,
            "last_high":       candle.high,
            "last_low":        candle.low,
            "last_close":      candle.close,
            "lower_wick":      lower,
            "upper_wick":      upper,
            "body":            body,
            "atr":             atr,
            "ratio_body":      max(lower, upper) / body if body > 0 else 0,
            "ratio_atr":       max(lower, upper) / atr  if atr  > 0 else 0,
            "recovery":        (candle.close - candle.low) / lower if lower > 0 else 0,
            "cfg_spike_ratio": cfg_module.SPIKE_RATIO,
            "cfg_spike_atr":   cfg_module.SPIKE_VS_ATR,
            "cfg_recovery":    cfg_module.RECOVERY_RATIO,
        }

        signal = self.detector.detect(candle)
        if signal:
            STATE["signals_found"] += 1
            logger.info(
                f"[{self.symbol}] SPIKE {signal.direction} "
                f"score={signal.score} tip={signal.spike_tip:.6f} "
                f"entry={signal.entry_price:.6f} "
                f"tp={signal.take_profit:.6f} sl={signal.stop_loss:.6f}"
            )
            can_trade, reason = self.rm.can_trade()
            if STATE["dry_run"]:
                # 空跑模式：模拟完整交易流程（不实际下单，但记录持仓和盈亏）
                if can_trade:
                    await self.pm.try_open(signal, self.symbol)  # 下单接口已被patch为假单
                else:
                    STATE["signals_blocked"] += 1
                    logger.info(f"[DRY] {self.symbol} 风控拦截: {reason}")
            elif can_trade:
                await self.pm.try_open(signal, self.symbol)
            else:
                STATE["signals_blocked"] += 1
                logger.warning(f"[{self.symbol}] 风控拦截: {reason}")

        await self._monitor(price)

    async def _monitor(self, price: float):
        open_before = {p.id for p in self.pm.open_positions}
        await self.pm.monitor_positions(price, self.symbol)
        open_after  = {p.id for p in self.pm.open_positions}
        for pos in self.pm._positions:
            if pos.id in (open_before - open_after) and pos.status == "CLOSED":
                self.rm.record_trade(pos.pnl_usdt)


class TradingBot:
    def __init__(self):
        self.ex      = BinanceREST(cfg_module.API_KEY, cfg_module.API_SECRET, cfg_module.BASE_URL)
        self.pm      = PositionManager(self.ex, cfg_module)
        self.rm      = RiskManager(cfg_module)
        self.scanner = SymbolScanner(self.ex, cfg_module)
        self._workers: Dict[str, SymbolWorker] = {}
        self._running    = False
        self._tick_count = 0

        STATE["positions"]   = self.pm
        STATE["risk"]        = self.rm
        STATE["dry_run"]     = getattr(cfg_module, "DRY_RUN", False)
        STATE["scan_mode"]   = getattr(cfg_module, "SCAN_MODE", "single")
        STATE["live_config"] = _snapshot_config()

    async def start(self):
        logger.info("=== Spike Bot Starting ===")
        await self.pm.init_filters()

        try:
            bal = await self.ex.get_asset_balance(cfg_module.QUOTE_ASSET)
            self.rm.update_balance(bal)
            logger.info(f"初始余额: {bal:.2f} {cfg_module.QUOTE_ASSET}")
        except Exception as e:
            logger.warning(f"获取余额失败: {e}")

        dry = STATE["dry_run"]
        logger.info(f"模式: {'DRY-RUN 空跑（不下单）' if dry else 'LIVE 实盘'}")

        self._running    = True
        STATE["running"] = True

        while self._running:
            t0 = time.monotonic()
            try:
                await self._tick()
            except Exception as e:
                err = f"{datetime.now().strftime('%H:%M:%S')} [{type(e).__name__}] {e}"
                logger.error(f"Tick error: {e}", exc_info=True)
                STATE["errors"].append(err)
                STATE["errors"] = STATE["errors"][-60:]

            elapsed  = (time.monotonic() - t0) * 1000
            sleep_ms = max(0, cfg_module.POLL_INTERVAL_MS - elapsed)
            await asyncio.sleep(sleep_ms / 1000)

    async def _tick(self):
        self._tick_count += 1

        if self._tick_count % BALANCE_UPDATE_INTERVAL == 0:
            try:
                bal = await self.ex.get_asset_balance(cfg_module.QUOTE_ASSET)
                self.rm.update_balance(bal)
            except Exception:
                pass

        symbols = await self.scanner.get_symbols()
        STATE["symbols_active"] = symbols
        STATE["last_tick"]      = int(time.time())
        STATE["scan_mode"]      = getattr(cfg_module, "SCAN_MODE", "single")

        for sym in symbols:
            if sym not in self._workers:
                logger.info(f"添加币种: {sym}")
                self._workers[sym] = SymbolWorker(sym, self.ex, self.pm, self.rm)

        for sym in list(self._workers.keys()):
            if sym not in symbols:
                logger.info(f"移除币种: {sym}")
                del self._workers[sym]
                STATE["detectors"].pop(sym, None)
                STATE["prices"].pop(sym, None)

        batch_size = 5
        sym_list   = list(self._workers.keys())
        for i in range(0, len(sym_list), batch_size):
            batch = sym_list[i:i+batch_size]
            await asyncio.gather(
                *[self._workers[s].tick() for s in batch],
                return_exceptions=True
            )
            if i + batch_size < len(sym_list):
                await asyncio.sleep(0.1)

    def stop(self):
        self._running    = False
        STATE["running"] = False
        logger.info("Bot stopped")

    def apply_live_config(self, updates: dict):
        allowed = {
            "SPIKE_RATIO", "SPIKE_VS_ATR", "RECOVERY_RATIO", "MIN_SPIKE_PIPS",
            "TP_RATIO", "SL_RATIO", "MAX_HOLD_SECONDS",
            "ORDER_USDT", "MAX_OPEN_ORDERS", "TREND_FILTER",
            "DAILY_LOSS_LIMIT_USDT", "MAX_DRAWDOWN_PCT", "MAX_CONSECUTIVE_LOSSES",
            "SCAN_MODE", "SYMBOL", "SYMBOL_LIST",
            "AUTO_MIN_GAIN_PCT", "AUTO_MIN_VOLUME_USDT", "AUTO_MAX_SYMBOLS", "AUTO_REFRESH_SEC",
        }
        changed = []
        for k, v in updates.items():
            if k in allowed:
                setattr(cfg_module, k, v)
                changed.append(f"{k}={v}")
        if changed:
            logger.info(f"参数热更新: {', '.join(changed)}")
            STATE["live_config"] = _snapshot_config()
            STATE["scan_mode"]   = getattr(cfg_module, "SCAN_MODE", "single")
            for sym, worker in self._workers.items():
                worker.detector = SpikeDetector(cfg_module)
                STATE["detectors"][sym] = worker.detector
        return changed


# 全局实例供 dashboard 调用
_bot_instance: TradingBot = None


async def run():
    global _bot_instance
    _bot_instance = TradingBot()
    try:
        await _bot_instance.start()
    finally:
        await _bot_instance.ex.close()
