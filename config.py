"""
Spike Arbitrage Bot - Configuration
腾讯云东京 / Binance REST API
"""

# ── Binance API ──────────────────────────────────────────────
API_KEY    = "YOUR_API_KEY"
API_SECRET = "YOUR_API_SECRET"
BASE_URL   = "https://api.binance.com"

# ── 多币种扫描 ────────────────────────────────────────────────
SCAN_MODE  = "single"   # single | list | auto

SYMBOL     = "CTSIUSDT"
BASE_ASSET = "CTSI"
QUOTE_ASSET= "USDT"

SYMBOL_LIST = [
    "CTSIUSDT", "SOLUSDT", "SUIUSDT", "APEUSDT",
    "INJUSDT",  "ARBUSDT", "STXUSDT", "FETUSDT",
]

# auto 模式 - 涨幅榜筛选
AUTO_MIN_GAIN_PCT     = 15.0        # |24h涨幅| ≥ 15%（调低更容易选到币）
AUTO_MIN_VOLUME_USDT  = 10_000_000  # ≥ 10M USDT 成交量
AUTO_MIN_PRICE        = 0.0001
AUTO_MAX_SYMBOLS      = 10
AUTO_REFRESH_SEC      = 900         # 15分钟重新筛选

# ── 插针检测参数（宽松版，适合低流动性小币）──────────────────
SPIKE_RATIO      = 2.0    # 针/实体倍数，降低到2倍（原3倍太严）
SPIKE_VS_ATR     = 1.5    # 针/ATR倍数，降低到1.5倍（原2.5倍）
ATR_PERIOD       = 20
RECOVERY_RATIO   = 0.40   # 回归40%即触发（原50%）
MIN_SPIKE_PIPS   = 0.00005 # 绝对最小针长，大幅降低（原0.0003对CTSI太高）

# ── 仓位与资金管理 ────────────────────────────────────────────
ORDER_USDT       = 20.0
MAX_OPEN_ORDERS  = 2
RISK_PER_TRADE   = 0.01

# ── 止盈止损 ──────────────────────────────────────────────────
TP_RATIO         = 0.65   # 止盈：回归针长65%
SL_RATIO         = 0.12   # 止损：针尖再延伸12%
MAX_HOLD_SECONDS = 20     # 降低到20秒（1秒K线策略要快进快出）

# ── 趋势过滤 ──────────────────────────────────────────────────
MA_PERIOD        = 99
TREND_FILTER     = False  # 关闭趋势过滤（小币趋势判断不准）

# ── 轮询 ─────────────────────────────────────────────────────
POLL_INTERVAL_MS = 800
KLINE_LIMIT      = 120

# ── Web Dashboard ─────────────────────────────────────────────
WEB_HOST         = "0.0.0.0"
WEB_PORT         = 8888
WEB_SECRET       = "spike2024"

# ── 风险控制 ──────────────────────────────────────────────────
DAILY_LOSS_LIMIT_USDT   = 10.0
MAX_DRAWDOWN_PCT        = 5.0
MAX_CONSECUTIVE_LOSSES  = 5
MAX_DAILY_TRADES        = 200
CIRCUIT_COOLDOWN_SEC    = 3600

# ── 日志 ─────────────────────────────────────────────────────
LOG_DIR   = "logs"
LOG_LEVEL = "INFO"

# ── 模式 ─────────────────────────────────────────────────────
DRY_RUN = False   # True=空跑 / False=实盘
