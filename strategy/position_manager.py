"""
仓位管理器 - 多币种版本
市价单入场，精确用TP/SL价平仓
"""
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
    direction: str       # BUY | SELL
    entry_price: float
    quantity: float
    take_profit: float
    stop_loss: float
    open_time: float
    order_id: Optional[int] = None
    status: str = "OPEN"
    close_price: float = 0.0
    close_reason: str = ""  # TP | SL | TIMEOUT
    pnl_usdt: float = 0.0
    signal_score: float = 0.0
    rr_ratio: float = 0.0

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
        self.ex  = exchange
        self.cfg = config
        self._positions: list[Position] = []
        self._pos_counter = 0
        self._total_pnl   = 0.0
        self._win_count   = 0
        self._loss_count  = 0
        self._filters: Dict[str, dict] = {}
        self._default_filters = {"qty_step": 1.0, "price_step": 0.00001, "min_qty": 1.0}

    async def init_filters(self, symbol: str = None):
        await self._fetch_filters(symbol or self.cfg.SYMBOL)

    async def _fetch_filters(self, symbol: str):
        if symbol in self._filters:
            return
        try:
            info = await self.ex.get_exchange_info(symbol)
            if not info:
                self._filters[symbol] = self._default_filters.copy()
                return
            fi = {"qty_step": 1.0, "price_step": 0.00001, "min_qty": 1.0}
            for f in info["filters"]:
                if f["filterType"] == "LOT_SIZE":
                    fi["qty_step"] = float(f["stepSize"])
                    fi["min_qty"]  = float(f["minQty"])
                if f["filterType"] == "PRICE_FILTER":
                    fi["price_step"] = float(f["tickSize"])
            self._filters[symbol] = fi
            logger.info(f"{symbol} filters: {fi}")
        except Exception as e:
            logger.warning(f"获取{symbol}精度失败: {e}")
            self._filters[symbol] = self._default_filters.copy()

    def _get_filter(self, symbol: str) -> dict:
        return self._filters.get(symbol, self._default_filters)

    def _round_qty(self, qty: float, symbol: str) -> float:
        step = self._get_filter(symbol)["qty_step"]
        if step == 0:
            return qty
        return round(round(qty / step) * step, 8)

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
        await self._fetch_filters(sym)

        if len(self.open_positions) >= self.cfg.MAX_OPEN_ORDERS:
            return None

        # 同币种同方向不重复开
        for p in self.open_positions:
            if p.symbol == sym and p.direction == signal.direction:
                return None

        if signal.score < 25:
            logger.debug(f"Score {signal.score} < 25, skip")
            return None

        try:
            bal = await self.ex.get_asset_balance(self.cfg.QUOTE_ASSET)
            usdt_amount = min(self.cfg.ORDER_USDT, bal * 0.95)
        except Exception:
            usdt_amount = self.cfg.ORDER_USDT

        qty = self._round_qty(usdt_amount / signal.entry_price, sym)
        min_qty = self._get_filter(sym)["min_qty"]
        if qty < min_qty:
            logger.warning(f"{sym}: qty {qty} < min {min_qty}")
            return None

        logger.info(
            f"Opening {sym} {signal.direction} | "
            f"entry≈{signal.entry_price:.6f} "
            f"tp={signal.take_profit:.6f} sl={signal.stop_loss:.6f} "
            f"R:R={signal.rr_ratio} score={signal.score}"
        )

        try:
            # 市价单：必然成交，消除IOC不成交问题
            order = await self.ex.place_market_order(
                symbol=sym, side=signal.direction, quantity=qty,
            )
            filled_qty = float(order.get("executedQty", 0))
            fills = order.get("fills", [])
            if fills:
                total_cost = sum(float(f["price"]) * float(f["qty"]) for f in fills)
                total_qty  = sum(float(f["qty"]) for f in fills)
                filled_price = total_cost / total_qty if total_qty > 0 else signal.entry_price
            else:
                filled_price = signal.entry_price

            if filled_qty < min_qty:
                logger.warning(f"{sym}: market order not filled")
                return None

            self._pos_counter += 1
            pos = Position(
                id=self._pos_counter,
                symbol=sym,
                direction=signal.direction,
                entry_price=filled_price,
                quantity=filled_qty,
                take_profit=signal.take_profit,
                stop_loss=signal.stop_loss,
                open_time=time.time(),
                order_id=order.get("orderId"),
                signal_score=signal.score,
                rr_ratio=signal.rr_ratio,
            )
            self._positions.append(pos)
            logger.info(f"Position #{pos.id} {sym} opened @ {filled_price:.6f}")
            return pos

        except Exception as e:
            logger.error(f"Open failed {sym}: {e}")
            return None

    async def monitor_positions(self, current_price: float, symbol: str = None):
        for pos in list(self.open_positions):
            if symbol and pos.symbol != symbol:
                continue

            reason     = None
            exit_price = current_price

            if pos.direction == "BUY":
                if current_price >= pos.take_profit:
                    reason     = "TP"
                    exit_price = pos.take_profit  # 精确用TP价
                elif current_price <= pos.stop_loss:
                    reason     = "SL"
                    exit_price = pos.stop_loss    # 精确用SL价
            else:
                if current_price <= pos.take_profit:
                    reason     = "TP"
                    exit_price = pos.take_profit
                elif current_price >= pos.stop_loss:
                    reason     = "SL"
                    exit_price = pos.stop_loss

            if not reason and pos.age_seconds >= self.cfg.MAX_HOLD_SECONDS:
                reason     = "TIMEOUT"
                exit_price = current_price  # 超时用当前市价

            if reason:
                await self._close(pos, exit_price, reason)

    async def _close(self, pos: Position, exit_price: float, reason: str):
        close_side = "SELL" if pos.direction == "BUY" else "BUY"
        logger.info(
            f"Closing #{pos.id} {pos.symbol} {pos.direction} @ {exit_price:.6f} "
            f"[{reason}] age={pos.age_seconds:.1f}s"
        )
        try:
            await self.ex.place_market_order(pos.symbol, close_side, pos.quantity)
        except Exception as e:
            logger.error(f"Close failed: {e}")

        pnl = pos.calc_pnl(exit_price)
        pos.status       = "CLOSED"
        pos.close_price  = exit_price
        pos.close_reason = reason
        pos.pnl_usdt     = round(pnl, 4)
        self._total_pnl += pnl
        if pnl > 0:
            self._win_count  += 1
        else:
            self._loss_count += 1
        logger.info(f"#{pos.id} closed | PnL={pnl:+.4f} USDT")

    def get_recent_trades(self, n: int = 20) -> list[Position]:
        return [p for p in self._positions if p.status == "CLOSED"][-n:]
