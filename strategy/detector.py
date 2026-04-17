"""
插针检测引擎 v4 - 修正版

根本问题修正：
  之前用 lower_wick = min(open,close) - low 来测量针长
  但这个定义下，close越高（回归越多），lower_wick越大
  导致 SPIKE_RATIO（wick/body）和 MAX_RECOVERY 相互矛盾：
    - close接近open时：wick大/body小 → 通过SPIKE_RATIO，但recovery≈100%
    - close接近针尖时：wick小/body大 → 通过recovery要求，但SPIKE_RATIO不足

正确做法：
  用 spike_drop = open - low 来衡量整根针的长度（下跌幅度）
  用 recovery   = (close - low) / spike_drop 衡量恢复程度
  用 body/spike_drop 判断是否是真插针（实体占针的比例要小）

  下插针 BUY 触发条件：
    ① spike_drop / ATR >= SPIKE_VS_ATR  （针足够大）
    ② body / spike_drop <= 1/SPIKE_RATIO （实体占比小，是真插针不是趋势）
    ③ MIN_RECOVERY <= recovery <= MAX_RECOVERY （已部分回归）
    ④ R:R >= MIN_RR

  入场：candle.close（市价单，下一根K线）
  止盈：entry + (spike_root - entry) × TP_RATIO
  止损：low - max(spike_drop×SL_RATIO, ATR×SL_ATR_MULT)
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
    direction: str
    entry_price: float
    take_profit: float
    stop_loss: float
    spike_tip: float      # 针尖（最低点）
    spike_root: float     # 针根（开盘价）
    spike_length: float   # 针长（open - low）
    atr: float
    recovery_pct: float   # 已回归比例 (close-low)/(open-low)
    rr_ratio: float
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

        # ── 下插针 → BUY ──────────────────────────────────────
        # spike_drop = 从开盘到最低点的距离（整根下刺长度）
        spike_drop = candle.open - candle.low
        if spike_drop > 0:
            body        = candle.body
            body_ratio  = body / spike_drop  # 实体占针的比例

            # 条件①：针相对ATR足够大
            if spike_drop / atr >= self.cfg.SPIKE_VS_ATR:
                # 条件②：实体占比小（真插针，不是大阴线）
                # body_ratio < 1/SPIKE_RATIO
                # SPIKE_RATIO=2.5 → body < 40% of spike
                max_body_ratio = 1.0 / self.cfg.SPIKE_RATIO
                if body_ratio <= max_body_ratio:
                    # 条件③：回归比例
                    # recovery = (close - low) / spike_drop
                    # close接近low → recovery≈0（还在底部）
                    # close接近open → recovery≈1（完全恢复）
                    recovery = (candle.close - candle.low) / spike_drop

                    min_rec = getattr(self.cfg, 'MIN_RECOVERY', 0.20)
                    max_rec = getattr(self.cfg, 'MAX_RECOVERY', 0.70)

                    if min_rec <= recovery <= max_rec:
                        spike_tip  = candle.low
                        spike_root = candle.open  # 针根=开盘价

                        entry = candle.close

                        # 止盈：从入场到针根(=open)的距离走TP_RATIO比例
                        if spike_root > entry:
                            tp = entry + (spike_root - entry) * self.cfg.TP_RATIO
                        else:
                            # close超过了open（罕见），ATR兜底
                            tp = entry + atr * 0.3

                        # 止损：针尖下方，两者取大
                        sl_wick = spike_tip - spike_drop * self.cfg.SL_RATIO
                        sl_atr  = spike_tip - atr * getattr(self.cfg, 'SL_ATR_MULT', 0.5)
                        sl = min(sl_wick, sl_atr)

                        if tp <= entry or sl >= spike_tip:
                            return None

                        tp_dist = tp - entry
                        sl_dist = entry - sl
                        if sl_dist <= 0:
                            return None
                        rr = tp_dist / sl_dist

                        if rr < getattr(self.cfg, 'MIN_RR', 1.5):
                            return None

                        score = self._score(candle, spike_drop, atr,
                                            body_ratio, recovery, rr, candle.volume)

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
                            spike_length=spike_drop,
                            atr=atr,
                            recovery_pct=round(recovery, 3),
                            rr_ratio=round(rr, 2),
                            score=score,
                            candle=candle,
                        )

        # ── 上插针 → SELL ──────────────────────────────────────
        spike_rise = candle.high - candle.open  # 从开盘到最高点
        if spike_rise > 0:
            body       = candle.body
            body_ratio = body / spike_rise

            if spike_rise / atr >= self.cfg.SPIKE_VS_ATR:
                max_body_ratio = 1.0 / self.cfg.SPIKE_RATIO
                if body_ratio <= max_body_ratio:
                    recovery = (candle.high - candle.close) / spike_rise

                    min_rec = getattr(self.cfg, 'MIN_RECOVERY', 0.20)
                    max_rec = getattr(self.cfg, 'MAX_RECOVERY', 0.70)

                    if min_rec <= recovery <= max_rec:
                        spike_tip  = candle.high
                        spike_root = candle.open

                        entry = candle.close

                        if spike_root < entry:
                            tp = entry - (entry - spike_root) * self.cfg.TP_RATIO
                        else:
                            tp = entry - atr * 0.3

                        sl_wick = spike_tip + spike_rise * self.cfg.SL_RATIO
                        sl_atr  = spike_tip + atr * getattr(self.cfg, 'SL_ATR_MULT', 0.5)
                        sl = max(sl_wick, sl_atr)

                        if tp >= entry or sl <= spike_tip:
                            return None

                        tp_dist = entry - tp
                        sl_dist = sl - entry
                        if sl_dist <= 0:
                            return None
                        rr = tp_dist / sl_dist

                        if rr < getattr(self.cfg, 'MIN_RR', 1.5):
                            return None

                        score = self._score(candle, spike_rise, atr,
                                            body_ratio, recovery, rr, candle.volume)

                        return SpikeSignal(
                            direction="SELL",
                            entry_price=entry,
                            take_profit=tp,
                            stop_loss=sl,
                            spike_tip=spike_tip,
                            spike_root=spike_root,
                            spike_length=spike_rise,
                            atr=atr,
                            recovery_pct=round(recovery, 3),
                            rr_ratio=round(rr, 2),
                            score=score,
                            candle=candle,
                        )

        return None

    def _score(self, candle, spike_len, atr, body_ratio, recovery, rr, volume):
        # 针/ATR比越大越好（30分）
        s_spike = min(spike_len / atr / (self.cfg.SPIKE_VS_ATR * 2), 1.0) * 30
        # 实体占比越小越好（25分）
        max_br = 1.0 / self.cfg.SPIKE_RATIO
        s_body  = max(0.0, 1.0 - body_ratio / max_br) * 25
        # 回归在40%~60%最理想（20分）
        s_rec   = max(0.0, 1.0 - abs(recovery - 0.5) / 0.5) * 20
        # R:R越高越好（15分）
        s_rr    = min(rr / 3.0, 1.0) * 15
        # 成交量突增（10分）
        recent  = [c.volume for c in list(self.candles)[-20:]]
        avg_v   = float(np.mean(recent)) if recent else 1.0
        s_vol   = min((volume / avg_v) / 5.0, 1.0) * 10
        return round(s_spike + s_body + s_rec + s_rr + s_vol, 1)
