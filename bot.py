"""
主交易循环 - 多币种版本
每个币种独立的检测器 + 仓位管理，共享风控和交易所连接
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

# ─────────────────────────────────────────────────────────────
# 全局状态（dashboard 直接读这个 dict）
# ─────────────────────────────────────────────────────────────
STATE = {
    "running":          False,
    "dry_run":          False,
    "scan_mode":        "single",
    "symbols_active":   [],          # 当前扫描的币种列表
    "prices":           {},          # {symbol: price}
    "last_tick":        0,
    "signals_found":    0,
    "signals_blocked":  0,
    "detectors":        {},          # {symbol: SpikeDetector}
    "positions":        None,        # 全局 PositionManager
    "risk":             None,        # RiskManager
    "errors":           [],
    # 网格搜索状态
    "grid_running":     False,
    "grid_progress":    0,
    "grid_total":       0,
    "grid_results":     [],
    "grid_best":        None,
    # 实时参数（可从 dashboard 热更新）
    "live_config":      {},
}

BALANCE_UPDATE_INTERVAL = 30   # 每多少 tick 刷新一次余额


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

        # 避免重复处理同一根K线
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
            if can_trade and not STATE["dry_run"]:
                await self.pm.try_open(signal, self.symbol)
            elif STATE["dry_run"]:
                logger.info(f"[DRY-RUN] 信号被空跑模式跳过: {self.symbol} {signal.direction}")
                STATE["signals_found"] += 0  # 仍计数但不下单
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
        self._running     = False
        self._tick_count  = 0

        STATE["positions"] = self.pm
        STATE["risk"]      = self.rm
        STATE["dry_run"]   = getattr(cfg_module, "DRY_RUN", False)
        STATE["scan_mode"] = getattr(cfg_module, "SCAN_MODE", "single")
        STATE["live_config"] = _snapshot_config()

    async def start(self):
        logger.info("=== Spike Bot Starting (multi-symbol) ===")
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

        # 定期刷新余额
        if self._tick_count % BALANCE_UPDATE_INTERVAL == 0:
            try:
                bal = await self.ex.get_asset_balance(cfg_module.QUOTE_ASSET)
                self.rm.update_balance(bal)
            except Exception:
                pass

        # 获取当前要扫描的币种列表
        symbols = await self.scanner.get_symbols()
        STATE["symbols_active"] = symbols
        STATE["last_tick"]      = int(time.time())

        # 为新币种创建 worker
        for sym in symbols:
            if sym not in self._workers:
                logger.info(f"添加币种: {sym}")
                self._workers[sym] = SymbolWorker(sym, self.ex, self.pm, self.rm)

        # 移除不再需要的 worker
        for sym in list(self._workers.keys()):
            if sym not in symbols:
                logger.info(f"移除币种: {sym}")
                del self._workers[sym]
                STATE["detectors"].pop(sym, None)
                STATE["prices"].pop(sym, None)

        # 并发轮询所有币种（最多5个并发，避免触发限速）
        batch_size = 5
        sym_list   = list(self._workers.keys())
        for i in range(0, len(sym_list), batch_size):
            batch = sym_list[i:i+batch_size]
            await asyncio.gather(
                *[self._workers[s].tick() for s in batch],
                return_exceptions=True
            )
            if i + batch_size < len(sym_list):
                await asyncio.sleep(0.1)  # 批次间小停顿

    def stop(self):
        self._running    = False
        STATE["running"] = False
        logger.info("Bot stopped")

    def apply_live_config(self, updates: dict):
        """Dashboard 热更新参数（不重启）"""
        allowed = {
            "SPIKE_RATIO", "SPIKE_VS_ATR", "RECOVERY_RATIO",
            "TP_RATIO", "SL_RATIO", "MAX_HOLD_SECONDS",
            "ORDER_USDT", "MAX_OPEN_ORDERS", "TREND_FILTER",
            "DAILY_LOSS_LIMIT_USDT", "MAX_DRAWDOWN_PCT", "MAX_CONSECUTIVE_LOSSES",
            "SCAN_MODE", "SYMBOL", "SYMBOL_LIST",
        }
        changed = []
        for k, v in updates.items():
            if k in allowed:
                setattr(cfg_module, k, v)
                changed.append(f"{k}={v}")
        if changed:
            logger.info(f"参数热更新: {', '.join(changed)}")
            STATE["live_config"] = _snapshot_config()
            # 重建所有检测器以应用新参数
            for sym, worker in self._workers.items():
                worker.detector = SpikeDetector(cfg_module)
                STATE["detectors"][sym] = worker.detector
        return changed


def _snapshot_config() -> dict:
    keys = [
        "SCAN_MODE","SYMBOL","SYMBOL_LIST",
        "SPIKE_RATIO","SPIKE_VS_ATR","ATR_PERIOD","RECOVERY_RATIO","MIN_SPIKE_PIPS",
        "ORDER_USDT","MAX_OPEN_ORDERS",
        "TP_RATIO","SL_RATIO","MAX_HOLD_SECONDS",
        "MA_PERIOD","TREND_FILTER",
        "POLL_INTERVAL_MS",
        "DAILY_LOSS_LIMIT_USDT","MAX_DRAWDOWN_PCT",
        "MAX_CONSECUTIVE_LOSSES","MAX_DAILY_TRADES",
        "DRY_RUN",
    ]
    return {k: getattr(cfg_module, k, None) for k in keys}


# 全局 bot 实例（dashboard 调用热更新用）
_bot_instance: TradingBot = None


async def run():
    global _bot_instance
    _bot_instance = TradingBot()
    try:
        await _bot_instance.start()
    finally:
        await _bot_instance.ex.close()
