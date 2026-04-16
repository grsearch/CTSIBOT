"""
仓位管理器
负责下单、监控止盈止损、超时平仓
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from strategy.detector import SpikeSignal
from core.exchange import BinanceREST

logger = logging.getLogger(__name__)


@dataclass
class Position:
    id: int                     # 唯一ID
    symbol: str
    direction: str              # BUY / SELL
    entry_price: float
    quantity: float
    take_profit: float
    stop_loss: float
    open_time: float            # unix timestamp
    order_id: Optional[int] = None
    status: str = "OPEN"        # OPEN / CLOSED
    close_price: float = 0.0
    close_reason: str = ""      # TP / SL / TIMEOUT / MANUAL
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
        self._total_pnl = 0.0
        self._win_count = 0
        self._loss_count = 0

        # 精度信息（从exchange info获取）
        self._qty_step   = 1.0
        self._price_step = 0.00001
        self._min_qty    = 1.0

    async def init_filters(self):
        """获取交易对精度"""
        info = await self.ex.get_exchange_info(self.cfg.SYMBOL)
        if not info:
            return
        for f in info["filters"]:
            if f["filterType"] == "LOT_SIZE":
                self._qty_step = float(f["stepSize"])
                self._min_qty  = float(f["minQty"])
            if f["filterType"] == "PRICE_FILTER":
                self._price_step = float(f["tickSize"])
        logger.info(f"Filters: qty_step={self._qty_step}, price_step={self._price_step}")

    def _round_qty(self, qty: float) -> float:
        step = self._qty_step
        return round(round(qty / step) * step, 8)

    def _round_price(self, price: float) -> float:
        step = self._price_step
        return round(round(price / step) * step, 8)

    @property
    def open_positions(self) -> list[Position]:
        return [p for p in self._positions if p.status == "OPEN"]

    @property
    def stats(self) -> dict:
        total = self._win_count + self._loss_count
        return {
            "total_trades":  total,
            "win":           self._win_count,
            "loss":          self._loss_count,
            "win_rate":      round(self._win_count / total * 100, 1) if total else 0,
            "total_pnl":     round(self._total_pnl, 4),
            "open_count":    len(self.open_positions),
        }

    async def try_open(self, signal: SpikeSignal) -> Optional[Position]:
        """尝试根据信号开仓"""
        # 检查最大持仓限制
        if len(self.open_positions) >= self.cfg.MAX_OPEN_ORDERS:
            logger.debug("Max open positions reached")
            return None

        # 检查是否已有同方向仓位
        for p in self.open_positions:
            if p.direction == signal.direction:
                logger.debug(f"Already have {signal.direction} position")
                return None

        # 评分过滤（低分信号放弃）
        if signal.score < 40:
            logger.debug(f"Score too low: {signal.score}")
            return None

        # 计算下单数量
        usdt_amount = min(
            self.cfg.ORDER_USDT,
            await self.ex.get_asset_balance(self.cfg.QUOTE_ASSET) * 0.95
        )
        qty = self._round_qty(usdt_amount / signal.entry_price)
        if qty < self._min_qty:
            logger.warning(f"Qty {qty} below min {self._min_qty}")
            return None

        entry  = self._round_price(signal.entry_price)
        tp     = self._round_price(signal.take_profit)
        sl     = self._round_price(signal.stop_loss)

        logger.info(
            f"Opening {signal.direction} | entry={entry} "
            f"tp={tp} sl={sl} qty={qty} score={signal.score}"
        )

        try:
            # 用 IOC 限价单快速成交，避免市价单滑点
            order = await self.ex.place_limit_order(
                symbol=self.cfg.SYMBOL,
                side=signal.direction,
                quantity=qty,
                price=entry,
                time_in_force="IOC",
            )
            filled_qty   = float(order.get("executedQty", 0))
            filled_price = float(order.get("fills", [{}])[0].get("price", entry)) \
                           if order.get("fills") else entry

            if filled_qty < self._min_qty:
                logger.warning(f"Order not filled: {order}")
                return None

            self._pos_counter += 1
            pos = Position(
                id=self._pos_counter,
                symbol=self.cfg.SYMBOL,
                direction=signal.direction,
                entry_price=filled_price,
                quantity=filled_qty,
                take_profit=tp,
                stop_loss=sl,
                open_time=time.time(),
                order_id=order.get("orderId"),
                signal_score=signal.score,
            )
            self._positions.append(pos)
            logger.info(f"Position #{pos.id} opened at {filled_price}")
            return pos

        except Exception as e:
            logger.error(f"Open order failed: {e}")
            return None

    async def monitor_positions(self, current_price: float):
        """
        每次轮询调用：检查所有持仓的止盈/止损/超时
        current_price: 最新成交价
        """
        for pos in self.open_positions:
            reason = None
            exit_price = current_price

            if pos.direction == "BUY":
                if current_price >= pos.take_profit:
                    reason = "TP"
                elif current_price <= pos.stop_loss:
                    reason = "SL"
            else:  # SELL
                if current_price <= pos.take_profit:
                    reason = "TP"
                elif current_price >= pos.stop_loss:
                    reason = "SL"

            if not reason and pos.age_seconds >= self.cfg.MAX_HOLD_SECONDS:
                reason = "TIMEOUT"

            if reason:
                await self._close_position(pos, exit_price, reason)

    async def _close_position(self, pos: Position, exit_price: float, reason: str):
        logger.info(
            f"Closing #{pos.id} {pos.direction} @ {exit_price} "
            f"reason={reason} age={pos.age_seconds:.1f}s"
        )
        close_side = "SELL" if pos.direction == "BUY" else "BUY"
        try:
            await self.ex.place_market_order(
                self.cfg.SYMBOL, close_side, pos.quantity
            )
        except Exception as e:
            logger.error(f"Close order failed: {e}")

        pnl = pos.calc_pnl(exit_price)
        pos.status      = "CLOSED"
        pos.close_price = exit_price
        pos.close_reason= reason
        pos.pnl_usdt    = round(pnl, 4)

        self._total_pnl += pnl
        if pnl > 0:
            self._win_count  += 1
        else:
            self._loss_count += 1

        logger.info(f"Position #{pos.id} closed | PnL={pnl:.4f} USDT | reason={reason}")

    def get_recent_trades(self, n: int = 20) -> list[Position]:
        closed = [p for p in self._positions if p.status == "CLOSED"]
        return closed[-n:]
