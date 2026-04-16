"""
Binance REST Client
支持腾讯云环境（无 WebSocket），带重试、限速、签名
"""
import hashlib
import hmac
import time
import asyncio
import logging
from typing import Optional
from urllib.parse import urlencode

import aiohttp

logger = logging.getLogger(__name__)


class BinanceREST:
    def __init__(self, api_key: str, api_secret: str, base_url: str):
        self.api_key    = api_key
        self.api_secret = api_secret
        self.base_url   = base_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None
        self._weight_used = 0
        self._weight_reset_at = 0

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=5)
            self._session = aiohttp.ClientSession(
                headers={"X-MBX-APIKEY": self.api_key},
                timeout=timeout,
            )
        return self._session

    def _sign(self, params: dict) -> dict:
        params["timestamp"] = int(time.time() * 1000)
        query = urlencode(params)
        sig = hmac.new(
            self.api_secret.encode(), query.encode(), hashlib.sha256
        ).hexdigest()
        params["signature"] = sig
        return params

    async def _request(
        self, method: str, path: str, params: dict = None,
        signed: bool = False, retries: int = 3
    ) -> dict:
        session = await self._get_session()
        params  = params or {}
        if signed:
            params = self._sign(params)

        url = f"{self.base_url}{path}"
        last_err = None

        for attempt in range(retries):
            try:
                async with session.request(method, url, params=params) as resp:
                    # 记录权重消耗
                    used = resp.headers.get("X-MBX-USED-WEIGHT-1M", "0")
                    self._weight_used = int(used)

                    if resp.status == 429:
                        retry_after = int(resp.headers.get("Retry-After", 5))
                        logger.warning(f"Rate limit hit, sleeping {retry_after}s")
                        await asyncio.sleep(retry_after)
                        continue

                    if resp.status == 418:
                        logger.error("IP banned by Binance!")
                        await asyncio.sleep(60)
                        continue

                    data = await resp.json()
                    if resp.status != 200:
                        logger.error(f"API error {resp.status}: {data}")
                        last_err = data
                        await asyncio.sleep(0.5 * (attempt + 1))
                        continue
                    return data

            except asyncio.TimeoutError:
                logger.warning(f"Timeout attempt {attempt+1}/{retries}")
                last_err = "timeout"
                await asyncio.sleep(0.3)
            except aiohttp.ClientError as e:
                logger.warning(f"Network error: {e}")
                last_err = str(e)
                await asyncio.sleep(0.5)

        raise RuntimeError(f"Request failed after {retries} retries: {last_err}")

    # ── 公开接口 ──────────────────────────────────────────────

    async def get_klines(self, symbol: str, interval: str = "1s", limit: int = 120):
        """获取K线，interval='1s' 需要 Binance 支持1秒K线"""
        data = await self._request("GET", "/api/v3/klines", {
            "symbol": symbol, "interval": interval, "limit": limit
        })
        klines = []
        for k in data:
            klines.append({
                "open_time": k[0],
                "open":  float(k[1]),
                "high":  float(k[2]),
                "low":   float(k[3]),
                "close": float(k[4]),
                "volume":float(k[5]),
                "close_time": k[6],
                "is_closed": True,
            })
        return klines

    async def get_orderbook(self, symbol: str, limit: int = 5):
        return await self._request("GET", "/api/v3/depth", {
            "symbol": symbol, "limit": limit
        })

    async def get_ticker(self, symbol: str):
        return await self._request("GET", "/api/v3/ticker/bookTicker", {
            "symbol": symbol
        })

    async def get_account(self):
        return await self._request("GET", "/api/v3/account", {}, signed=True)

    async def get_asset_balance(self, asset: str) -> float:
        account = await self.get_account()
        for b in account["balances"]:
            if b["asset"] == asset:
                return float(b["free"])
        return 0.0

    async def get_exchange_info(self, symbol: str):
        data = await self._request("GET", "/api/v3/exchangeInfo", {"symbol": symbol})
        for s in data["symbols"]:
            if s["symbol"] == symbol:
                return s
        return None

    async def place_limit_order(
        self, symbol: str, side: str, quantity: float,
        price: float, time_in_force: str = "GTC"
    ) -> dict:
        """
        side: BUY / SELL
        time_in_force: GTC | IOC | FOK
        """
        params = {
            "symbol":      symbol,
            "side":        side,
            "type":        "LIMIT",
            "timeInForce": time_in_force,
            "quantity":    f"{quantity:.2f}",
            "price":       f"{price:.6f}",
        }
        return await self._request("POST", "/api/v3/order", params, signed=True)

    async def place_market_order(self, symbol: str, side: str, quantity: float) -> dict:
        params = {
            "symbol":   symbol,
            "side":     side,
            "type":     "MARKET",
            "quantity": f"{quantity:.2f}",
        }
        return await self._request("POST", "/api/v3/order", params, signed=True)

    async def cancel_order(self, symbol: str, order_id: int) -> dict:
        return await self._request("DELETE", "/api/v3/order", {
            "symbol": symbol, "orderId": order_id
        }, signed=True)

    async def get_open_orders(self, symbol: str) -> list:
        return await self._request("GET", "/api/v3/openOrders", {
            "symbol": symbol
        }, signed=True)

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
