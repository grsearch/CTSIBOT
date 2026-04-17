"""
仓位管理器 - 多币种版本
每个 symbol 独立精度缓存，统一记录所有仓位
"""
import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional, Dict

from strategy.detector import SpikeSignal
from core.exchange import BinanceREST

logger = logging.getLogger(__name__)


@dataclass
class Position:
    id: int
    symbol: str
    direction: str
    entry_price: float
    quantity: float
    take_profit: float
    stop_loss: float
    open_time: float
    order_id: Optional[int] = None
    status: str = "OPEN"
    close_price: float = 0.0
    close_reason: str = ""
    pnl_usdt: float = 0.0
    signal_score: float = 0.0

    @property
    def age_seconds(self) -> float:
        return time.time() - self.open_time

    def calc_pnl(self, exit_price: float) -> float:
        if self.direction == "BUY":
            return (exit_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - exit_price) * self.quantity


class PositionManager:
    def __init__(self, exchange: BinanceREST, config):
        self.ex   = exchange
        self.cfg  = config
        self._positions: list[Position] = []
        self._pos_counter = 0
        self._total_pnl   = 0.0
        self._win_count   = 0
        self._loss_count  = 0
        # 每个 symbol 的精度信息
        self._filters: Dict[str, dict] = {}
        # 默认精度（未获取到时使用）
        self._default_filters = {"qty_step": 1.0, "price_step": 0.00001, "min_qty": 1.0}

    async def init_filters(self, symbol: str = None):
        """获取交易对精度，支持指定symbol或读config.SYMBOL"""
        sym = symbol or self.cfg.SYMBOL
        await self._fetch_filters(sym)

    async def _fetch_filters(self, symbol: str):
        if symbol in self._filters:
            return
        try:
            info = await self.ex.get_exchange_info(symbol)
            if not info:
                self._filters[symbol] = self._default_filters.copy()
                return
            f_info = {"qty_step": 1.0, "price_step": 0.00001, "min_qty": 1.0}
            for f in info["filters"]:
                if f["filterType"] == "LOT_SIZE":
                    f_info["qty_step"] = float(f["stepSize"])
                    f_info["min_qty"]  = float(f["minQty"])
                if f["filterType"] == "PRICE_FILTER":
                    f_info["price_step"] = float(f["tickSize"])
            self._filters[symbol] = f_info
            logger.info(f"{symbol} filters: {f_info}")
        except Exception as e:
            logger.warning(f"获取{symbol}精度失败: {e}")
            self._filters[symbol] = self._default_filters.copy()

    def _get_filter(self, symbol: str) -> dict:
        return self._filters.get(symbol, self._default_filters)

    def _round_qty(self, qty: float, symbol: str) -> float:
        step = self._get_filter(symbol)["qty_step"]
        return round(round(qty / step) * step, 8)

    def _round_price(self, price: float, symbol: str) -> float:
        step = self._get_filter(symbol)["price_step"]
        return round(round(price / step) * step, 8)

    @property
    def open_positions(self) -> list[Position]:
        return [p for p in self._positions if p.status == "OPEN"]

    @property
    def stats(self) -> dict:
        total = self._win_count + self._loss_count
        return {
            "total_trades": total,
            "win":          self._win_count,
            "loss":         self._loss_count,
            "win_rate":     round(self._win_count / total * 100, 1) if total else 0,
            "total_pnl":    round(self._total_pnl, 4),
            "open_count":   len(self.open_positions),
        }

    async def try_open(self, signal: SpikeSignal, symbol: str = None) -> Optional[Position]:
        sym = symbol or self.cfg.SYMBOL

        # 确保有该 symbol 的精度
        await self._fetch_filters(sym)

        if len(self.open_positions) >= self.cfg.MAX_OPEN_ORDERS:
            logger.debug("Max open positions reached")
            return None

        # 同 symbol 同方向不重复开
        for p in self.open_positions:
            if p.symbol == sym and p.direction == signal.direction:
                logger.debug(f"Already have {signal.direction} on {sym}")
                return None

        if signal.score < 25:  # 降低评分门槛（原40太严）
            logger.debug(f"Score too low: {signal.score}")
            return None

        try:
            usdt_amount = min(
                self.cfg.ORDER_USDT,
                await self.ex.get_asset_balance(self.cfg.QUOTE_ASSET) * 0.95
            )
        except Exception:
            usdt_amount = self.cfg.ORDER_USDT

        qty = self._round_qty(usdt_amount / signal.entry_price, sym)
        min_qty = self._get_filter(sym)["min_qty"]
        if qty < min_qty:
            logger.warning(f"{sym}: qty {qty} < min {min_qty}")
            return None

        entry = self._round_price(signal.entry_price, sym)
        tp    = self._round_price(signal.take_profit,  sym)
        sl    = self._round_price(signal.stop_loss,    sym)

        logger.info(f"Opening {sym} {signal.direction} | entry={entry} tp={tp} sl={sl} qty={qty} score={signal.score}")

        try:
            order = await self.ex.place_limit_order(
                symbol=sym, side=signal.direction,
                quantity=qty, price=entry, time_in_force="IOC",
            )
            filled_qty = float(order.get("executedQty", 0))
            fills = order.get("fills", [])
            raw_price = float(fills[0]["price"]) if fills else 0.0
            filled_price = raw_price if raw_price > 0 else entry

            if filled_qty < min_qty:
                logger.warning(f"{sym}: IOC not filled")
                return None

            self._pos_counter += 1
            pos = Position(
                id=self._pos_counter, symbol=sym,
                direction=signal.direction,
                entry_price=filled_price, quantity=filled_qty,
                take_profit=tp, stop_loss=sl,
                open_time=time.time(),
                order_id=order.get("orderId"),
                signal_score=signal.score,
            )
            self._positions.append(pos)
            logger.info(f"Position #{pos.id} {sym} opened @ {filled_price}")
            return pos
        except Exception as e:
            logger.error(f"Open order failed {sym}: {e}")
            return None

    async def monitor_positions(self, current_price: float, symbol: str = None):
        """检查指定 symbol（或所有）持仓的 TP/SL/超时"""
        for pos in self.open_positions:
            if symbol and pos.symbol != symbol:
                continue
            reason = None
            price  = current_price

            if pos.direction == "BUY":
                if price >= pos.take_profit:  reason = "TP"
                elif price <= pos.stop_loss:  reason = "SL"
            else:
                if price <= pos.take_profit:  reason = "TP"
                elif price >= pos.stop_loss:  reason = "SL"

            if not reason and pos.age_seconds >= self.cfg.MAX_HOLD_SECONDS:
                reason = "TIMEOUT"

            if reason:
                await self._close_position(pos, price, reason)

    async def _close_position(self, pos: Position, exit_price: float, reason: str):
        close_side = "SELL" if pos.direction == "BUY" else "BUY"
        logger.info(f"Closing #{pos.id} {pos.symbol} {pos.direction} @ {exit_price} [{reason}] age={pos.age_seconds:.1f}s")
        try:
            await self.ex.place_market_order(pos.symbol, close_side, pos.quantity)
        except Exception as e:
            logger.error(f"Close order failed: {e}")

        pnl = pos.calc_pnl(exit_price)
        pos.status       = "CLOSED"
        pos.close_price  = exit_price
        pos.close_reason = reason
        pos.pnl_usdt     = round(pnl, 4)
        self._total_pnl += pnl
        if pnl > 0: self._win_count  += 1
        else:        self._loss_count += 1
        logger.info(f"#{pos.id} closed | PnL={pnl:.4f} USDT")

    def get_recent_trades(self, n: int = 20) -> list[Position]:
        return [p for p in self._positions if p.status == "CLOSED"][-n:]
