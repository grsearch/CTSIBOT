"""
CTSI Spike Arbitrage Bot - Configuration
腾讯云东京 / Binance REST API
"""

# ── Binance API ──────────────────────────────────────────────
API_KEY    = "YOUR_API_KEY"
API_SECRET = "YOUR_API_SECRET"
BASE_URL   = "https://api.binance.com"   # 东京节点也可用 api1~api4

# ── 交易标的 ─────────────────────────────────────────────────
SYMBOL     = "CTSIUSDT"
BASE_ASSET = "CTSI"
QUOTE_ASSET= "USDT"

# ── 插针检测参数 ──────────────────────────────────────────────
SPIKE_RATIO      = 3.0    # 针长 / K线实体 倍数阈值
SPIKE_VS_ATR     = 2.5    # 针长 / ATR 倍数阈值
ATR_PERIOD       = 20     # 用于计算平均振幅的K线根数
RECOVERY_RATIO   = 0.50   # 收盘价至少回归针长的50%才触发
MIN_SPIKE_PIPS   = 0.0003 # 针的绝对最小长度（过滤噪音）

# ── 仓位与资金管理 ────────────────────────────────────────────
ORDER_USDT       = 20.0   # 每笔下单金额 USDT
MAX_OPEN_ORDERS  = 2      # 同时持仓笔数上限
RISK_PER_TRADE   = 0.01   # 每笔亏损不超过账户余额的 1%

# ── 止盈止损（相对于针低点/高点的 tick 偏移） ──────────────────
TP_RATIO         = 0.70   # 止盈目标：回归针长的70%
SL_RATIO         = 0.10   # 止损：针的最低点再下移 10%针长
MAX_HOLD_SECONDS = 30     # 最长持仓时间，超时强制平仓

# ── 趋势过滤 ──────────────────────────────────────────────────
MA_PERIOD        = 99
TREND_FILTER     = True   # True = 顺趋势方向才入场

# ── 轮询间隔 ──────────────────────────────────────────────────
POLL_INTERVAL_MS = 800    # REST轮询间隔（毫秒），低于1000以保持准1秒刷新
KLINE_LIMIT      = 120    # 每次拉取的1秒K线根数

# ── Web Dashboard ─────────────────────────────────────────────
WEB_HOST         = "0.0.0.0"
WEB_PORT         = 8888
WEB_SECRET       = "ctsi2024"  # dashboard 登录密码

# ── 风险控制 ──────────────────────────────────────────────────
DAILY_LOSS_LIMIT_USDT   = 10.0   # 每日最大亏损 USDT（触发熔断）
MAX_DRAWDOWN_PCT        = 5.0    # 最大回撤比例 %（触发熔断）
MAX_CONSECUTIVE_LOSSES  = 5      # 最大连续亏损次数（触发熔断）
MAX_DAILY_TRADES        = 200    # 每日最大交易次数
CIRCUIT_COOLDOWN_SEC    = 3600   # 熔断后冷却时间（秒）

# ── 日志 ─────────────────────────────────────────────────────
LOG_DIR          = "logs"
LOG_LEVEL        = "INFO"
