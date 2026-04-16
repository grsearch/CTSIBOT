"""
插针检测引擎
核心逻辑：识别1秒K线插针 + 胜率过滤
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
    direction: str          # "BUY" | "SELL"
    entry_price: float      # 建议入场价
    take_profit: float      # 止盈价
    stop_loss: float        # 止损价
    spike_tip: float        # 针尖价格
    spike_root: float       # 针根价格（回归目标）
    spike_length: float     # 针的绝对长度
    atr: float
    recovery_pct: float     # 当前K线已回归的百分比
    score: float            # 综合评分 0-100
    candle: Candle = None


class SpikeDetector:
    def __init__(self, config):
        self.cfg = config
        self.candles: deque[Candle] = deque(maxlen=500)
        self._atr_cache: float = 0.0

    def update(self, klines: list[dict]):
        """用新K线数据更新内部缓存"""
        new_times = {c.open_time for c in self.candles}
        added = 0
        for k in klines:
            if k["open_time"] not in new_times:
                self.candles.append(Candle(
                    open_time=k["open_time"],
                    open=k["open"], high=k["high"],
                    low=k["low"],   close=k["close"],
                    volume=k["volume"],
                ))
                added += 1
        if added:
            self._atr_cache = self._calc_atr()

    def _calc_atr(self) -> float:
        """True Range的简单均值（用收盘-开盘近似，避免需要前一根收盘）"""
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
        """
        对最新一根K线判断是否出现插针信号
        返回 SpikeSignal 或 None
        """
        atr = self._atr_cache
        if atr == 0:
            return None

        # ── 下插针 → 做多 ────────────────────────────────────
        lower = candle.lower_wick
        if lower >= self.cfg.MIN_SPIKE_PIPS:
            body  = max(candle.body, candle.range * 0.01)  # 防止体为0
            ratio_body = lower / body
            ratio_atr  = lower / atr

            if ratio_body >= self.cfg.SPIKE_RATIO and ratio_atr >= self.cfg.SPIKE_VS_ATR:
                spike_root  = min(candle.open, candle.close)
                spike_tip   = candle.low
                recovery    = (candle.close - spike_tip) / lower
                if recovery >= self.cfg.RECOVERY_RATIO:
                    score = self._score(candle, "BUY", ratio_body, ratio_atr,
                                        recovery, candle.volume)
                    tp = spike_root + (spike_root - spike_tip) * (self.cfg.TP_RATIO - 1)
                    # 实际止盈：回到针根部附近
                    tp = spike_tip + lower * self.cfg.TP_RATIO
                    sl = spike_tip - lower * self.cfg.SL_RATIO
                    entry = candle.close  # 下根K线开盘附近

                    # 趋势过滤：MA99 在价格下方才做多
                    if self.cfg.TREND_FILTER:
                        ma = self._calc_ma(self.cfg.MA_PERIOD)
                        if ma > candle.close * 1.005:  # MA远在上方 → 空头环境，下插针胜率低
                            logger.debug(f"BUY filtered by trend: ma={ma:.6f} > close={candle.close:.6f}")
                            # 不过滤，但降低评分
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

        # ── 上插针 → 做空（现货卖出持仓）────────────────────────
        upper = candle.upper_wick
        if upper >= self.cfg.MIN_SPIKE_PIPS:
            body  = max(candle.body, candle.range * 0.01)
            ratio_body = upper / body
            ratio_atr  = upper / atr

            if ratio_body >= self.cfg.SPIKE_RATIO and ratio_atr >= self.cfg.SPIKE_VS_ATR:
                spike_root = max(candle.open, candle.close)
                spike_tip  = candle.high
                recovery   = (spike_tip - candle.close) / upper
                if recovery >= self.cfg.RECOVERY_RATIO:
                    score = self._score(candle, "SELL", ratio_body, ratio_atr,
                                        recovery, candle.volume)
                    tp    = spike_tip - upper * self.cfg.TP_RATIO
                    sl    = spike_tip + upper * self.cfg.SL_RATIO
                    entry = candle.close

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

    def _score(
        self, candle: Candle, direction: str,
        ratio_body: float, ratio_atr: float,
        recovery: float, volume: float
    ) -> float:
        """
        综合评分 0-100：
        - 针/实体比      (30分)
        - 针/ATR比       (25分)
        - 已回归比例     (25分)
        - 成交量突增     (20分)
        """
        s_body     = min(ratio_body / (self.cfg.SPIKE_RATIO * 3), 1.0) * 30
        s_atr      = min(ratio_atr  / (self.cfg.SPIKE_VS_ATR * 2), 1.0) * 25
        s_recovery = min(recovery   / 0.9, 1.0) * 25

        # 成交量：与近20根均量比较
        recent_vols = [c.volume for c in list(self.candles)[-20:]]
        avg_vol = float(np.mean(recent_vols)) if recent_vols else 1.0
        vol_ratio = volume / avg_vol if avg_vol > 0 else 1.0
        s_vol = min(vol_ratio / 5.0, 1.0) * 20

        return round(s_body + s_atr + s_recovery + s_vol, 1)
