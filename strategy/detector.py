"""
插针检测引擎
核心逻辑：识别1秒K线插针 + 胜率过滤

TP/SL 计算规则（已修复）：
  BUY (下插针):
    entry  = candle.close
    tp     = spike_root + atr * 0.2        # 超过针根一点点，确保 tp > entry
             (若 tp <= entry 则 tp = entry + wick * 0.15，兜底)
    sl     = spike_tip - wick * SL_RATIO   # 针尖下方

  SELL (上插针):
    entry  = candle.close
    tp     = spike_root - atr * 0.2        # 低于针根，确保 tp < entry
             (若 tp >= entry 则 tp = entry - wick * 0.15，兜底)
    sl     = spike_tip + wick * SL_RATIO   # 针尖上方
"""
import logging
from dataclasses import dataclass, field
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
    spike_tip: float
    spike_root: float
    spike_length: float
    atr: float
    recovery_pct: float
    score: float
    candle: Candle = None


class SpikeDetector:
    def __init__(self, config):
        self.cfg = config
        self.candles: deque[Candle] = deque(maxlen=500)
        self._atr_cache: float = 0.0

    def update(self, klines: list[dict]):
        new_times = {c.open_time for c in self.candles}
        for k in klines:
            if k["open_time"] not in new_times:
                self.candles.append(Candle(
                    open_time=k["open_time"],
                    open=k["open"], high=k["high"],
                    low=k["low"],   close=k["close"],
                    volume=k["volume"],
                ))
        self._atr_cache = self._calc_atr()

    def _calc_atr(self) -> float:
        candles = list(self.candles)
        if len(candles) < 5:
            return 0.0
        n = min(self.cfg.ATR_PERIOD, len(candles) - 1)
        ranges = [c.range for c in candles[-n:]]
        return float(np.mean(ranges)) if ranges else 0.0

    def _calc_ma(self, period: int) -> float:
        candles = list(self.candles)
        if len(candles) < period:
            return 0.0
        closes = [c.close for c in candles[-period:]]
        return float(np.mean(closes))

    def detect(self, candle: Candle) -> Optional[SpikeSignal]:
        atr = self._atr_cache
        if atr == 0:
            return None

        # MIN_SPIKE_PIPS: 相对于价格的比例 (e.g. 0.00005 = 0.005%)
        min_abs = (candle.close * self.cfg.MIN_SPIKE_PIPS
                   if self.cfg.MIN_SPIKE_PIPS < 0.01
                   else self.cfg.MIN_SPIKE_PIPS)

        # ── 下插针 → BUY ─────────────────────────────────────
        lower = candle.lower_wick
        if lower >= min_abs:
            body       = max(candle.body, candle.range * 0.01)
            ratio_body = lower / body
            ratio_atr  = lower / atr

            if ratio_body >= self.cfg.SPIKE_RATIO and ratio_atr >= self.cfg.SPIKE_VS_ATR:
                spike_tip  = candle.low
                spike_root = min(candle.open, candle.close)
                recovery   = (candle.close - spike_tip) / lower

                if recovery >= self.cfg.RECOVERY_RATIO:
                    entry = candle.close

                    # TP: entry 到 spike_root 方向走 TP_RATIO 比例
                    # 确保 tp > entry
                    if spike_root > entry:
                        tp = entry + (spike_root - entry) * self.cfg.TP_RATIO
                    else:
                        # over-recovery: close 超过了 root，用 ATR 兜底
                        tp = entry + atr * self.cfg.TP_RATIO * 0.5

                    # SL: 针尖下方
                    sl = spike_tip - lower * self.cfg.SL_RATIO

                    # 验证：tp > entry > spike_tip > sl
                    if not (tp > entry > spike_tip >= sl):
                        logger.debug(
                            f"BUY geometry invalid: tp={tp:.6f} entry={entry:.6f} "
                            f"tip={spike_tip:.6f} sl={sl:.6f}, skip"
                        )
                        return None

                    score = self._score(candle, "BUY", ratio_body, ratio_atr,
                                        recovery, candle.volume)

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
                        score=score,
                        candle=candle,
                    )

        # ── 上插针 → SELL ────────────────────────────────────
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

                if recovery >= self.cfg.RECOVERY_RATIO:
                    entry = candle.close

                    # TP: entry 到 spike_root 方向走 TP_RATIO 比例
                    if spike_root < entry:
                        tp = entry - (entry - spike_root) * self.cfg.TP_RATIO
                    else:
                        tp = entry - atr * self.cfg.TP_RATIO * 0.5

                    # SL: 针尖上方
                    sl = spike_tip + upper * self.cfg.SL_RATIO

                    # 验证：sl > spike_tip > entry > tp
                    if not (sl >= spike_tip >= entry >= tp):
                        logger.debug(
                            f"SELL geometry invalid: sl={sl:.6f} tip={spike_tip:.6f} "
                            f"entry={entry:.6f} tp={tp:.6f}, skip"
                        )
                        return None

                    score = self._score(candle, "SELL", ratio_body, ratio_atr,
                                        recovery, candle.volume)

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
                        score=score,
                        candle=candle,
                    )

        return None

    def _score(self, candle, direction, ratio_body, ratio_atr, recovery, volume):
        s_body     = min(ratio_body / (self.cfg.SPIKE_RATIO * 3), 1.0) * 30
        s_atr      = min(ratio_atr  / (self.cfg.SPIKE_VS_ATR * 2), 1.0) * 25
        s_recovery = min(recovery   / 0.9, 1.0) * 25
        recent_vols = [c.volume for c in list(self.candles)[-20:]]
        avg_vol = float(np.mean(recent_vols)) if recent_vols else 1.0
        vol_ratio = volume / avg_vol if avg_vol > 0 else 1.0
        s_vol = min(vol_ratio / 5.0, 1.0) * 20
        return round(s_body + s_atr + s_recovery + s_vol, 1)
