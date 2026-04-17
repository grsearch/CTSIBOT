"""
Spike Arbitrage Bot - 配置文件
所有参数均可通过 Dashboard 热更新，无需重启
"""

# ── Binance API ──────────────────────────────────────────────
API_KEY     = "YOUR_API_KEY"
API_SECRET  = "YOUR_API_SECRET"
BASE_URL    = "https://api.binance.com"

# ── 扫描模式 ─────────────────────────────────────────────────
# "single" = 只盯一个币
# "list"   = 手动指定列表
# "auto"   = 每15分钟查涨幅榜自动筛选
SCAN_MODE   = "single"
SYMBOL      = "CTSIUSDT"
BASE_ASSET  = "CTSI"
QUOTE_ASSET = "USDT"

SYMBOL_LIST = [
    "CTSIUSDT", "SOLUSDT", "SUIUSDT", "FETUSDT",
    "INJUSDT",  "ARBUSDT", "APEUSDT", "STXUSDT",
]

# auto 模式参数
AUTO_MIN_GAIN_PCT    = 15.0       # 24h涨幅绝对值 >= 此值
AUTO_MIN_VOLUME_USDT = 10_000_000 # 24h成交额 >= 此值
AUTO_MAX_SYMBOLS     = 10
AUTO_REFRESH_SEC     = 900        # 15分钟重新筛选

# ── 插针检测参数 ──────────────────────────────────────────────
SPIKE_RATIO  = 2.5    # 下影线/K线实体 >= 此值（真插针判断）
SPIKE_VS_ATR = 1.5    # 下影线/ATR(20) >= 此值（相对波动够大）
ATR_PERIOD   = 20
MIN_SPIKE_PIPS = 0.00005  # 针的最小长度（相对价格的比例）

# ── 入场条件 ──────────────────────────────────────────────────
# 当根1秒K线收盘后判断，下一根K线用市价单入场
# 触发要求：当根K线插针后已部分回归，处于 [MIN_RECOVERY, MAX_RECOVERY] 区间
#
# 为什么需要 MIN_RECOVERY（最小回归）：
#   == 0 时：价格可能还在针尖，还没确认反转，风险大
#   == 0.20：已回升20%，初步确认转折
#
# 为什么需要 MAX_RECOVERY（最大回归）：
#   == 1.0 时：已完全回到针根，没有利润空间了
#   == 0.70：还有30%空间留给止盈
#
MIN_RECOVERY = 0.15   # 已回归 >= 15% 才触发（确认开始反转）
MAX_RECOVERY = 0.45   # 已回归 <= 45% 才触发（保留足够利润空间）
                      # 数学推导：entry在40%处时R:R≈1.2，30%处R:R≈1.75

# ── 止盈止损（基于针尖计算，不受入场价影响）────────────────────
# BUY  示例：针尖=6.980，针长=0.020
#   tp = 6.980 + 0.020 * 0.75 = 6.995
#   sl = 6.980 - max(0.020*0.10, ATR*0.5)  ← 两者取大，自适应
#
# 风险收益比检查（代码会过滤 R:R < MIN_RR 的信号）：
#   TP距离 = tp - entry
#   SL距离 = entry - sl
#   R:R = TP距离 / SL距离，至少要 >= 1.5
#
TP_RATIO     = 1.0    # 止盈：entry到针根距离的100%（即到达针根=开盘价）
SL_RATIO     = 0.10   # 止损基础比例：针尖 - 针长 × 10%
SL_ATR_MULT  = 0.5    # 止损ATR倍数：针尖 - ATR × 0.5（两者取大）
MIN_RR       = 1.0    # 最低风险收益比（插针策略靠高胜率弥补R:R）

MAX_HOLD_SECONDS = 30  # 超时强制平仓

# ── 趋势过滤 ──────────────────────────────────────────────────
MA_PERIOD    = 99
TREND_FILTER = False   # True时：MA在价格上方则降低BUY信号评分

# ── 仓位与资金管理 ────────────────────────────────────────────
ORDER_USDT      = 20.0  # 每笔下单金额
MAX_OPEN_ORDERS = 2     # 同时最多持仓笔数

# ── 轮询 ─────────────────────────────────────────────────────
POLL_INTERVAL_MS = 800   # REST轮询间隔（毫秒）
KLINE_LIMIT      = 120   # 每次拉取K线根数

# ── 风险控制 ──────────────────────────────────────────────────
DAILY_LOSS_LIMIT_USDT  = 10.0  # 每日最大亏损，触发熔断
MAX_DRAWDOWN_PCT       = 5.0   # 最大回撤%，触发熔断
MAX_CONSECUTIVE_LOSSES = 5     # 最大连续亏损次数
MAX_DAILY_TRADES       = 200
CIRCUIT_COOLDOWN_SEC   = 3600  # 熔断冷却1小时

# ── 模式 ─────────────────────────────────────────────────────
DRY_RUN = False   # True=空跑模拟 / False=实盘

# ── Web Dashboard ─────────────────────────────────────────────
WEB_HOST = "0.0.0.0"
WEB_PORT = 8888

# ── 日志 ─────────────────────────────────────────────────────
LOG_DIR   = "logs"
LOG_LEVEL = "INFO"
