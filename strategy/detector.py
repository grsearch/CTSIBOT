"""
插针检测引擎

策略逻辑（基于REST轮询现实）：
  用已收盘的1秒K线检测插针，下一根K线市价入场。

  检测条件（同时满足）：
    ① 下影线 >= MIN_SPIKE_PIPS（绝对长度过滤噪音）
    ② 下影线 / 实体   >= SPIKE_RATIO  （真插针，不是趋势K线）
    ③ 下影线 / ATR(20)>= SPIKE_VS_ATR（相对近期波动够大）
    ④ 已回归比例 in [MIN_RECOVERY, MAX_RECOVERY]
       - 已回归 = (收盘-针尖) / 针长
       - 太少(<20%)：可能还在下跌，未确认反转
       - 太多(>70%)：利润空间不足
    ⑤ 风险收益比 >= MIN_RR（自动计算，过滤低质量信号）

  入场价：candle.close（下一根K线市价单成交）
  止盈：针尖 + 针长 × TP_RATIO
  止损：针尖 - max(针长×SL_RATIO, ATR×SL_ATR_MULT)
         两者取大 = 自适应止损，市场平静时更紧，波动大时更宽
"""
import logging
from dataclasses import dataclass
from typing import Optional
from collections import deque
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Candle:
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low

    @property
    def range(self) -> float:
        return self.high - self.low


@dataclass
class SpikeSignal:
    direction: str        # "BUY" | "SELL"
    entry_price: float    # 预估入场价（收盘价，市价单入场）
    take_profit: float    # 止盈价
    stop_loss: float      # 止损价
    spike_tip: float      # 针尖
    spike_root: float     # 针根
    spike_length: float   # 针长
    atr: float
    recovery_pct: float   # 当前已回归比例
    rr_ratio: float       # 实际风险收益比
    score: float
    candle: Candle = None


class SpikeDetector:
    def __init__(self, config):
        self.cfg = config
        self.candles: deque[Candle] = deque(maxlen=500)
        self._atr_cache: float = 0.0

    def update(self, klines: list):
        existing = {c.open_time for c in self.candles}
        for k in klines:
            if k["open_time"] not in existing:
                self.candles.append(Candle(
                    open_time=k["open_time"],
                    open=k["open"], high=k["high"],
                    low=k["low"],   close=k["close"],
                    volume=k["volume"],
                ))
        self._atr_cache = self._calc_atr()

    def _calc_atr(self) -> float:
        cs = list(self.candles)
        if len(cs) < 5:
            return 0.0
        n = min(self.cfg.ATR_PERIOD, len(cs) - 1)
        return float(np.mean([c.range for c in cs[-n:]])) or 0.0

    def _calc_ma(self, period: int) -> float:
        cs = list(self.candles)
        if len(cs) < period:
            return 0.0
        return float(np.mean([c.close for c in cs[-period:]]))

    def detect(self, candle: Candle) -> Optional[SpikeSignal]:
        atr = self._atr_cache
        if atr == 0:
            return None

        # 最小针长（相对价格比例）
        min_abs = (candle.close * self.cfg.MIN_SPIKE_PIPS
                   if self.cfg.MIN_SPIKE_PIPS < 0.01
                   else self.cfg.MIN_SPIKE_PIPS)

        # ── 下插针 → BUY ──────────────────────────────────────
        lower = candle.lower_wick
        if lower >= min_abs:
            body       = max(candle.body, candle.range * 0.01)
            ratio_body = lower / body
            ratio_atr  = lower / atr

            if ratio_body >= self.cfg.SPIKE_RATIO and ratio_atr >= self.cfg.SPIKE_VS_ATR:
                spike_tip  = candle.low
                spike_root = min(candle.open, candle.close)
                recovery   = (candle.close - spike_tip) / lower

                min_rec = getattr(self.cfg, 'MIN_RECOVERY', 0.20)
                max_rec = getattr(self.cfg, 'MAX_RECOVERY', 0.70)

                if min_rec <= recovery <= max_rec:
                    entry = candle.close

                    # 止盈：基于针尖
                    tp = spike_tip + lower * self.cfg.TP_RATIO

                    # 止损：两者取大（针长比例 vs ATR倍数）
                    sl_by_wick = spike_tip - lower * self.cfg.SL_RATIO
                    sl_by_atr  = spike_tip - atr * getattr(self.cfg, 'SL_ATR_MULT', 0.5)
                    sl = min(sl_by_wick, sl_by_atr)  # min = 更低 = 更宽止损

                    # 过滤：tp必须高于entry
                    if tp <= entry:
                        return None

                    # 风险收益比计算
                    tp_dist = tp - entry
                    sl_dist = entry - sl
                    if sl_dist <= 0:
                        return None
                    rr = tp_dist / sl_dist

                    min_rr = getattr(self.cfg, 'MIN_RR', 1.5)
                    if rr < min_rr:
                        return None  # R:R不够，不入场

                    score = self._score(candle, ratio_body, ratio_atr,
                                        recovery, rr, candle.volume)

                    if self.cfg.TREND_FILTER:
                        ma = self._calc_ma(self.cfg.MA_PERIOD)
                        if ma > candle.close * 1.005:
                            score *= 0.7

                    return SpikeSignal(
                        direction="BUY",
                        entry_price=entry,
                        take_profit=tp,
                        stop_loss=sl,
                        spike_tip=spike_tip,
                        spike_root=spike_root,
                        spike_length=lower,
                        atr=atr,
                        recovery_pct=recovery,
                        rr_ratio=round(rr, 2),
                        score=score,
                        candle=candle,
                    )

        # ── 上插针 → SELL ──────────────────────────────────────
        upper = candle.upper_wick
        min_abs2 = (candle.close * self.cfg.MIN_SPIKE_PIPS
                    if self.cfg.MIN_SPIKE_PIPS < 0.01
                    else self.cfg.MIN_SPIKE_PIPS)
        if upper >= min_abs2:
            body       = max(candle.body, candle.range * 0.01)
            ratio_body = upper / body
            ratio_atr  = upper / atr

            if ratio_body >= self.cfg.SPIKE_RATIO and ratio_atr >= self.cfg.SPIKE_VS_ATR:
                spike_tip  = candle.high
                spike_root = max(candle.open, candle.close)
                recovery   = (spike_tip - candle.close) / upper

                min_rec = getattr(self.cfg, 'MIN_RECOVERY', 0.20)
                max_rec = getattr(self.cfg, 'MAX_RECOVERY', 0.70)

                if min_rec <= recovery <= max_rec:
                    entry = candle.close
                    tp    = spike_tip - upper * self.cfg.TP_RATIO

                    sl_by_wick = spike_tip + upper * self.cfg.SL_RATIO
                    sl_by_atr  = spike_tip + atr * getattr(self.cfg, 'SL_ATR_MULT', 0.5)
                    sl = max(sl_by_wick, sl_by_atr)  # max = 更高 = 更宽止损

                    if tp >= entry:
                        return None

                    tp_dist = entry - tp
                    sl_dist = sl - entry
                    if sl_dist <= 0:
                        return None
                    rr = tp_dist / sl_dist

                    min_rr = getattr(self.cfg, 'MIN_RR', 1.5)
                    if rr < min_rr:
                        return None

                    score = self._score(candle, ratio_body, ratio_atr,
                                        recovery, rr, candle.volume)

                    return SpikeSignal(
                        direction="SELL",
                        entry_price=entry,
                        take_profit=tp,
                        stop_loss=sl,
                        spike_tip=spike_tip,
                        spike_root=spike_root,
                        spike_length=upper,
                        atr=atr,
                        recovery_pct=recovery,
                        rr_ratio=round(rr, 2),
                        score=score,
                        candle=candle,
                    )

        return None

    def _score(self, candle, ratio_body, ratio_atr, recovery, rr, volume):
        # 针/实体比越大越好（30分）
        s_body = min(ratio_body / (self.cfg.SPIKE_RATIO * 3), 1.0) * 30
        # 针/ATR比越大越好（20分）
        s_atr  = min(ratio_atr  / (self.cfg.SPIKE_VS_ATR * 2), 1.0) * 20
        # 已回归在40%~60%最理想（25分）
        ideal  = 0.5
        max_rec = getattr(self.cfg, 'MAX_RECOVERY', 0.70)
        s_rec  = max(0.0, 1.0 - abs(recovery - ideal) / ideal) * 25
        # R:R越高越好（15分）
        s_rr   = min(rr / 3.0, 1.0) * 15
        # 成交量突增（10分）
        recent = [c.volume for c in list(self.candles)[-20:]]
        avg_v  = float(np.mean(recent)) if recent else 1.0
        s_vol  = min((candle.volume / avg_v) / 5.0, 1.0) * 10
        return round(s_body + s_atr + s_rec + s_rr + s_vol, 1)
