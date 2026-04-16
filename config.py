"""
Spike Arbitrage Bot - Configuration
腾讯云东京 / Binance REST API
所有参数均可通过 Dashboard 实时修改，重启后从此文件读取
"""

# ── Binance API ──────────────────────────────────────────────
API_KEY    = "YOUR_API_KEY"
API_SECRET = "YOUR_API_SECRET"
BASE_URL   = "https://api.binance.com"

# ── 多币种扫描 ────────────────────────────────────────────────
# 模式: "single" = 只盯一个币  |  "list" = 指定列表  |  "auto" = 自动筛选活跃币
SCAN_MODE  = "single"

# single 模式下的交易币种
SYMBOL     = "CTSIUSDT"
BASE_ASSET = "CTSI"
QUOTE_ASSET= "USDT"

# list 模式：手动指定多个币种
SYMBOL_LIST = [
    "CTSIUSDT", "SOLUSDT", "SUIUSDT", "APEUSDT",
    "INJUSDT",  "ARBUSDT", "STXUSDT", "FETUSDT",
]

# auto 模式：从24h行情中自动筛选满足条件的币
AUTO_MIN_GAIN_PCT     = 30.0        # 24h涨幅下限 %（绝对值，涨跌均算）
AUTO_MIN_VOLUME_USDT  = 20_000_000  # 24h最低成交额（USDT），默认20M
AUTO_MIN_PRICE        = 0.0001      # 最低价格（过滤极小数精度问题）
AUTO_MAX_SYMBOLS      = 10          # 最多同时监控几个币
AUTO_REFRESH_SEC      = 900         # 重新查涨幅榜间隔（秒），默认15分钟

# ── 插针检测参数 ──────────────────────────────────────────────
SPIKE_RATIO      = 3.0    # 针长 / K线实体 倍数阈值
SPIKE_VS_ATR     = 2.5    # 针长 / ATR 倍数阈值
ATR_PERIOD       = 20     # ATR 计算周期
RECOVERY_RATIO   = 0.50   # 收盘价至少回归针长的50%才触发
MIN_SPIKE_PIPS   = 0.0003 # 针的最小绝对长度

# ── 仓位与资金管理 ────────────────────────────────────────────
ORDER_USDT       = 20.0   # 每笔下单金额 USDT
MAX_OPEN_ORDERS  = 2      # 全局同时持仓笔数上限
RISK_PER_TRADE   = 0.01   # 单笔亏损上限（账户余额比例）

# ── 止盈止损 ──────────────────────────────────────────────────
TP_RATIO         = 0.70   # 止盈：回归针长的70%
SL_RATIO         = 0.10   # 止损：针尖再延伸10%
MAX_HOLD_SECONDS = 30     # 超时强制平仓（秒）

# ── 趋势过滤 ──────────────────────────────────────────────────
MA_PERIOD        = 99
TREND_FILTER     = True

# ── 轮询 ─────────────────────────────────────────────────────
POLL_INTERVAL_MS = 800    # 每个币种轮询间隔（ms）
KLINE_LIMIT      = 120    # 每次拉取K线根数

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
DRY_RUN = False   # True = 不实际下单（空跑）
