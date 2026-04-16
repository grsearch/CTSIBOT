"""
Dashboard v4
- Header: 去掉价格，改为币种数 + 今日PnL
- 监控Tab: 风控面板常驻解除熔断按钮
- 币种管理Tab: Auto模式改为涨幅榜筛选，显示筛选明细
- 参数/网格 Tab 保持不变
"""
import asyncio, json, logging, time, itertools, statistics
import config as cfg_module
from aiohttp import web
from bot import STATE

logger = logging.getLogger(__name__)

HTML = r"""<!DOCTYPE html>
<html lang="zh"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Spike Bot</title>
<style>
:root{--bg:#0a0c10;--s1:#111318;--s2:#181c24;--bd:#22283a;
--gr:#00d48a;--rd:#ff3d5a;--bl:#3d8eff;--am:#ffb020;--pu:#a855f7;
--tx:#dde3f0;--mt:#4a5568;--r:10px}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--tx);font-family:'SF Mono','Fira Code',monospace;font-size:12px}

header{background:var(--s1);border-bottom:1px solid var(--bd);
  padding:9px 18px;display:flex;align-items:center;gap:10px;
  position:sticky;top:0;z-index:100}
.dot{width:8px;height:8px;border-radius:50%;background:var(--mt);flex-shrink:0}
.dot.on{background:var(--gr);box-shadow:0 0 7px var(--gr);animation:blink 1.8s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}
h1{font-size:13px;font-weight:700;letter-spacing:.1em;color:var(--bl)}
.mode-badge{padding:2px 10px;border-radius:6px;font-size:10px;font-weight:700;letter-spacing:.06em}
.dry-badge{background:rgba(255,176,32,.15);color:var(--am);border:1px solid rgba(255,176,32,.3)}
.live-badge{background:rgba(0,212,138,.15);color:var(--gr);border:1px solid rgba(0,212,138,.3)}

/* header 右侧信息块 */
.hd-right{margin-left:auto;display:flex;align-items:center;gap:16px}
.hd-stat{display:flex;flex-direction:column;align-items:flex-end;gap:1px}
.hd-stat .lbl{font-size:9px;color:var(--mt);text-transform:uppercase;letter-spacing:.06em}
.hd-stat .val{font-size:14px;font-weight:700;line-height:1}
.hd-divider{width:1px;height:28px;background:var(--bd)}
.hd-time{font-size:10px;color:var(--mt)}

.tabs{background:var(--s1);border-bottom:1px solid var(--bd);display:flex;padding:0 18px}
.tab{padding:10px 16px;font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;
  color:var(--mt);cursor:pointer;border-bottom:2px solid transparent;transition:all .15s;user-select:none}
.tab:hover{color:var(--tx)}
.tab.active{color:var(--bl);border-bottom-color:var(--bl)}

.panel{display:none;padding:14px 18px;flex-direction:column;gap:12px}
.panel.active{display:flex}

.card{background:var(--s1);border:1px solid var(--bd);border-radius:var(--r);padding:12px 14px}
.ch{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.12em;
  color:var(--mt);margin-bottom:10px;display:flex;align-items:center;gap:8px}

.g4{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
.g3{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
@media(max-width:900px){.g4,.g3{grid-template-columns:repeat(2,1fr)}.g2{grid-template-columns:1fr}}

.sc .lb{font-size:9px;color:var(--mt);text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px}
.sc .vl{font-size:22px;font-weight:800;line-height:1.1}
.sc .sb{font-size:9px;color:var(--mt);margin-top:3px}
.gr{color:var(--gr)}.rd{color:var(--rd)}.bl{color:var(--bl)}.am{color:var(--am)}.pu{color:var(--pu)}

.tag{display:inline-block;padding:2px 7px;border-radius:3px;font-size:9px;font-weight:700}
.tag.buy{background:rgba(0,212,138,.12);color:var(--gr)}
.tag.sell{background:rgba(255,61,90,.12);color:var(--rd)}
.tag.tp{background:rgba(0,212,138,.12);color:var(--gr)}
.tag.sl{background:rgba(255,61,90,.12);color:var(--rd)}
.tag.timeout{background:rgba(61,142,255,.12);color:var(--bl)}

table{width:100%;border-collapse:collapse}
th{padding:5px 8px;text-align:left;font-size:9px;color:var(--mt);
  text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid var(--bd)}
td{padding:6px 8px;border-bottom:1px solid #13171f;font-size:11px}
tr:last-child td{border:none}
tr:hover td{background:#13171f}

.rb{height:4px;border-radius:2px;background:var(--s2);margin-top:5px;overflow:hidden}
.rf{height:100%;border-radius:2px;transition:width .5s}

.bdg{display:inline-block;padding:2px 8px;border-radius:8px;font-size:9px;font-weight:700}
.bdg.ok{background:rgba(0,212,138,.15);color:var(--gr)}
.bdg.ng{background:rgba(255,61,90,.15);color:var(--rd)}

button{background:transparent;border:1px solid var(--bd);color:var(--tx);
  padding:6px 14px;border-radius:6px;cursor:pointer;font-size:11px;
  font-family:inherit;transition:all .15s}
button:hover{border-color:var(--bl);color:var(--bl)}
button.danger{border-color:var(--rd);color:var(--rd)}
button.danger:hover{background:rgba(255,61,90,.08)}
button.primary{border-color:var(--bl);color:var(--bl)}
button.primary:hover{background:rgba(61,142,255,.08)}
button.success{border-color:var(--gr);color:var(--gr)}
button.success:hover{background:rgba(0,212,138,.08)}
button.warn{border-color:var(--am);color:var(--am)}
button.warn:hover{background:rgba(255,176,32,.08)}
button:disabled{opacity:.4;cursor:not-allowed}

/* 风控面板 */
.risk-panel{border:1px solid var(--bd);border-radius:var(--r);padding:12px 14px}
.risk-panel.tripped{border-color:rgba(255,61,90,.5);background:rgba(255,61,90,.04)}
.risk-panel.ok{border-color:var(--bd)}

/* circuit breaker box */
.cb-box{display:flex;align-items:center;gap:12px;padding:10px 14px;
  border-radius:8px;background:var(--s2);border:1px solid var(--bd);margin-top:10px}
.cb-box.tripped{background:rgba(255,61,90,.06);border-color:rgba(255,61,90,.4)}
.cb-box.ok{background:rgba(0,212,138,.04);border-color:rgba(0,212,138,.2)}
.cb-icon{font-size:18px}
.cb-text{flex:1}
.cb-title{font-size:12px;font-weight:700;margin-bottom:2px}
.cb-sub{font-size:10px;color:var(--mt)}

.form-row{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px}
.field{display:flex;flex-direction:column;gap:4px}
.field label{font-size:10px;color:var(--mt);text-transform:uppercase;letter-spacing:.06em}
.field input,.field select,.field textarea{background:var(--s2);border:1px solid var(--bd);
  color:var(--tx);padding:6px 10px;border-radius:6px;font-size:12px;font-family:inherit;outline:none;
  transition:border-color .15s}
.field input:focus,.field select:focus,.field textarea:focus{border-color:var(--bl)}
.field .hint{font-size:9px;color:var(--mt)}

.prog-bar{height:6px;border-radius:3px;background:var(--s2);margin:8px 0;overflow:hidden}
.prog-fill{height:100%;border-radius:3px;background:var(--bl);transition:width .3s}
.result-best{background:rgba(0,212,138,.05)}

/* gainer table */
.gain-pos{color:var(--gr);font-weight:700}
.gain-neg{color:var(--rd);font-weight:700}
.vol-bar{display:inline-block;height:6px;border-radius:3px;background:var(--bl);vertical-align:middle;margin-left:6px;opacity:.6}

/* symbol pills */
.sym-pill{display:inline-flex;align-items:center;gap:6px;background:var(--s2);
  border:1px solid var(--bd);border-radius:6px;padding:4px 10px;font-size:11px;margin:3px}
.pill-dot{width:6px;height:6px;border-radius:50%;background:var(--gr)}

/* scan countdown */
.countdown{font-size:10px;color:var(--mt);margin-top:8px}
.countdown span{color:var(--am);font-weight:700}

.logbox{height:130px;overflow-y:auto;padding:8px 10px;font-size:10px;
  line-height:1.8;background:var(--s2);border-radius:6px}
.logbox .e{color:var(--rd)}.logbox .i{color:var(--mt)}

.sep{border:none;border-top:1px solid var(--bd);margin:8px 0}
</style>
</head>
<body>
<header>
  <div class="dot" id="hDot"></div>
  <h1>SPIKE BOT</h1>
  <span class="mode-badge dry-badge" id="modeBadge">空跑</span>
  <span class="hd-time" id="hTime"></span>

  <div class="hd-right">
    <div class="hd-stat">
      <span class="lbl">监控币种</span>
      <span class="val am" id="hSymCount">0</span>
    </div>
    <div class="hd-divider"></div>
    <div class="hd-stat">
      <span class="lbl">今日收益</span>
      <span class="val" id="hDayPnl">+0.0000</span>
    </div>
    <div class="hd-divider"></div>
    <div class="hd-stat">
      <span class="lbl">总收益</span>
      <span class="val" id="hTotPnl">+0.0000</span>
    </div>
  </div>
</header>

<div class="tabs">
  <div class="tab active" onclick="showTab('monitor',this)">监控</div>
  <div class="tab" onclick="showTab('params',this)">参数设置</div>
  <div class="tab" onclick="showTab('grid',this)">网格搜索</div>
  <div class="tab" onclick="showTab('symbols',this)">币种管理</div>
</div>

<!-- ══════════ TAB: 监控 ══════════ -->
<div class="panel active" id="tab-monitor">
  <div class="g4">
    <div class="card sc"><div class="lb">胜率</div><div class="vl bl" id="wr">0%</div><div class="sb" id="wl">0W / 0L</div></div>
    <div class="card sc"><div class="lb">总交易</div><div class="vl am" id="totalT">0</div><div class="sb" id="openC">持仓 0</div></div>
    <div class="card sc"><div class="lb">信号发现</div><div class="vl bl" id="sigN">0</div><div class="sb" id="sigB">拦截 0</div></div>
    <div class="card sc"><div class="lb">扫描模式</div><div class="vl" id="scanModeHd" style="font-size:14px">—</div><div class="sb" id="scanCntHd">0 个币种</div></div>
  </div>

  <!-- 风控面板（常驻熔断按钮） -->
  <div class="card risk-panel" id="riskPanel">
    <div class="ch">
      风控状态
      <span class="bdg ok" id="riskBdg">✓ 正常</span>
    </div>
    <div class="g3">
      <div>
        <div style="font-size:9px;color:var(--mt);margin-bottom:3px">今日亏损</div>
        <div style="font-size:14px;font-weight:700" id="rLoss">0.00 / — USDT</div>
        <div class="rb"><div class="rf" id="rLossBar" style="background:var(--rd);width:0%"></div></div>
      </div>
      <div>
        <div style="font-size:9px;color:var(--mt);margin-bottom:3px">账户回撤</div>
        <div style="font-size:14px;font-weight:700" id="rDD">0.00%</div>
        <div class="rb"><div class="rf" id="rDDBar" style="background:var(--am);width:0%"></div></div>
      </div>
      <div>
        <div style="font-size:9px;color:var(--mt);margin-bottom:3px">连续亏损</div>
        <div style="font-size:14px;font-weight:700" id="rCons">0 次</div>
        <div class="rb"><div class="rf" id="rConsBar" style="background:var(--pu);width:0%"></div></div>
      </div>
    </div>
    <!-- 熔断状态框（常驻） -->
    <div class="cb-box ok" id="cbBox">
      <div class="cb-icon" id="cbIcon">✅</div>
      <div class="cb-text">
        <div class="cb-title" id="cbTitle">熔断器正常</div>
        <div class="cb-sub" id="cbSub">所有风控条件未触发，可正常交易</div>
      </div>
      <button class="danger" id="cbResetBtn" onclick="resetCircuit()" style="flex-shrink:0">
        解除熔断
      </button>
    </div>
  </div>

  <div class="g2">
    <div class="card">
      <div class="ch">当前持仓 <span class="am" id="openCnt">0</span></div>
      <table>
        <thead><tr><th>币种</th><th>方向</th><th>入场</th><th>TP</th><th>SL</th><th>持时</th><th>分</th></tr></thead>
        <tbody id="openTb"><tr><td colspan="7" style="text-align:center;color:var(--mt);padding:16px">无持仓</td></tr></tbody>
      </table>
    </div>
    <div class="card">
      <div class="ch">最近成交</div>
      <table>
        <thead><tr><th>币种</th><th>方向</th><th>入场</th><th>出场</th><th>原因</th><th>盈亏</th></tr></thead>
        <tbody id="tradeTb"><tr><td colspan="6" style="text-align:center;color:var(--mt);padding:16px">暂无</td></tr></tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <div class="ch">错误日志</div>
    <div class="logbox" id="logbox"><div class="i">等待运行...</div></div>
  </div>

  <div class="card" style="border-color:rgba(61,142,255,.2)">
    <div class="ch" style="color:var(--bl)">实时诊断
      <span style="font-weight:400;font-size:10px;color:var(--mt);margin-left:4px">— 为什么没有交易？</span>
    </div>
    <div id="diagBox" style="font-size:11px;line-height:2;color:var(--mt)">等待数据...</div>
  </div>
</div>

<!-- ══════════ TAB: 参数设置 ══════════ -->
<div class="panel" id="tab-params">
  <div class="card">
    <div class="ch">插针检测</div>
    <div class="form-row">
      <div class="field"><label>SPIKE_RATIO 针/实体倍数</label>
        <input type="number" id="p_SPIKE_RATIO" step="0.5" min="1">
        <span class="hint">针长 ÷ K线实体 ≥ 此值才触发</span></div>
      <div class="field"><label>SPIKE_VS_ATR 针/ATR倍数</label>
        <input type="number" id="p_SPIKE_VS_ATR" step="0.5" min="1">
        <span class="hint">针长 ÷ ATR(20) ≥ 此值</span></div>
      <div class="field"><label>RECOVERY_RATIO 最小回归比</label>
        <input type="number" id="p_RECOVERY_RATIO" step="0.05" min="0.1" max="0.95">
        <span class="hint">当根K线已回归针的 xx% 才入场</span></div>
      <div class="field"><label>MIN_SPIKE_PIPS 最小针长</label>
        <input type="number" id="p_MIN_SPIKE_PIPS" step="0.0001">
        <span class="hint">绝对值，过滤超小振幅</span></div>
    </div>
  </div>
  <div class="card">
    <div class="ch">止盈止损</div>
    <div class="form-row">
      <div class="field"><label>TP_RATIO 止盈比</label>
        <input type="number" id="p_TP_RATIO" step="0.05" min="0.3" max="0.99">
        <span class="hint">回归针长的 xx% 时止盈</span></div>
      <div class="field"><label>SL_RATIO 止损比</label>
        <input type="number" id="p_SL_RATIO" step="0.05" min="0.01" max="0.5">
        <span class="hint">针尖再延伸 xx% 为止损</span></div>
      <div class="field"><label>MAX_HOLD_SECONDS 最长持仓秒</label>
        <input type="number" id="p_MAX_HOLD_SECONDS" step="5" min="5">
        <span class="hint">超时强制平仓</span></div>
      <div class="field"><label>ORDER_USDT 单笔金额</label>
        <input type="number" id="p_ORDER_USDT" step="5" min="5">
        <span class="hint">每笔下单 USDT 金额</span></div>
    </div>
  </div>
  <div class="card">
    <div class="ch">风险控制</div>
    <div class="form-row">
      <div class="field"><label>DAILY_LOSS_LIMIT_USDT</label>
        <input type="number" id="p_DAILY_LOSS_LIMIT_USDT" step="1" min="1">
        <span class="hint">每日亏损上限触发熔断</span></div>
      <div class="field"><label>MAX_DRAWDOWN_PCT %</label>
        <input type="number" id="p_MAX_DRAWDOWN_PCT" step="0.5" min="1" max="50">
        <span class="hint">账户回撤上限触发熔断</span></div>
      <div class="field"><label>MAX_CONSECUTIVE_LOSSES</label>
        <input type="number" id="p_MAX_CONSECUTIVE_LOSSES" step="1" min="2" max="20">
        <span class="hint">连续亏损次数上限</span></div>
      <div class="field"><label>MAX_OPEN_ORDERS</label>
        <input type="number" id="p_MAX_OPEN_ORDERS" step="1" min="1" max="10">
        <span class="hint">同时最多持仓笔数</span></div>
    </div>
  </div>
  <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
    <button class="primary" onclick="applyParams()">应用参数（热更新，不需重启）</button>
    <button onclick="loadParams()">重新读取</button>
    <span id="paramMsg" style="font-size:11px"></span>
  </div>
  <div class="card" style="background:rgba(255,176,32,.03);border-color:rgba(255,176,32,.15)">
    <div class="ch" style="color:var(--am)">当前生效参数快照</div>
    <pre id="cfgSnapshot" style="font-size:10px;color:var(--mt);line-height:1.9;white-space:pre-wrap"></pre>
  </div>
</div>

<!-- ══════════ TAB: 网格搜索 ══════════ -->
<div class="panel" id="tab-grid">
  <div class="card">
    <div class="ch">搜索空间配置
      <span style="font-weight:400;font-size:10px;color:var(--mt);margin-left:4px">— 对所有当前监控的币种并行回测</span>
    </div>
    <div class="form-row">
      <div class="field"><label>SPIKE_RATIO 候选</label>
        <input type="text" id="g_spike_ratio" value="1.5,2.0,2.5,3.0">
        <span class="hint">逗号分隔多个值</span></div>
      <div class="field"><label>SPIKE_VS_ATR 候选</label>
        <input type="text" id="g_spike_atr" value="1.0,1.5,2.0,2.5"></div>
      <div class="field"><label>RECOVERY_RATIO 候选</label>
        <input type="text" id="g_recovery" value="0.30,0.40,0.50"></div>
      <div class="field"><label>TP_RATIO 候选</label>
        <input type="text" id="g_tp" value="0.55,0.65,0.75"></div>
      <div class="field"><label>SL_RATIO 候选</label>
        <input type="text" id="g_sl" value="0.08,0.12,0.18"></div>
      <div class="field"><label>MAX_HOLD_SECONDS 候选</label>
        <input type="text" id="g_hold" value="15,20,30"></div>
    </div>
    <div style="margin-top:10px;display:flex;gap:10px;align-items:center;flex-wrap:wrap">
      <div class="field" style="flex-direction:row;align-items:center;gap:8px;margin:0">
        <label style="white-space:nowrap;font-size:10px;color:var(--mt)">回测天数</label>
        <input type="number" id="g_days" value="2" min="1" max="7" style="width:60px">
      </div>
      <div class="field" style="flex-direction:row;align-items:center;gap:8px;margin:0">
        <label style="white-space:nowrap;font-size:10px;color:var(--mt)">优化目标</label>
        <select id="g_target">
          <option value="expectancy">期望值 expectancy</option>
          <option value="win_rate">胜率 win_rate</option>
          <option value="total_pnl">总PnL</option>
          <option value="sharpe">Sharpe</option>
        </select>
      </div>
      <button class="primary" id="gridBtn" onclick="startGrid()">开始搜索</button>
      <span id="gridCombo" style="font-size:10px;color:var(--mt)"></span>
    </div>
  </div>

  <!-- 进度 + 日志 -->
  <div class="card" id="gridProgressCard" style="display:none">
    <div class="ch">
      进度 <span id="gridPct" class="am">0%</span>
      <span id="gridStatus" style="font-weight:400;color:var(--mt);font-size:10px;margin-left:8px"></span>
    </div>
    <div class="prog-bar"><div class="prog-fill" id="gridBar" style="width:0%"></div></div>
    <div id="gridLog" style="margin-top:8px;font-size:10px;color:var(--mt);line-height:1.9"></div>
  </div>

  <!-- 汇总 Top10（跨所有币种） -->
  <div class="card" id="gridResultCard" style="display:none">
    <div class="ch">
      汇总 Top 10
      <span style="font-weight:400;font-size:10px;color:var(--mt);margin-left:4px">— 跨所有币种合并统计</span>
      <button class="success" style="margin-left:auto;padding:3px 10px;font-size:10px" onclick="applyBest()">应用最优参数</button>
    </div>
    <div style="overflow-x:auto">
    <table>
      <thead><tr>
        <th>#</th><th>SR</th><th>ATR</th><th>REC</th><th>TP</th><th>SL</th><th>HOLD</th>
        <th>总笔数</th><th>胜率</th><th>期望值</th><th>Sharpe</th><th>总PnL</th><th>覆盖币</th><th></th>
      </tr></thead>
      <tbody id="gridTb"></tbody>
    </table></div>
  </div>

  <!-- 按币种分开的结果 -->
  <div id="gridSymCards"></div>
</div>

<!-- ══════════ TAB: 币种管理 ══════════ -->
<div class="panel" id="tab-symbols">
  <div class="card">
    <div class="ch">扫描模式</div>
    <div style="display:flex;gap:14px;flex-wrap:wrap;margin-bottom:14px">
      <label style="display:flex;align-items:center;gap:6px;cursor:pointer">
        <input type="radio" name="scanMode" value="single" id="sm_single"> Single 单币种</label>
      <label style="display:flex;align-items:center;gap:6px;cursor:pointer">
        <input type="radio" name="scanMode" value="list" id="sm_list"> List 手动列表</label>
      <label style="display:flex;align-items:center;gap:6px;cursor:pointer">
        <input type="radio" name="scanMode" value="auto" id="sm_auto"> Auto 涨幅榜</label>
    </div>

    <!-- Single -->
    <div id="sm_single_opt">
      <div class="field" style="max-width:200px">
        <label>交易对</label>
        <input type="text" id="sym_single" placeholder="CTSIUSDT">
      </div>
    </div>

    <!-- List -->
    <div id="sm_list_opt" style="display:none">
      <div class="field">
        <label>交易对列表（每行或逗号分隔）</label>
        <textarea id="sym_list" rows="4" style="resize:vertical">CTSIUSDT
SOLUSDT
SUIUSDT
FETUSDT</textarea>
      </div>
    </div>

    <!-- Auto -->
    <div id="sm_auto_opt" style="display:none">
      <div style="background:rgba(61,142,255,.06);border:1px solid rgba(61,142,255,.2);
        border-radius:8px;padding:10px 14px;margin-bottom:12px;font-size:11px;color:var(--mt);line-height:1.8">
        每 <span class="am" id="refreshMinDisplay">15</span> 分钟查一次 Binance 24h 涨幅榜，
        筛选 <span class="bl">|涨幅| ≥ 设定值</span> 且 <span class="bl">成交量 ≥ 设定值</span> 的币，
        按涨幅绝对值从高到低取前 N 个。<br>
        大涨大跌 = 市场情绪激烈 = <span class="gr">插针出现概率更高</span>。
      </div>
      <div class="form-row">
        <div class="field">
          <label>最小涨幅绝对值 %</label>
          <input type="number" id="auto_gain" value="15" min="5" max="200" step="5">
          <span class="hint">|涨幅| ≥ 此值（涨跌均算）</span>
        </div>
        <div class="field">
          <label>最低24h成交量 (USDT)</label>
          <input type="number" id="auto_vol" value="10000000" step="1000000">
          <span class="hint">10000000 = 10M USDT</span>
        </div>
        <div class="field">
          <label>最多监控币数</label>
          <input type="number" id="auto_max_n" value="10" min="1" max="20">
        </div>
        <div class="field">
          <label>刷新间隔 (分钟)</label>
          <input type="number" id="auto_refresh_min" value="15" min="5" max="60"
            oninput="document.getElementById('refreshMinDisplay').textContent=this.value">
        </div>
      </div>
    </div>

    <div style="margin-top:12px;display:flex;gap:10px;align-items:center;flex-wrap:wrap">
      <button class="primary" onclick="applySymbols()">应用</button>
      <button class="warn" onclick="forceRescan()" id="rescanBtn">立即重新扫描</button>
      <span id="symMsg" style="font-size:11px"></span>
    </div>
  </div>

  <!-- 活跃币种 + 涨幅榜详情 -->
  <div class="card">
    <div class="ch">
      当前活跃币种
      <span style="margin-left:auto;font-size:10px;color:var(--mt)">
        下次刷新: <span class="am" id="nextRefresh">—</span>
      </span>
    </div>
    <div id="activePills" style="min-height:32px;margin-bottom:8px"></div>
    <div style="font-size:10px;color:var(--mt)">
      模式: <span class="am" id="scanModeLabel">—</span>
    </div>
  </div>

  <!-- Auto 模式下显示涨幅榜明细 -->
  <div class="card" id="gainerDetailCard" style="display:none">
    <div class="ch">涨幅榜明细（最近一次扫描）</div>
    <table>
      <thead><tr><th>#</th><th>币种</th><th>24h涨幅</th><th>振幅</th><th>成交量</th></tr></thead>
      <tbody id="gainerTb"></tbody>
    </table>
  </div>
</div>

<script>
// ── Tab 切换 ──────────────────────────────────────────────
function showTab(name, el){
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('tab-'+name).classList.add('active');
}

// ── SSE ──────────────────────────────────────────────────
const es = new EventSource('/stream');
let _D = {};
es.onmessage = e => {
  _D = JSON.parse(e.data);
  renderAll(_D);
};

const fmt  = (v,n=4) => (v>=0?'+':'')+v.toFixed(n);
const fmtP = v => v.toFixed(6);
const clamp= (v,lo,hi) => Math.min(Math.max(v,lo),hi);

function renderAll(d){
  renderHeader(d);
  renderMonitor(d);
  renderSymbolTab(d);
  if(d.live_config) fillParams(d.live_config);
  renderGrid(d);
}

function renderHeader(d){
  document.getElementById('hDot').className = 'dot'+(d.running?' on':'');
  document.getElementById('hTime').textContent =
    d.last_tick ? new Date(d.last_tick*1000).toLocaleTimeString('zh') : '';

  const dry = d.dry_run;
  const mb = document.getElementById('modeBadge');
  mb.textContent = dry ? '空跑 DRY-RUN' : '实盘 LIVE';
  mb.className = 'mode-badge '+(dry?'dry-badge':'live-badge');

  const symN = (d.symbols_active||[]).length;
  document.getElementById('hSymCount').textContent = symN;

  const dp = d.risk ? d.risk.daily_pnl||0 : 0;
  const tp = d.stats ? d.stats.total_pnl||0 : 0;
  const dpEl = document.getElementById('hDayPnl');
  dpEl.textContent = fmt(dp); dpEl.className='val '+(dp>=0?'gr':'rd');
  const tpEl = document.getElementById('hTotPnl');
  tpEl.textContent = fmt(tp); tpEl.className='val '+(tp>=0?'gr':'rd');
}

function renderMonitor(d){
  const DL = d.live_config?.DAILY_LOSS_LIMIT_USDT || 10;
  const MD = d.live_config?.MAX_DRAWDOWN_PCT || 5;
  const MC = d.live_config?.MAX_CONSECUTIVE_LOSSES || 5;

  document.getElementById('wr').textContent = (d.stats?.win_rate||0)+'%';
  document.getElementById('wl').textContent = (d.stats?.win||0)+'W / '+(d.stats?.loss||0)+'L';
  document.getElementById('totalT').textContent = d.stats?.total_trades||0;
  document.getElementById('openC').textContent = '持仓 '+(d.stats?.open_count||0);
  document.getElementById('sigN').textContent = d.signals_found||0;
  document.getElementById('sigB').textContent = '拦截 '+(d.signals_blocked||0);
  document.getElementById('scanModeHd').textContent = (d.scan_mode||'—').toUpperCase();
  document.getElementById('scanCntHd').textContent = (d.symbols_active||[]).length+' 个币种';

  if(d.risk){
    const rk = d.risk;
    const bdg = document.getElementById('riskBdg');
    bdg.textContent = rk.can_trade ? '✓ 正常' : '✗ 熔断';
    bdg.className = 'bdg '+(rk.can_trade?'ok':'ng');

    const la = Math.abs(Math.min(rk.daily_pnl||0, 0));
    document.getElementById('rLoss').textContent = la.toFixed(2)+' / '+DL+' USDT';
    document.getElementById('rLossBar').style.width = clamp(la/DL*100,0,100)+'%';
    document.getElementById('rDD').textContent = (rk.drawdown_pct||0).toFixed(2)+'%';
    document.getElementById('rDDBar').style.width = clamp((rk.drawdown_pct||0)/MD*100,0,100)+'%';
    document.getElementById('rCons').textContent = (rk.consecutive_losses||0)+' 次';
    document.getElementById('rConsBar').style.width = clamp((rk.consecutive_losses||0)/MC*100,0,100)+'%';

    // 熔断框（常驻）
    const cbBox = document.getElementById('cbBox');
    const tripped = rk.circuit_broken;
    cbBox.className = 'cb-box '+(tripped?'tripped':'ok');
    document.getElementById('cbIcon').textContent = tripped ? '🔴' : '✅';
    document.getElementById('cbTitle').textContent = tripped ? '熔断已触发！' : '熔断器正常';
    document.getElementById('cbSub').textContent = tripped
      ? '原因: '+rk.circuit_reason
      : '所有风控条件未触发，可正常交易';
    document.getElementById('cbResetBtn').disabled = !tripped;
    document.getElementById('cbResetBtn').style.opacity = tripped ? '1' : '0.3';
  }

  // 持仓
  document.getElementById('openCnt').textContent = d.stats?.open_count||0;
  const ob = document.getElementById('openTb');
  ob.innerHTML = !d.open_positions?.length
    ? '<tr><td colspan="7" style="text-align:center;color:var(--mt);padding:14px">无持仓</td></tr>'
    : d.open_positions.map(p => `<tr>
        <td class="am">${p.symbol}</td>
        <td><span class="tag ${p.direction.toLowerCase()}">${p.direction}</span></td>
        <td>${fmtP(p.entry_price)}</td>
        <td class="gr">${fmtP(p.take_profit)}</td>
        <td class="rd">${fmtP(p.stop_loss)}</td>
        <td>${p.age_seconds.toFixed(0)}s</td>
        <td class="am">${p.signal_score||'—'}</td>
      </tr>`).join('');

  const tb = document.getElementById('tradeTb');
  tb.innerHTML = !d.recent_trades?.length
    ? '<tr><td colspan="6" style="text-align:center;color:var(--mt);padding:14px">暂无</td></tr>'
    : [...d.recent_trades].reverse().map(t => {
        const pc = t.pnl_usdt>=0 ? 'var(--gr)' : 'var(--rd)';
        return `<tr>
          <td class="am">${t.symbol}</td>
          <td><span class="tag ${t.direction.toLowerCase()}">${t.direction}</span></td>
          <td>${fmtP(t.entry_price)}</td>
          <td>${fmtP(t.close_price)}</td>
          <td><span class="tag ${t.close_reason.toLowerCase()}">${t.close_reason}</span></td>
          <td style="color:${pc};font-weight:700">${fmt(t.pnl_usdt)}</td>
        </tr>`;
      }).join('');

  // 实时诊断
  if(d.diag){
    const dg = d.diag;
    let lines = [];
    lines.push(`📡 <span style="color:var(--tx)">最新K线</span>: open=${dg.last_open?.toFixed(6)||'—'} high=${dg.last_high?.toFixed(6)||'—'} low=${dg.last_low?.toFixed(6)||'—'} close=${dg.last_close?.toFixed(6)||'—'}`);
    lines.push(`📏 <span style="color:var(--tx)">下影线</span>: ${dg.lower_wick?.toFixed(6)||'—'} &nbsp;|&nbsp; 上影线: ${dg.upper_wick?.toFixed(6)||'—'} &nbsp;|&nbsp; 实体: ${dg.body?.toFixed(6)||'—'}`);
    lines.push(`📊 <span style="color:var(--tx)">ATR(20)</span>: ${dg.atr?.toFixed(6)||'—'} &nbsp;|&nbsp; 针/实体比: ${dg.ratio_body?.toFixed(2)||'—'} (需≥${dg.cfg_spike_ratio||'—'}) &nbsp;|&nbsp; 针/ATR比: ${dg.ratio_atr?.toFixed(2)||'—'} (需≥${dg.cfg_spike_atr||'—'})`);
    const passBody = dg.ratio_body >= dg.cfg_spike_ratio;
    const passAtr  = dg.ratio_atr  >= dg.cfg_spike_atr;
    const passRec  = dg.recovery   >= dg.cfg_recovery;
    lines.push(`🔍 <span style="color:var(--tx)">检测结果</span>: 针/实体 ${passBody?'<span style="color:var(--gr)">✓</span>':'<span style="color:var(--rd)">✗</span>'} &nbsp; 针/ATR ${passAtr?'<span style="color:var(--gr)">✓</span>':'<span style="color:var(--rd)">✗</span>'} &nbsp; 回归比${dg.recovery?.toFixed(2)||'—'} ${passRec?'<span style="color:var(--gr)">✓</span>':'<span style="color:var(--rd)">✗</span>'}`);
    if(d.signals_found>0) lines.push(`✅ <span style="color:var(--gr)">已发现 ${d.signals_found} 个信号</span>${d.dry_run?' (空跑未下单)':''}`);
    else lines.push(`⏳ <span style="color:var(--am)">暂无信号 — 等待符合条件的插针出现</span>`);
    document.getElementById('diagBox').innerHTML = lines.join('<br>');
  }

  if(d.errors?.length){
    document.getElementById('logbox').innerHTML =
      d.errors.map(e=>`<div class="e">✗ ${e}</div>`).join('');
  }
}

// ── 参数面板 ──────────────────────────────────────────────
let _userEditingParams = false;
let _paramEditTimer = null;
function _markParamEditing(){
  _userEditingParams = true;
  clearTimeout(_paramEditTimer);
  _paramEditTimer = setTimeout(()=>{ _userEditingParams=false; }, 10000);
}
// Lock params form on any focus
document.querySelectorAll('[id^="p_"]').forEach(el=>{
  if(el) el.addEventListener('focus', _markParamEditing);
});

function fillParams(cfg){
  const keys = ['SPIKE_RATIO','SPIKE_VS_ATR','RECOVERY_RATIO','MIN_SPIKE_PIPS',
    'TP_RATIO','SL_RATIO','MAX_HOLD_SECONDS','ORDER_USDT',
    'DAILY_LOSS_LIMIT_USDT','MAX_DRAWDOWN_PCT','MAX_CONSECUTIVE_LOSSES','MAX_OPEN_ORDERS'];
  if(_userEditingParams) return;  // 用户正在编辑，不覆盖
  keys.forEach(k => {
    const el = document.getElementById('p_'+k);
    if(el && document.activeElement !== el) el.value = cfg[k] ?? '';
  });
  document.getElementById('cfgSnapshot').textContent = JSON.stringify(cfg, null, 2);
}
function loadParams(){ if(_D.live_config) fillParams(_D.live_config); }
function applyParams(){
  const keys = ['SPIKE_RATIO','SPIKE_VS_ATR','RECOVERY_RATIO','MIN_SPIKE_PIPS',
    'TP_RATIO','SL_RATIO','MAX_HOLD_SECONDS','ORDER_USDT',
    'DAILY_LOSS_LIMIT_USDT','MAX_DRAWDOWN_PCT','MAX_CONSECUTIVE_LOSSES','MAX_OPEN_ORDERS'];
  const updates = {};
  keys.forEach(k => {
    const el = document.getElementById('p_'+k);
    if(el && el.value !== '') updates[k] = parseFloat(el.value);
  });
  post('/api/set_params', updates).then(d => {
    const msg = document.getElementById('paramMsg');
    msg.textContent = d.ok ? '✓ 已应用: '+d.changed.join(', ') : '✗ '+d.error;
    msg.style.color = d.ok ? 'var(--gr)' : 'var(--rd)';
    setTimeout(()=>msg.textContent='', 4000);
  });
}

// ── 网格搜索 ──────────────────────────────────────────────
function calcCombos(){
  let n = 1;
  ['g_spike_ratio','g_spike_atr','g_recovery','g_tp','g_sl','g_hold'].forEach(id => {
    n *= document.getElementById(id).value.split(',').filter(x=>x.trim()).length || 1;
  });
  document.getElementById('gridCombo').textContent = '共 '+n+' 种组合';
}
document.querySelectorAll('#tab-grid input[type=text]').forEach(el=>el.addEventListener('input',calcCombos));
calcCombos();

function startGrid(){
  const p = {
    spike_ratio: document.getElementById('g_spike_ratio').value.split(',').map(Number).filter(Boolean),
    spike_atr:   document.getElementById('g_spike_atr').value.split(',').map(Number).filter(Boolean),
    recovery:    document.getElementById('g_recovery').value.split(',').map(Number).filter(Boolean),
    tp:          document.getElementById('g_tp').value.split(',').map(Number).filter(Boolean),
    sl:          document.getElementById('g_sl').value.split(',').map(Number).filter(Boolean),
    hold:        document.getElementById('g_hold').value.split(',').map(Number).filter(Boolean),
    days:        parseInt(document.getElementById('g_days').value)||2,
    target:      document.getElementById('g_target').value,
  };
  document.getElementById('gridProgressCard').style.display = 'block';
  document.getElementById('gridBtn').disabled = true;
  post('/api/grid_search', p).then(d => { if(!d.ok) alert('启动失败: '+d.error); });
}
function renderGrid(d){
  const hasActivity = d.grid_running || d.grid_progress > 0;
  if(!hasActivity && !d.grid_results?.length && !d.grid_sym_results) return;

  if(hasActivity || d.grid_progress > 0){
    document.getElementById('gridProgressCard').style.display = 'block';
    const pct = d.grid_total > 0 ? Math.round(d.grid_progress/d.grid_total*100) : 0;
    document.getElementById('gridPct').textContent = pct+'%';
    document.getElementById('gridBar').style.width = pct+'%';
    document.getElementById('gridStatus').textContent =
      d.grid_running
        ? `${d.grid_progress} / ${d.grid_total}`
        : '✓ 搜索完成';
    if(!d.grid_running) document.getElementById('gridBtn').disabled = false;
  }

  // 进度日志
  if(d.grid_log?.length){
    document.getElementById('gridLog').innerHTML =
      d.grid_log.map(l => `<div>→ ${l}</div>`).join('');
  }

  // 汇总 Top10
  if(d.grid_results?.length){
    document.getElementById('gridResultCard').style.display = 'block';
    document.getElementById('gridTb').innerHTML = d.grid_results.slice(0,10).map((r,i) => `
      <tr class="${i===0?'result-best':''}">
        <td class="${i===0?'gr':''}">${i+1}</td>
        <td>${r.p.SPIKE_RATIO}</td><td>${r.p.SPIKE_VS_ATR}</td>
        <td>${r.p.RECOVERY_RATIO}</td><td>${r.p.TP_RATIO}</td>
        <td>${r.p.SL_RATIO}</td><td>${r.p.MAX_HOLD_SECONDS}</td>
        <td>${r.m.n}</td>
        <td class="${r.m.win_rate>=55?'gr':'rd'}">${r.m.win_rate}%</td>
        <td class="${r.m.expectancy>0?'gr':'rd'}">${r.m.expectancy.toFixed(5)}</td>
        <td>${r.m.sharpe.toFixed(3)}</td>
        <td class="${r.m.total_pnl>0?'gr':'rd'}">${r.m.total_pnl.toFixed(4)}</td>
        <td class="am">${r.m.symbols_covered||'—'}</td>
        <td><button style="padding:2px 8px;font-size:9px" onclick="applyRow(${i})">应用</button></td>
      </tr>`).join('');
  }

  // 按币种分开展示
  if(d.grid_sym_results && Object.keys(d.grid_sym_results).length){
    const container = document.getElementById('gridSymCards');
    container.innerHTML = Object.entries(d.grid_sym_results).map(([sym, results]) => {
      if(!results?.length) return '';
      const rows = results.slice(0,5).map((r,i) => `
        <tr class="${i===0?'result-best':''}">
          <td class="${i===0?'gr':''}">${i+1}</td>
          <td>${r.p.SPIKE_RATIO}</td><td>${r.p.SPIKE_VS_ATR}</td>
          <td>${r.p.RECOVERY_RATIO}</td><td>${r.p.TP_RATIO}</td>
          <td>${r.p.SL_RATIO}</td><td>${r.p.MAX_HOLD_SECONDS}</td>
          <td>${r.m.n}</td>
          <td class="${r.m.win_rate>=55?'gr':'rd'}">${r.m.win_rate}%</td>
          <td class="${r.m.expectancy>0?'gr':'rd'}">${r.m.expectancy.toFixed(5)}</td>
          <td>${r.m.sharpe.toFixed(3)}</td>
          <td class="${r.m.total_pnl>0?'gr':'rd'}">${r.m.total_pnl.toFixed(4)}</td>
          <td><button style="padding:2px 8px;font-size:9px" onclick="applySymRow('${sym}',${i})">应用</button></td>
        </tr>`).join('');
      return \`
        <div class="card" style="margin-top:0">
          <div class="ch"><span class="am">${sym}</span>
            <span style="font-weight:400;color:var(--mt);font-size:10px;margin-left:6px">Top 5</span>
          </div>
          <div style="overflow-x:auto">
          <table><thead><tr>
            <th>#</th><th>SR</th><th>ATR</th><th>REC</th><th>TP</th><th>SL</th><th>HOLD</th>
            <th>N</th><th>胜率</th><th>期望值</th><th>Sharpe</th><th>PnL</th><th></th>
          </tr></thead><tbody>${rows}</tbody></table>
          </div>
        </div>\`;
    }).join('');
  }
}

function applyBest(){ if(_D.grid_best) applyGridParams(_D.grid_best); }
function applyRow(i){ if(_D.grid_results?.[i]) applyGridParams(_D.grid_results[i].p); }
function applySymRow(sym, i){
  const r = _D.grid_sym_results?.[sym]?.[i];
  if(r) applyGridParams(r.p);
}
function applyGridParams(p){
  if(!confirm('应用这组参数到当前配置？')) return;
  post('/api/set_params', p).then(d => {
    alert(d.ok ? '✓ 已应用: '+d.changed.join(', ') : '✗ '+d.error);
  });
}

// ── 币种管理 ─────────────────────────────────────────────
// 用户正在操作表单时，SSE 推送不覆盖选项（防止闪退）
let _userEditingSymbols = false;
let _userEditTimer = null;

function _markUserEditing(){
  _userEditingSymbols = true;
  clearTimeout(_userEditTimer);
  _userEditTimer = setTimeout(() => { _userEditingSymbols = false; }, 8000);
}

document.querySelectorAll('input[name=scanMode]').forEach(r => {
  r.addEventListener('mousedown', _markUserEditing);
  r.addEventListener('change', () => {
    _markUserEditing();
    ['single','list','auto'].forEach(m =>
      document.getElementById('sm_'+m+'_opt').style.display = r.value===m?'block':'none'
    );
  });
});
// 任意表单元素交互都锁定
['sym_single','sym_list','auto_gain','auto_vol','auto_max_n','auto_refresh_min'].forEach(id => {
  const el = document.getElementById(id);
  if(el) el.addEventListener('focus', _markUserEditing);
});

function _showModeOpts(mode){
  ['single','list','auto'].forEach(m =>
    document.getElementById('sm_'+m+'_opt').style.display = m===mode?'block':'none'
  );
}

function renderSymbolTab(d){
  const mode = d.scan_mode || 'single';
  document.getElementById('scanModeLabel').textContent = mode;

  // ★ 只有用户没在操作时才同步 radio 和面板显示
  if(!_userEditingSymbols){
    const rb = document.querySelector(`input[name=scanMode][value=${mode}]`);
    if(rb && !rb.checked){
      rb.checked = true;
      _showModeOpts(mode);
    }
  }

  if(d.live_config?.SYMBOL){
    const el = document.getElementById('sym_single');
    if(el && document.activeElement!==el) el.value = d.live_config.SYMBOL;
  }

  // 活跃币种 pills（带当前价格）
  const syms   = d.symbols_active || [];
  const prices = d.prices || {};
  document.getElementById('activePills').innerHTML = syms.length===0
    ? '<span style="color:var(--mt);font-size:11px">无活跃币种</span>'
    : syms.map(s => `
        <span class="sym-pill">
          <span class="pill-dot"></span>
          <span class="am">${s}</span>
          ${prices[s] ? `<span style="color:var(--mt)">${prices[s].toFixed(prices[s]<0.01?6:4)}</span>` : ''}
        </span>`).join('');

  // 下次刷新倒计时
  if(d.next_refresh_in !== undefined){
    const sec = Math.round(d.next_refresh_in);
    const mm = Math.floor(sec/60), ss = sec%60;
    document.getElementById('nextRefresh').textContent =
      mode==='auto' ? `${mm}:${ss.toString().padStart(2,'0')}` : '—';
  }

  // Auto 模式涨幅榜明细
  const gCard = document.getElementById('gainerDetailCard');
  if(mode==='auto' && d.gainer_detail?.length){
    gCard.style.display = 'block';
    const maxVol = Math.max(...d.gainer_detail.map(g=>g.vol_usdt));
    document.getElementById('gainerTb').innerHTML = d.gainer_detail.map((g,i) => {
      const barW = Math.round(g.vol_usdt/maxVol*80);
      const gainCls = g.gain_pct>=0 ? 'gain-pos' : 'gain-neg';
      const gainStr = (g.gain_pct>=0?'+':'')+g.gain_pct.toFixed(2)+'%';
      const volStr  = (g.vol_usdt/1e6).toFixed(1)+'M';
      return `<tr>
        <td style="color:var(--mt)">${i+1}</td>
        <td class="am">${g.symbol}</td>
        <td class="${gainCls}">${gainStr}</td>
        <td style="color:var(--mt)">${g.amp_pct.toFixed(2)}%</td>
        <td>${volStr}<span class="vol-bar" style="width:${barW}px"></span></td>
      </tr>`;
    }).join('');
  } else {
    gCard.style.display = 'none';
  }

  // 同步 auto 表单值
  if(d.live_config){
    const cfg = d.live_config;
    ['auto_gain','auto_vol','auto_max_n'].forEach((id,i) => {
      const el=document.getElementById(id);
      const keys=['AUTO_MIN_GAIN_PCT','AUTO_MIN_VOLUME_USDT','AUTO_MAX_SYMBOLS'];
      if(el && document.activeElement!==el && cfg[keys[i]]!=null) el.value=cfg[keys[i]];
    });
    const rm=document.getElementById('auto_refresh_min');
    if(rm && document.activeElement!==rm && cfg.AUTO_REFRESH_SEC!=null){
      rm.value=Math.round(cfg.AUTO_REFRESH_SEC/60);
      document.getElementById('refreshMinDisplay').textContent=rm.value;
    }
  }
}

function applySymbols(){
  const mode = document.querySelector('input[name=scanMode]:checked')?.value || 'single';
  const updates = {SCAN_MODE: mode};
  if(mode==='single'){
    updates.SYMBOL = document.getElementById('sym_single').value.trim().toUpperCase();
  } else if(mode==='list'){
    updates.SYMBOL_LIST = document.getElementById('sym_list').value
      .split(/[\n,]+/).map(s=>s.trim().toUpperCase()).filter(Boolean);
  } else {
    updates.AUTO_MIN_GAIN_PCT    = parseFloat(document.getElementById('auto_gain').value)||30;
    updates.AUTO_MIN_VOLUME_USDT = parseFloat(document.getElementById('auto_vol').value)||20000000;
    updates.AUTO_MAX_SYMBOLS     = parseInt(document.getElementById('auto_max_n').value)||10;
    updates.AUTO_REFRESH_SEC     = parseInt(document.getElementById('auto_refresh_min').value||15)*60;
  }
  post('/api/set_params', updates).then(d=>{
    const msg=document.getElementById('symMsg');
    msg.textContent = d.ok ? '✓ 已应用' : '✗ '+d.error;
    msg.style.color = d.ok ? 'var(--gr)' : 'var(--rd)';
    setTimeout(()=>msg.textContent='', 3000);
  });
}

function forceRescan(){
  post('/api/force_rescan',{}).then(d=>{
    document.getElementById('symMsg').textContent='✓ 正在重新扫描...';
    document.getElementById('symMsg').style.color='var(--am)';
    setTimeout(()=>document.getElementById('symMsg').textContent='',4000);
  });
}

function resetCircuit(){
  post('/api/reset_circuit',{}).then(d=>console.log('reset:',d));
}

// ── 工具函数 ──────────────────────────────────────────────
function post(url, body){
  return fetch(url, {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify(body)
  }).then(r=>r.json()).catch(e=>({ok:false,error:String(e)}));
}
</script>
</body></html>"""


# ─── SSE stream handler ──────────────────────────────────────
async def handle_stream(req):
    resp = web.StreamResponse()
    resp.headers.update({
        "Content-Type":  "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection":    "keep-alive",
    })
    await resp.prepare(req)
    try:
        while True:
            pm = STATE.get("positions")
            rm = STATE.get("risk")
            # 尝试获取 scanner 的涨幅详情和倒计时
            scanner = None
            from bot import _bot_instance
            if _bot_instance:
                scanner = getattr(_bot_instance, 'scanner', None)

            stats = {"total_trades":0,"win":0,"loss":0,"win_rate":0,"total_pnl":0,"open_count":0}
            open_pos, recent_trades = [], []
            if pm:
                stats = pm.stats
                for p in pm.open_positions:
                    open_pos.append({
                        "id":p.id, "symbol":p.symbol, "direction":p.direction,
                        "entry_price":p.entry_price, "take_profit":p.take_profit,
                        "stop_loss":p.stop_loss, "age_seconds":round(p.age_seconds,1),
                        "signal_score":p.signal_score,
                    })
                for t in pm.get_recent_trades(15):
                    recent_trades.append({
                        "id":t.id, "symbol":t.symbol, "direction":t.direction,
                        "entry_price":t.entry_price, "close_price":t.close_price,
                        "close_reason":t.close_reason, "pnl_usdt":t.pnl_usdt,
                    })

            next_refresh_in = 0
            gainer_detail   = []
            if scanner:
                interval = getattr(cfg_module, "AUTO_REFRESH_SEC", 900)
                elapsed  = time.time() - scanner._last_refresh
                next_refresh_in = max(0, interval - elapsed)
                gainer_detail   = scanner.last_scan_detail

            payload = {
                "running":          STATE.get("running",False),
                "dry_run":          STATE.get("dry_run",False),
                "scan_mode":        STATE.get("scan_mode","single"),
                "symbols_active":   STATE.get("symbols_active",[]),
                "prices":           STATE.get("prices",{}),
                "last_tick":        STATE.get("last_tick",0),
                "signals_found":    STATE.get("signals_found",0),
                "signals_blocked":  STATE.get("signals_blocked",0),
                "stats":            stats,
                "open_positions":   open_pos,
                "recent_trades":    recent_trades,
                "risk":             rm.status_dict if rm else None,
                "live_config":      STATE.get("live_config",{}),
                "errors":           STATE.get("errors",[])[-12:],
                "grid_running":     STATE.get("grid_running",False),
                "grid_progress":    STATE.get("grid_progress",0),
                "grid_total":       STATE.get("grid_total",0),
                "grid_results":     STATE.get("grid_results",[])[:10],
                "grid_best":        STATE.get("grid_best"),
                "grid_sym_results": STATE.get("grid_sym_results",{}),
                "grid_log":         STATE.get("grid_log",[])[-8:],
                "next_refresh_in":  round(next_refresh_in),
                "gainer_detail":    gainer_detail,
                "diag":             STATE.get("diag", {}),
            }
            await resp.write(f"data: {json.dumps(payload)}\n\n".encode())
            await asyncio.sleep(1)
    except (ConnectionResetError, asyncio.CancelledError):
        pass
    return resp


# ─── API handlers ─────────────────────────────────────────────
async def handle_index(req):
    return web.Response(text=HTML, content_type="text/html")


async def handle_set_params(req):
    try:
        updates = await req.json()
        from bot import _bot_instance
        if _bot_instance:
            changed = _bot_instance.apply_live_config(updates)
            return web.json_response({"ok": True, "changed": changed})
        import config as cm
        for k, v in updates.items():
            if hasattr(cm, k): setattr(cm, k, v)
        return web.json_response({"ok": True, "changed": list(updates.keys())})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})


async def handle_reset_circuit(req):
    rm = STATE.get("risk")
    if rm:
        rm.manual_reset()
        return web.json_response({"ok": True, "msg": "熔断已解除"})
    return web.json_response({"ok": False, "error": "risk manager not init"})


async def handle_force_rescan(req):
    from bot import _bot_instance
    if _bot_instance and hasattr(_bot_instance, 'scanner'):
        syms = await _bot_instance.scanner.force_refresh()
        return web.json_response({"ok": True, "symbols": syms})
    return web.json_response({"ok": False, "error": "scanner not ready"})


async def handle_grid_search(req):
    if STATE.get("grid_running"):
        return web.json_response({"ok": False, "error": "已有搜索在运行"})
    try:
        body = await req.json()
        asyncio.create_task(_run_grid_search(body))
        return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})


async def _run_grid_search(params: dict):
    """
    多币种网格搜索：
    1. 获取当前所有活跃币种
    2. 每个币种独立拉取历史K线
    3. 对所有参数组合回测，收集每笔交易PnL
    4. 按币种分开显示 + 汇总跨币种排名
    """
    from core.exchange import BinanceREST
    from strategy.detector import SpikeDetector, Candle

    STATE["grid_running"]     = True
    STATE["grid_progress"]    = 0
    STATE["grid_total"]       = 0
    STATE["grid_results"]     = []
    STATE["grid_best"]        = None
    STATE["grid_sym_results"] = {}
    STATE["grid_log"]         = []

    def log(msg):
        STATE["grid_log"].append(msg)
        STATE["grid_log"] = STATE["grid_log"][-30:]
        logger.info(f"[Grid] {msg}")

    try:
        # ── 1. 确定要回测的币种列表 ──────────────────────────
        symbols = list(STATE.get("symbols_active", []))
        if not symbols:
            symbols = [cfg_module.SYMBOL]
        log(f"回测币种: {symbols}")

        days   = params.get("days", 2)
        target = params.get("target", "expectancy")

        grid = {
            "SPIKE_RATIO":      params.get("spike_ratio", [cfg_module.SPIKE_RATIO]),
            "SPIKE_VS_ATR":     params.get("spike_atr",   [cfg_module.SPIKE_VS_ATR]),
            "RECOVERY_RATIO":   params.get("recovery",    [cfg_module.RECOVERY_RATIO]),
            "TP_RATIO":         params.get("tp",          [cfg_module.TP_RATIO]),
            "SL_RATIO":         params.get("sl",          [cfg_module.SL_RATIO]),
            "MAX_HOLD_SECONDS": params.get("hold",        [cfg_module.MAX_HOLD_SECONDS]),
        }
        keys   = list(grid.keys())
        combos = list(itertools.product(*[grid[k] for k in keys]))
        STATE["grid_total"] = len(symbols) * len(combos)
        log(f"参数组合: {len(combos)} 种 × {len(symbols)} 个币 = {STATE['grid_total']} 次评估")

        class FC:
            ATR_PERIOD=20; MA_PERIOD=99; TREND_FILTER=False
            def __init__(self, base):
                for k in dir(base):
                    if not k.startswith("_"):
                        try: setattr(self, k, getattr(base, k))
                        except: pass

        ex = BinanceREST(cfg_module.API_KEY, cfg_module.API_SECRET, cfg_module.BASE_URL)

        # ── 2. 逐币种拉数据 + 回测 ───────────────────────────
        # 跨币种汇总：每个参数组合的 trades 列表（所有币加在一起）
        combo_trades = {i: [] for i in range(len(combos))}
        all_results_by_sym = {}

        for sym_idx, symbol in enumerate(symbols):
            log(f"[{sym_idx+1}/{len(symbols)}] 拉取 {symbol} {days}天历史K线...")

            # 拉取历史数据
            klines   = []
            end_time = None
            target_n = days * 86400
            fetch_err = False

            while len(klines) < target_n:
                try:
                    chunk = await ex.get_klines(symbol, "1s", 1000)
                    if not chunk: break
                    klines = chunk + klines
                    end_time = chunk[0]["open_time"] - 1
                    await asyncio.sleep(0.12)
                except Exception as e:
                    log(f"  {symbol} 拉取失败: {e}")
                    fetch_err = True
                    break

            if len(klines) < 100:
                log(f"  {symbol} 数据不足({len(klines)}根)，跳过")
                STATE["grid_progress"] += len(combos)
                continue

            log(f"  {symbol} 获取 {len(klines)} 根K线，开始评估...")

            # 对该币种跑所有参数组合
            sym_combo_results = []
            for idx, combo in enumerate(combos):
                fc = FC(cfg_module)
                for k, v in zip(keys, combo): setattr(fc, k, v)

                det    = SpikeDetector(fc)
                trades = []
                for i in range(fc.ATR_PERIOD + 1, len(klines)):
                    det.update(klines[max(0, i-200):i])
                    k2 = klines[i]
                    c  = Candle(open_time=k2["open_time"], open=k2["open"],
                                high=k2["high"], low=k2["low"],
                                close=k2["close"], volume=k2["volume"])
                    sig = det.detect(c)
                    if sig:
                        future = klines[i+1 : i+1+fc.MAX_HOLD_SECONDS]
                        pnl    = _sim(sig, future)
                        trades.append(pnl)
                        combo_trades[idx].append(pnl)  # 汇总

                STATE["grid_progress"] += 1
                if idx % 5 == 0: await asyncio.sleep(0)

                if len(trades) < 3:
                    continue

                m = _calc_metrics(trades)
                sym_combo_results.append({
                    "score": m.get(target, 0),
                    "p":     dict(zip(keys, combo)),
                    "m":     m,
                })

            # 该币种 Top10
            sym_combo_results.sort(key=lambda x: x["score"], reverse=True)
            all_results_by_sym[symbol] = sym_combo_results[:10]
            STATE["grid_sym_results"] = all_results_by_sym
            log(f"  {symbol} 完成，有效组合 {len(sym_combo_results)} 个")

        await ex.close()

        # ── 3. 跨币种汇总排名 ────────────────────────────────
        log("汇总跨币种排名...")
        agg_results = []
        for idx, combo in enumerate(combos):
            all_trades = combo_trades[idx]
            if len(all_trades) < 3:
                continue
            m = _calc_metrics(all_trades)
            m["symbols_covered"] = sum(
                1 for sym_res in all_results_by_sym.values()
                if any(r["p"] == dict(zip(keys, combo)) for r in sym_res)
            )
            agg_results.append({
                "score": m.get(target, 0),
                "p":     dict(zip(keys, combo)),
                "m":     m,
            })

        agg_results.sort(key=lambda x: x["score"], reverse=True)
        STATE["grid_results"] = agg_results[:10]
        STATE["grid_best"]    = agg_results[0]["p"] if agg_results else None
        log(f"完成！汇总有效组合 {len(agg_results)} 个，最优: {STATE['grid_best']}")

    except Exception as e:
        logger.error(f"Grid error: {e}", exc_info=True)
        log(f"错误: {e}")
    finally:
        STATE["grid_running"] = False


def _calc_metrics(trades: list) -> dict:
    wins     = sum(1 for p in trades if p > 0)
    n        = len(trades)
    wr       = wins / n * 100
    total    = sum(trades)
    avg_win  = sum(p for p in trades if p > 0) / max(wins, 1)
    avg_loss = abs(sum(p for p in trades if p < 0)) / max(n - wins, 1)
    expect   = (wins/n) * avg_win - ((n-wins)/n) * avg_loss
    std      = statistics.stdev(trades) if n > 1 else 1e-9
    sharpe   = (total/n) / std if std > 0 else 0
    return {
        "n":          n,
        "win_rate":   round(wr, 1),
        "total_pnl":  round(total, 5),
        "expectancy": round(expect, 6),
        "sharpe":     round(sharpe, 3),
        "avg_win":    round(avg_win, 6),
        "avg_loss":   round(avg_loss, 6),
    }


def _sim(sig, future) -> float:
    for k in future:
        hi,lo=k["high"],k["low"]
        if sig.direction=="BUY":
            if lo<=sig.stop_loss: return sig.stop_loss-sig.entry_price
            if hi>=sig.take_profit: return sig.take_profit-sig.entry_price
        else:
            if hi>=sig.stop_loss: return sig.entry_price-sig.stop_loss
            if lo<=sig.take_profit: return sig.entry_price-sig.take_profit
    ep=future[-1]["close"] if future else sig.entry_price
    return (ep-sig.entry_price) if sig.direction=="BUY" else (sig.entry_price-ep)


async def run_web():
    app = web.Application()
    app.router.add_get("/",                    handle_index)
    app.router.add_get("/stream",              handle_stream)
    app.router.add_post("/api/set_params",     handle_set_params)
    app.router.add_post("/api/reset_circuit",  handle_reset_circuit)
    app.router.add_post("/api/force_rescan",   handle_force_rescan)
    app.router.add_post("/api/grid_search",    handle_grid_search)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, cfg_module.WEB_HOST, cfg_module.WEB_PORT)
    await site.start()
    logger.info(f"Dashboard: http://0.0.0.0:{cfg_module.WEB_PORT}")
    return runner
