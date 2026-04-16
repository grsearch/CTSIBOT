"""
多币种扫描器
- single  : 只监控 config.SYMBOL
- list    : 监控 config.SYMBOL_LIST
- auto    : 从24h行情自动筛选活跃插针候选币
"""
import asyncio
import logging
import time
from typing import List

logger = logging.getLogger(__name__)


class SymbolScanner:
    def __init__(self, exchange, config):
        self.ex  = exchange
        self.cfg = config
        self._symbols: List[str]  = []
        self._last_refresh: float = 0

    async def get_symbols(self) -> List[str]:
        mode = getattr(self.cfg, "SCAN_MODE", "single")

        if mode == "single":
            return [self.cfg.SYMBOL]

        if mode == "list":
            return list(self.cfg.SYMBOL_LIST)

        if mode == "auto":
            now = time.time()
            interval = getattr(self.cfg, "AUTO_REFRESH_INTERVAL", 3600)
            if not self._symbols or (now - self._last_refresh) > interval:
                self._symbols = await self._auto_select()
                self._last_refresh = now
            return self._symbols

        return [self.cfg.SYMBOL]

    async def _auto_select(self) -> List[str]:
        """
        从 Binance 24h ticker 中筛选候选币种：
        条件：USDT计价 + 成交额在设定范围内 + 价格合理 + 按成交额从高到低取前N个
        """
        try:
            tickers = await self.ex._request("GET", "/api/v3/ticker/24hr")
        except Exception as e:
            logger.error(f"获取24h行情失败: {e}")
            return [self.cfg.SYMBOL]

        candidates = []
        min_vol  = getattr(self.cfg, "AUTO_MIN_VOLUME_USDT", 5_000_000)
        max_vol  = getattr(self.cfg, "AUTO_MAX_VOLUME_USDT", 200_000_000)
        min_price= getattr(self.cfg, "AUTO_MIN_PRICE", 0.001)
        max_n    = getattr(self.cfg, "AUTO_MAX_SYMBOLS", 10)

        for t in tickers:
            sym = t.get("symbol", "")
            if not sym.endswith("USDT"):
                continue
            # 排除稳定币
            base = sym[:-4]
            if base in ("USDC","BUSD","TUSD","USDP","FDUSD","DAI","EUR","GBP"):
                continue
            try:
                vol   = float(t.get("quoteVolume", 0))
                price = float(t.get("lastPrice", 0))
                # 波动率（24h振幅 / 收盘价）作为插针潜力指标
                hi    = float(t.get("highPrice", price))
                lo    = float(t.get("lowPrice",  price))
                amp   = (hi - lo) / price if price > 0 else 0
            except Exception:
                continue

            if min_vol <= vol <= max_vol and price >= min_price:
                candidates.append({
                    "symbol": sym,
                    "volume": vol,
                    "amp":    amp,
                    "price":  price,
                })

        if not candidates:
            logger.warning("auto模式未找到候选币，回退到 SYMBOL")
            return [self.cfg.SYMBOL]

        # 综合评分：成交额归一化 * 0.6 + 振幅归一化 * 0.4
        max_v = max(c["volume"] for c in candidates) or 1
        max_a = max(c["amp"]    for c in candidates) or 1
        for c in candidates:
            c["score"] = (c["volume"]/max_v)*0.6 + (c["amp"]/max_a)*0.4

        candidates.sort(key=lambda x: x["score"], reverse=True)
        selected = [c["symbol"] for c in candidates[:max_n]]
        logger.info(f"auto筛选结果({len(selected)}个): {selected}")
        return selected
