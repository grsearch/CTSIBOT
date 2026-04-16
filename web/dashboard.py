"""
Dashboard - 完整版 v3
Tab 布局：监控 / 参数设置 / 网格搜索 / 币种管理
"""
import asyncio, json, logging, time, itertools
import config as cfg_module
from aiohttp import web
from bot import STATE

logger = logging.getLogger(__name__)

# ─── HTML ────────────────────────────────────────────────────
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
/* header */
header{background:var(--s1);border-bottom:1px solid var(--bd);padding:9px 18px;
  display:flex;align-items:center;gap:10px;position:sticky;top:0;z-index:100}
.dot{width:8px;height:8px;border-radius:50%;background:var(--mt);flex-shrink:0}
.dot.on{background:var(--gr);box-shadow:0 0 7px var(--gr);animation:blink 1.8s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}
h1{font-size:13px;font-weight:700;letter-spacing:.1em;color:var(--bl)}
.dry-badge{background:rgba(255,176,32,.15);color:var(--am);border:1px solid rgba(255,176,32,.3);
  padding:2px 10px;border-radius:6px;font-size:10px;font-weight:700;letter-spacing:.06em}
.live-badge{background:rgba(0,212,138,.15);color:var(--gr);border:1px solid rgba(0,212,138,.3);
  padding:2px 10px;border-radius:6px;font-size:10px;font-weight:700;letter-spacing:.06em}
.price-hd{margin-left:auto;font-size:18px;font-weight:800;color:var(--am);letter-spacing:.03em}
.time-hd{font-size:10px;color:var(--mt)}
/* tabs */
.tabs{background:var(--s1);border-bottom:1px solid var(--bd);
  display:flex;gap:0;padding:0 18px}
.tab{padding:10px 18px;font-size:11px;font-weight:600;letter-spacing:.06em;
  text-transform:uppercase;color:var(--mt);cursor:pointer;border-bottom:2px solid transparent;
  transition:all .15s;user-select:none}
.tab:hover{color:var(--tx)}
.tab.active{color:var(--bl);border-bottom-color:var(--bl)}
/* panels */
.panel{display:none;padding:14px 18px;flex-direction:column;gap:12px}
.panel.active{display:flex}
/* cards */
.card{background:var(--s1);border:1px solid var(--bd);border-radius:var(--r);padding:12px 14px}
.ch{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.12em;
  color:var(--mt);margin-bottom:10px;display:flex;align-items:center;gap:8px}
/* grids */
.g4{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
.g3{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
@media(max-width:900px){.g4,.g3{grid-template-columns:repeat(2,1fr)}.g2{grid-template-columns:1fr}}
/* stat cards */
.sc .lb{font-size:9px;color:var(--mt);text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px}
.sc .vl{font-size:22px;font-weight:800;line-height:1.1}
.sc .sb{font-size:9px;color:var(--mt);margin-top:3px}
/* colors */
.gr{color:var(--gr)}.rd{color:var(--rd)}.bl{color:var(--bl)}.am{color:var(--am)}.pu{color:var(--pu)}
/* tags */
.tag{display:inline-block;padding:2px 7px;border-radius:3px;font-size:9px;font-weight:700}
.tag.buy{background:rgba(0,212,138,.12);color:var(--gr)}
.tag.sell{background:rgba(255,61,90,.12);color:var(--rd)}
.tag.tp{background:rgba(0,212,138,.12);color:var(--gr)}
.tag.sl{background:rgba(255,61,90,.12);color:var(--rd)}
.tag.timeout{background:rgba(61,142,255,.12);color:var(--bl)}
/* tables */
table{width:100%;border-collapse:collapse}
th{padding:5px 8px;text-align:left;font-size:9px;color:var(--mt);
  text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid var(--bd)}
td{padding:6px 8px;border-bottom:1px solid #13171f;font-size:11px}
tr:last-child td{border:none}
tr:hover td{background:#13171f}
/* risk bars */
.rb{height:4px;border-radius:2px;background:var(--s2);margin-top:5px;overflow:hidden}
.rf{height:100%;border-radius:2px;transition:width .5s}
/* badge */
.bdg{display:inline-block;padding:2px 8px;border-radius:8px;font-size:9px;font-weight:700}
.bdg.ok{background:rgba(0,212,138,.15);color:var(--gr)}
.bdg.ng{background:rgba(255,61,90,.15);color:var(--rd)}
/* buttons */
btn,button{background:transparent;border:1px solid var(--bd);color:var(--tx);
  padding:6px 14px;border-radius:6px;cursor:pointer;font-size:11px;
  font-family:inherit;transition:all .15s;display:inline-block}
button:hover{border-color:var(--bl);color:var(--bl)}
button.danger{border-color:var(--rd);color:var(--rd)}
button.danger:hover{background:rgba(255,61,90,.08)}
button.primary{border-color:var(--bl);color:var(--bl)}
button.primary:hover{background:rgba(61,142,255,.08)}
button.success{border-color:var(--gr);color:var(--gr)}
button.success:hover{background:rgba(0,212,138,.08)}
button:disabled{opacity:.4;cursor:not-allowed}
/* form elements */
.form-row{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px}
.field{display:flex;flex-direction:column;gap:4px}
.field label{font-size:10px;color:var(--mt);text-transform:uppercase;letter-spacing:.06em}
.field input,.field select{background:var(--s2);border:1px solid var(--bd);
  color:var(--tx);padding:6px 10px;border-radius:6px;font-size:12px;font-family:inherit;
  outline:none;transition:border-color .15s}
.field input:focus,.field select:focus{border-color:var(--bl)}
.field .hint{font-size:9px;color:var(--mt)}
/* grid search */
.prog-bar{height:6px;border-radius:3px;background:var(--s2);overflow:hidden;margin:8px 0}
.prog-fill{height:100%;border-radius:3px;background:var(--bl);transition:width .3s}
.result-row-best{background:rgba(0,212,138,.06) !important}
/* symbol pills */
.sym-pill{display:inline-flex;align-items:center;gap:6px;background:var(--s2);
  border:1px solid var(--bd);border-radius:6px;padding:4px 10px;font-size:11px;
  margin:3px}
.sym-pill .dot2{width:6px;height:6px;border-radius:50%;background:var(--mt)}
.sym-pill .dot2.on{background:var(--gr)}
/* log */
.logbox{height:130px;overflow-y:auto;padding:8px 10px;font-size:10px;
  line-height:1.8;background:var(--s2);border-radius:6px}
.logbox .e{color:var(--rd)}.logbox .i{color:var(--mt)}
/* section sep */
.sep{border:none;border-top:1px solid var(--bd);margin:4px 0}
</style>
</head>
<body>
<header>
  <div class="dot" id="hDot"></div>
  <h1>SPIKE BOT</h1>
  <span id="modeBadge" class="dry-badge">空跑</span>
  <span class="time-hd" id="hTime"></span>
  <div class="price-hd" id="hPrice">—</div>
</header>

<div class="tabs">
  <div class="tab active" onclick="showTab('monitor')">监控</div>
  <div class="tab" onclick="showTab('params')">参数设置</div>
  <div class="tab" onclick="showTab('grid')">网格搜索</div>
  <div class="tab" onclick="showTab('symbols')">币种管理</div>
</div>

<!-- ═══ TAB 1: 监控 ═══ -->
<div class="panel active" id="tab-monitor">
  <div class="g4">
    <div class="card sc"><div class="lb">今日收益</div><div class="vl" id="dayPnl">+0.0000</div><div class="sb">USDT</div></div>
    <div class="card sc"><div class="lb">总收益</div><div class="vl" id="totPnl">+0.0000</div><div class="sb">USDT</div></div>
    <div class="card sc"><div class="lb">胜率</div><div class="vl bl" id="wr">0%</div><div class="sb" id="wl">0W / 0L</div></div>
    <div class="card sc"><div class="lb">信号/拦截</div><div class="vl am" id="sigN">0</div><div class="sb" id="sigB">拦截 0</div></div>
  </div>

  <div class="card">
    <div class="ch">风控状态 <span class="bdg ok" id="riskBdg">正常</span>
      <button class="danger" id="resetBtn" style="display:none;margin-left:auto;padding:3px 10px;font-size:10px" onclick="resetCircuit()">解除熔断</button>
    </div>
    <div class="g3">
      <div>
        <div style="font-size:9px;color:var(--mt);margin-bottom:3px">今日亏损</div>
        <div style="font-size:14px;font-weight:700" id="rLoss">0.00 / — USDT</div>
        <div class="rb"><div class="rf" id="rLossBar" style="background:var(--rd);width:0%"></div></div>
      </div>
      <div>
        <div style="font-size:9px;color:var(--mt);margin-bottom:3px">回撤</div>
        <div style="font-size:14px;font-weight:700" id="rDD">0.00%</div>
        <div class="rb"><div class="rf" id="rDDBar" style="background:var(--am);width:0%"></div></div>
      </div>
      <div>
        <div style="font-size:9px;color:var(--mt);margin-bottom:3px">连续亏损</div>
        <div style="font-size:14px;font-weight:700" id="rCons">0 次</div>
        <div class="rb"><div class="rf" id="rConsBar" style="background:var(--pu);width:0%"></div></div>
      </div>
    </div>
    <div style="margin-top:8px;font-size:10px;color:var(--rd)" id="rReason"></div>
  </div>

  <div class="g2">
    <div class="card">
      <div class="ch">当前持仓 <span class="am" id="openCnt">0</span></div>
      <table><thead><tr><th>币种</th><th>方向</th><th>入场</th><th>TP</th><th>SL</th><th>持时</th><th>分</th></tr></thead>
        <tbody id="openTb"><tr><td colspan="7" style="text-align:center;color:var(--mt);padding:16px">无持仓</td></tr></tbody>
      </table>
    </div>
    <div class="card">
      <div class="ch">最近成交</div>
      <table><thead><tr><th>币种</th><th>方向</th><th>入场</th><th>出场</th><th>原因</th><th>盈亏</th></tr></thead>
        <tbody id="tradeTb"><tr><td colspan="6" style="text-align:center;color:var(--mt);padding:16px">暂无</td></tr></tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <div class="ch">错误日志</div>
    <div class="logbox" id="logbox"><div class="i">等待运行...</div></div>
  </div>
</div>

<!-- ═══ TAB 2: 参数设置 ═══ -->
<div class="panel" id="tab-params">
  <div class="card">
    <div class="ch">插针检测</div>
    <div class="form-row">
      <div class="field"><label>针/实体倍数 SPIKE_RATIO</label>
        <input type="number" id="p_SPIKE_RATIO" step="0.5" min="1">
        <span class="hint">针长 ÷ K线实体 ≥ 此值才触发</span></div>
      <div class="field"><label>针/ATR倍数 SPIKE_VS_ATR</label>
        <input type="number" id="p_SPIKE_VS_ATR" step="0.5" min="1">
        <span class="hint">针长 ÷ ATR(20) ≥ 此值</span></div>
      <div class="field"><label>最小回归比 RECOVERY_RATIO</label>
        <input type="number" id="p_RECOVERY_RATIO" step="0.05" min="0.1" max="0.95">
        <span class="hint">当根K线已回归针的xx%才入场</span></div>
      <div class="field"><label>最小针长 MIN_SPIKE_PIPS</label>
        <input type="number" id="p_MIN_SPIKE_PIPS" step="0.0001">
        <span class="hint">绝对值，过滤超小振幅</span></div>
    </div>
  </div>
  <div class="card">
    <div class="ch">止盈止损</div>
    <div class="form-row">
      <div class="field"><label>止盈比 TP_RATIO</label>
        <input type="number" id="p_TP_RATIO" step="0.05" min="0.3" max="0.99">
        <span class="hint">回归针长的xx%平仓</span></div>
      <div class="field"><label>止损比 SL_RATIO</label>
        <input type="number" id="p_SL_RATIO" step="0.05" min="0.01" max="0.5">
        <span class="hint">针尖再延伸xx%为止损</span></div>
      <div class="field"><label>最长持仓秒 MAX_HOLD_SECONDS</label>
        <input type="number" id="p_MAX_HOLD_SECONDS" step="5" min="5">
        <span class="hint">超时强制平仓</span></div>
      <div class="field"><label>单笔金额 ORDER_USDT</label>
        <input type="number" id="p_ORDER_USDT" step="5" min="5">
        <span class="hint">每笔下单 USDT 金额</span></div>
    </div>
  </div>
  <div class="card">
    <div class="ch">风险控制</div>
    <div class="form-row">
      <div class="field"><label>日亏损上限 DAILY_LOSS_LIMIT_USDT</label>
        <input type="number" id="p_DAILY_LOSS_LIMIT_USDT" step="1" min="1"></div>
      <div class="field"><label>最大回撤% MAX_DRAWDOWN_PCT</label>
        <input type="number" id="p_MAX_DRAWDOWN_PCT" step="0.5" min="1" max="50"></div>
      <div class="field"><label>连续亏损上限 MAX_CONSECUTIVE_LOSSES</label>
        <input type="number" id="p_MAX_CONSECUTIVE_LOSSES" step="1" min="2" max="20"></div>
      <div class="field"><label>同时持仓数 MAX_OPEN_ORDERS</label>
        <input type="number" id="p_MAX_OPEN_ORDERS" step="1" min="1" max="10"></div>
    </div>
  </div>
  <div style="display:flex;gap:10px;align-items:center">
    <button class="primary" onclick="applyParams()">应用参数（热更新，不需重启）</button>
    <button onclick="loadParams()">重新读取</button>
    <span id="paramMsg" style="font-size:11px;color:var(--gr)"></span>
  </div>
  <div class="card" style="background:rgba(255,176,32,.04);border-color:rgba(255,176,32,.2)">
    <div class="ch" style="color:var(--am)">当前生效参数（只读快照）</div>
    <pre id="cfgSnapshot" style="font-size:10px;color:var(--mt);line-height:1.8;white-space:pre-wrap"></pre>
  </div>
</div>

<!-- ═══ TAB 3: 网格搜索 ═══ -->
<div class="panel" id="tab-grid">
  <div class="card">
    <div class="ch">搜索空间配置</div>
    <div class="form-row">
      <div class="field"><label>SPIKE_RATIO 候选值</label>
        <input type="text" id="g_spike_ratio" value="2.5,3.0,3.5,4.0">
        <span class="hint">逗号分隔</span></div>
      <div class="field"><label>SPIKE_VS_ATR 候选值</label>
        <input type="text" id="g_spike_atr" value="2.0,2.5,3.0"></div>
      <div class="field"><label>RECOVERY_RATIO 候选值</label>
        <input type="text" id="g_recovery" value="0.40,0.50,0.60"></div>
      <div class="field"><label>TP_RATIO 候选值</label>
        <input type="text" id="g_tp" value="0.60,0.70,0.80"></div>
      <div class="field"><label>SL_RATIO 候选值</label>
        <input type="text" id="g_sl" value="0.08,0.10,0.15"></div>
      <div class="field"><label>MAX_HOLD_SECONDS 候选值</label>
        <input type="text" id="g_hold" value="20,30,45"></div>
    </div>
    <div style="margin-top:10px;display:flex;gap:10px;align-items:center;flex-wrap:wrap">
      <div class="field" style="flex-direction:row;align-items:center;gap:8px;margin:0">
        <label style="white-space:nowrap">回测天数</label>
        <input type="number" id="g_days" value="2" min="1" max="7" style="width:60px">
      </div>
      <div class="field" style="flex-direction:row;align-items:center;gap:8px;margin:0">
        <label style="white-space:nowrap">优化目标</label>
        <select id="g_target">
          <option value="expectancy">期望值 expectancy</option>
          <option value="win_rate">胜率 win_rate</option>
          <option value="total_pnl">总PnL</option>
          <option value="sharpe">Sharpe</option>
        </select>
      </div>
      <button class="primary" id="gridBtn" onclick="startGrid()">开始网格搜索</button>
      <span id="gridCombo" style="font-size:10px;color:var(--mt)"></span>
    </div>
  </div>

  <div class="card" id="gridProgressCard" style="display:none">
    <div class="ch">搜索进度 <span id="gridPct">0%</span></div>
    <div class="prog-bar"><div class="prog-fill" id="gridBar" style="width:0%"></div></div>
    <div style="font-size:10px;color:var(--mt);margin-top:4px" id="gridStatus">准备中...</div>
  </div>

  <div class="card" id="gridResultCard" style="display:none">
    <div class="ch">搜索结果 Top 10
      <button class="success" style="margin-left:auto;padding:3px 10px;font-size:10px" onclick="applyBest()">应用最优参数</button>
    </div>
    <div style="overflow-x:auto">
    <table id="gridTable">
      <thead><tr>
        <th>#</th><th>SR</th><th>ATR</th><th>REC</th><th>TP</th><th>SL</th><th>HOLD</th>
        <th>N</th><th>胜率</th><th>期望值</th><th>Sharpe</th><th>总PnL</th><th></th>
      </tr></thead>
      <tbody id="gridTb"></tbody>
    </table>
    </div>
  </div>
</div>

<!-- ═══ TAB 4: 币种管理 ═══ -->
<div class="panel" id="tab-symbols">
  <div class="card">
    <div class="ch">扫描模式</div>
    <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px">
      <label style="display:flex;align-items:center;gap:6px;cursor:pointer">
        <input type="radio" name="scanMode" value="single" id="sm_single"> <span>Single 单币种</span></label>
      <label style="display:flex;align-items:center;gap:6px;cursor:pointer">
        <input type="radio" name="scanMode" value="list" id="sm_list"> <span>List 手动列表</span></label>
      <label style="display:flex;align-items:center;gap:6px;cursor:pointer">
        <input type="radio" name="scanMode" value="auto" id="sm_auto"> <span>Auto 自动筛选</span></label>
    </div>
    <div id="sm_single_opt">
      <div class="field" style="max-width:200px">
        <label>交易对 SYMBOL</label>
        <input type="text" id="sym_single" placeholder="CTSIUSDT">
      </div>
    </div>
    <div id="sm_list_opt" style="display:none">
      <div class="field">
        <label>交易对列表（每行一个或逗号分隔）</label>
        <textarea id="sym_list" rows="4" style="background:var(--s2);border:1px solid var(--bd);color:var(--tx);padding:8px;border-radius:6px;font-family:inherit;font-size:11px;resize:vertical">CTSIUSDT
SOLUSDT
SUIUSDT
FETUSDT</textarea>
      </div>
    </div>
    <div id="sm_auto_opt" style="display:none">
      <div class="form-row">
        <div class="field"><label>最低24h成交额(USDT)</label>
          <input type="number" id="auto_min_vol" value="5000000"></div>
        <div class="field"><label>最高24h成交额(USDT)</label>
          <input type="number" id="auto_max_vol" value="200000000"></div>
        <div class="field"><label>最多币种数</label>
          <input type="number" id="auto_max_n" value="10" min="1" max="20"></div>
        <div class="field"><label>刷新间隔(秒)</label>
          <input type="number" id="auto_refresh" value="3600"></div>
      </div>
    </div>
    <div style="margin-top:12px;display:flex;gap:10px">
      <button class="primary" onclick="applySymbols()">应用</button>
      <span id="symMsg" style="font-size:11px;color:var(--gr)"></span>
    </div>
  </div>

  <div class="card">
    <div class="ch">当前活跃币种</div>
    <div id="activePills" style="min-height:32px"></div>
    <div style="margin-top:10px;font-size:10px;color:var(--mt)">
      扫描模式: <span id="scanModeLabel" class="am">—</span> &nbsp;|&nbsp;
      API权重: <span id="apiWeight">—</span>
    </div>
  </div>
</div>

<script>
// ── Tab 切换 ──────────────────────────────────────────────
function showTab(name){
  document.querySelectorAll('.tab').forEach((t,i)=>{
    const names=['monitor','params','grid','symbols'];
    t.classList.toggle('active', names[i]===name);
  });
  document.querySelectorAll('.panel').forEach(p=>{
    p.classList.toggle('active', p.id==='tab-'+name);
  });
}

// ── SSE 实时数据 ──────────────────────────────────────────
const es = new EventSource('/stream');
let _lastData = {};

es.onmessage = e=>{
  const d = JSON.parse(e.data);
  _lastData = d;
  updateMonitor(d);
  updateSymbolTab(d);
  if(d.live_config) updateParamSnapshot(d.live_config);
  if(d.grid_progress !== undefined) updateGridProgress(d);
};

function fmt(v,n=4){ return (v>=0?'+':'')+v.toFixed(n); }
function fmtP(v){ return v.toFixed(6); }
function clamp(v,lo,hi){ return Math.min(Math.max(v,lo),hi); }

function updateMonitor(d){
  const DL = d.live_config ? d.live_config.DAILY_LOSS_LIMIT_USDT||10 : 10;
  const MD = d.live_config ? d.live_config.MAX_DRAWDOWN_PCT||5 : 5;
  const MC = d.live_config ? d.live_config.MAX_CONSECUTIVE_LOSSES||5 : 5;

  document.getElementById('hDot').className='dot'+(d.running?' on':'');
  // 显示所有活跃价格（最后一个）
  const prices = d.prices||{};
  const pvs = Object.values(prices);
  document.getElementById('hPrice').textContent = pvs.length ? pvs[pvs.length-1].toFixed(6) : '—';
  document.getElementById('hTime').textContent = d.last_tick ? new Date(d.last_tick*1000).toLocaleTimeString('zh') : '';

  const dry = d.dry_run;
  const mb = document.getElementById('modeBadge');
  mb.textContent = dry ? '空跑 DRY-RUN' : '实盘 LIVE';
  mb.className   = dry ? 'dry-badge' : 'live-badge';

  // 收益
  const tp = d.stats.total_pnl||0;
  const dp = d.risk ? d.risk.daily_pnl||0 : 0;
  const tpEl=document.getElementById('totPnl'); tpEl.textContent=fmt(tp); tpEl.className='vl '+(tp>=0?'gr':'rd');
  const dpEl=document.getElementById('dayPnl'); dpEl.textContent=fmt(dp); dpEl.className='vl '+(dp>=0?'gr':'rd');
  document.getElementById('wr').textContent=d.stats.win_rate+'%';
  document.getElementById('wl').textContent=d.stats.win+'W / '+d.stats.loss+'L';
  document.getElementById('sigN').textContent=d.signals_found||0;
  document.getElementById('sigB').textContent='拦截 '+(d.signals_blocked||0);

  // 风控
  if(d.risk){
    const rk=d.risk;
    const bdg=document.getElementById('riskBdg');
    bdg.textContent=rk.can_trade?'✓ 正常':'✗ 熔断';
    bdg.className='bdg '+(rk.can_trade?'ok':'ng');
    const la=Math.abs(Math.min(rk.daily_pnl,0));
    document.getElementById('rLoss').textContent=la.toFixed(2)+' / '+DL+' USDT';
    document.getElementById('rLossBar').style.width=clamp(la/DL*100,0,100)+'%';
    document.getElementById('rDD').textContent=rk.drawdown_pct.toFixed(2)+'%';
    document.getElementById('rDDBar').style.width=clamp(rk.drawdown_pct/MD*100,0,100)+'%';
    document.getElementById('rCons').textContent=rk.consecutive_losses+' 次';
    document.getElementById('rConsBar').style.width=clamp(rk.consecutive_losses/MC*100,0,100)+'%';
    document.getElementById('rReason').textContent=rk.circuit_broken?'熔断: '+rk.circuit_reason:'';
    document.getElementById('resetBtn').style.display=rk.circuit_broken?'inline-block':'none';
  }

  // 持仓
  document.getElementById('openCnt').textContent=d.stats.open_count||0;
  const ob=document.getElementById('openTb');
  ob.innerHTML=!d.open_positions||d.open_positions.length===0
    ?'<tr><td colspan="7" style="text-align:center;color:var(--mt);padding:16px">无持仓</td></tr>'
    :d.open_positions.map(p=>`<tr>
      <td class="am">${p.symbol||'—'}</td>
      <td><span class="tag ${p.direction.toLowerCase()}">${p.direction}</span></td>
      <td>${fmtP(p.entry_price)}</td>
      <td class="gr">${fmtP(p.take_profit)}</td>
      <td class="rd">${fmtP(p.stop_loss)}</td>
      <td>${p.age_seconds.toFixed(0)}s</td>
      <td class="am">${p.signal_score||'—'}</td>
    </tr>`).join('');

  // 成交
  const tb=document.getElementById('tradeTb');
  tb.innerHTML=!d.recent_trades||d.recent_trades.length===0
    ?'<tr><td colspan="6" style="text-align:center;color:var(--mt);padding:16px">暂无</td></tr>'
    :[...d.recent_trades].reverse().map(t=>{
      const pc=t.pnl_usdt>=0?'var(--gr)':'var(--rd)';
      return `<tr>
        <td class="am">${t.symbol||'—'}</td>
        <td><span class="tag ${t.direction.toLowerCase()}">${t.direction}</span></td>
        <td>${fmtP(t.entry_price)}</td>
        <td>${fmtP(t.close_price)}</td>
        <td><span class="tag ${t.close_reason.toLowerCase()}">${t.close_reason}</span></td>
        <td style="color:${pc};font-weight:700">${fmt(t.pnl_usdt)}</td>
      </tr>`;
    }).join('');

  // 日志
  if(d.errors&&d.errors.length){
    document.getElementById('logbox').innerHTML=
      d.errors.map(e=>`<div class="e">✗ ${e}</div>`).join('');
  }
}

// ── 参数面板 ──────────────────────────────────────────────
function updateParamSnapshot(cfg){
  document.getElementById('cfgSnapshot').textContent =
    JSON.stringify(cfg, null, 2);
  // 填充表单（只填一次或当前没焦点时）
  const fields=['SPIKE_RATIO','SPIKE_VS_ATR','RECOVERY_RATIO','MIN_SPIKE_PIPS',
    'TP_RATIO','SL_RATIO','MAX_HOLD_SECONDS','ORDER_USDT',
    'DAILY_LOSS_LIMIT_USDT','MAX_DRAWDOWN_PCT','MAX_CONSECUTIVE_LOSSES','MAX_OPEN_ORDERS'];
  fields.forEach(k=>{
    const el=document.getElementById('p_'+k);
    if(el && document.activeElement!==el) el.value=cfg[k]??'';
  });
}
function loadParams(){
  const d=_lastData;
  if(d.live_config) updateParamSnapshot(d.live_config);
}
function applyParams(){
  const keys=['SPIKE_RATIO','SPIKE_VS_ATR','RECOVERY_RATIO','MIN_SPIKE_PIPS',
    'TP_RATIO','SL_RATIO','MAX_HOLD_SECONDS','ORDER_USDT',
    'DAILY_LOSS_LIMIT_USDT','MAX_DRAWDOWN_PCT','MAX_CONSECUTIVE_LOSSES','MAX_OPEN_ORDERS'];
  const updates={};
  keys.forEach(k=>{
    const el=document.getElementById('p_'+k);
    if(el&&el.value!=='') updates[k]=parseFloat(el.value);
  });
  fetch('/api/set_params',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(updates)})
    .then(r=>r.json()).then(d=>{
      const msg=document.getElementById('paramMsg');
      msg.textContent = d.ok ? '✓ 已应用: '+d.changed.join(', ') : '✗ '+d.error;
      msg.style.color = d.ok ? 'var(--gr)' : 'var(--rd)';
      setTimeout(()=>msg.textContent='',4000);
    });
}

// ── 网格搜索 ──────────────────────────────────────────────
function calcCombos(){
  const fields=['g_spike_ratio','g_spike_atr','g_recovery','g_tp','g_sl','g_hold'];
  let n=1;
  fields.forEach(id=>{
    const v=document.getElementById(id).value;
    n *= v.split(',').filter(x=>x.trim()).length||1;
  });
  document.getElementById('gridCombo').textContent=`共 ${n} 种组合`;
}
document.querySelectorAll('#tab-grid input[type=text]').forEach(el=>el.addEventListener('input',calcCombos));
calcCombos();

function startGrid(){
  const params={
    spike_ratio: document.getElementById('g_spike_ratio').value.split(',').map(Number).filter(Boolean),
    spike_atr:   document.getElementById('g_spike_atr').value.split(',').map(Number).filter(Boolean),
    recovery:    document.getElementById('g_recovery').value.split(',').map(Number).filter(Boolean),
    tp:          document.getElementById('g_tp').value.split(',').map(Number).filter(Boolean),
    sl:          document.getElementById('g_sl').value.split(',').map(Number).filter(Boolean),
    hold:        document.getElementById('g_hold').value.split(',').map(Number).filter(Boolean),
    days:        parseInt(document.getElementById('g_days').value)||2,
    target:      document.getElementById('g_target').value,
  };
  document.getElementById('gridProgressCard').style.display='block';
  document.getElementById('gridBtn').disabled=true;
  document.getElementById('gridStatus').textContent='正在拉取历史数据...';
  fetch('/api/grid_search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(params)})
    .then(r=>r.json()).then(d=>{
      if(!d.ok) alert('启动失败: '+d.error);
    });
}
function updateGridProgress(d){
  if(!d.grid_running && d.grid_progress===0) return;
  document.getElementById('gridProgressCard').style.display='block';
  const pct=d.grid_total>0?Math.round(d.grid_progress/d.grid_total*100):0;
  document.getElementById('gridPct').textContent=pct+'%';
  document.getElementById('gridBar').style.width=pct+'%';
  document.getElementById('gridStatus').textContent=
    d.grid_running ? `${d.grid_progress} / ${d.grid_total} 组合` : '搜索完成';
  if(!d.grid_running){
    document.getElementById('gridBtn').disabled=false;
  }
  if(d.grid_results&&d.grid_results.length){
    document.getElementById('gridResultCard').style.display='block';
    const rows=d.grid_results.slice(0,10);
    document.getElementById('gridTb').innerHTML=rows.map((r,i)=>`
      <tr class="${i===0?'result-row-best':''}">
        <td class="${i===0?'gr am':''}">${i+1}</td>
        <td>${r.p.SPIKE_RATIO}</td><td>${r.p.SPIKE_VS_ATR}</td>
        <td>${r.p.RECOVERY_RATIO}</td><td>${r.p.TP_RATIO}</td>
        <td>${r.p.SL_RATIO}</td><td>${r.p.MAX_HOLD_SECONDS}</td>
        <td>${r.m.n}</td>
        <td class="${r.m.win_rate>=55?'gr':'rd'}">${r.m.win_rate}%</td>
        <td class="${r.m.expectancy>0?'gr':'rd'}">${r.m.expectancy.toFixed(5)}</td>
        <td>${r.m.sharpe.toFixed(3)}</td>
        <td class="${r.m.total_pnl>0?'gr':'rd'}">${r.m.total_pnl.toFixed(4)}</td>
        <td><button style="padding:2px 8px;font-size:9px" onclick="applyRow(${i})">应用</button></td>
      </tr>`).join('');
  }
}
function applyBest(){
  const d=_lastData;
  if(d.grid_best) applyGridParams(d.grid_best);
}
function applyRow(i){
  const d=_lastData;
  if(d.grid_results&&d.grid_results[i]) applyGridParams(d.grid_results[i].p);
}
function applyGridParams(p){
  if(!confirm('应用这组参数到当前运行配置？')) return;
  fetch('/api/set_params',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)})
    .then(r=>r.json()).then(d=>{
      alert(d.ok ? '✓ 参数已应用: '+d.changed.join(', ') : '✗ '+d.error);
    });
}

// ── 币种管理 ──────────────────────────────────────────────
document.querySelectorAll('input[name=scanMode]').forEach(r=>{
  r.addEventListener('change',()=>{
    ['single','list','auto'].forEach(m=>{
      document.getElementById('sm_'+m+'_opt').style.display=
        r.value===m?'block':'none';
    });
  });
});
function updateSymbolTab(d){
  document.getElementById('scanModeLabel').textContent=d.scan_mode||'—';
  const syms=d.symbols_active||[];
  const prices=d.prices||{};
  document.getElementById('activePills').innerHTML=
    syms.length===0
    ? '<span style="color:var(--mt);font-size:11px">无活跃币种</span>'
    : syms.map(s=>`
      <span class="sym-pill">
        <span class="dot2 on"></span>
        <span class="am">${s}</span>
        <span style="color:var(--mt)">${prices[s]?prices[s].toFixed(6):''}</span>
      </span>`).join('');

  // 同步模式单选
  const mode=d.scan_mode||'single';
  const rb=document.querySelector(`input[name=scanMode][value=${mode}]`);
  if(rb&&!rb.checked){ rb.checked=true; rb.dispatchEvent(new Event('change')); }

  if(d.live_config){
    const sym=document.getElementById('sym_single');
    if(sym&&document.activeElement!==sym) sym.value=d.live_config.SYMBOL||'';
  }
}
function applySymbols(){
  const mode=document.querySelector('input[name=scanMode]:checked')?.value||'single';
  const updates={SCAN_MODE: mode};
  if(mode==='single'){
    updates.SYMBOL=document.getElementById('sym_single').value.trim().toUpperCase();
  } else if(mode==='list'){
    const raw=document.getElementById('sym_list').value;
    updates.SYMBOL_LIST=raw.split(/[\n,]+/).map(s=>s.trim().toUpperCase()).filter(Boolean);
  } else {
    updates.AUTO_MIN_VOLUME_USDT=parseFloat(document.getElementById('auto_min_vol').value)||5000000;
    updates.AUTO_MAX_VOLUME_USDT=parseFloat(document.getElementById('auto_max_vol').value)||200000000;
    updates.AUTO_MAX_SYMBOLS=parseInt(document.getElementById('auto_max_n').value)||10;
    updates.AUTO_REFRESH_INTERVAL=parseInt(document.getElementById('auto_refresh').value)||3600;
  }
  fetch('/api/set_params',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(updates)})
    .then(r=>r.json()).then(d=>{
      const msg=document.getElementById('symMsg');
      msg.textContent=d.ok?'✓ 已应用':'✗ '+d.error;
      msg.style.color=d.ok?'var(--gr)':'var(--rd)';
      setTimeout(()=>msg.textContent='',3000);
    });
}

// 控制
function resetCircuit(){
  fetch('/api/reset_circuit',{method:'POST'}).then(r=>r.json()).then(d=>console.log(d));
}
</script>
</body></html>"""


# ─── API handlers ─────────────────────────────────────────────
async def handle_index(req): return web.Response(text=HTML, content_type="text/html")


async def handle_stream(req):
    resp = web.StreamResponse()
    resp.headers.update({"Content-Type":"text/event-stream","Cache-Control":"no-cache","Connection":"keep-alive"})
    await resp.prepare(req)
    try:
        while True:
            pm = STATE.get("positions")
            rm = STATE.get("risk")
            stats = {"total_trades":0,"win":0,"loss":0,"win_rate":0,"total_pnl":0,"open_count":0}
            open_pos, recent_trades = [], []
            if pm:
                stats = pm.stats
                for p in pm.open_positions:
                    open_pos.append({"id":p.id,"symbol":p.symbol,"direction":p.direction,
                        "entry_price":p.entry_price,"take_profit":p.take_profit,
                        "stop_loss":p.stop_loss,"age_seconds":round(p.age_seconds,1),"signal_score":p.signal_score})
                for t in pm.get_recent_trades(15):
                    recent_trades.append({"id":t.id,"symbol":t.symbol,"direction":t.direction,
                        "entry_price":t.entry_price,"close_price":t.close_price,
                        "close_reason":t.close_reason,"pnl_usdt":t.pnl_usdt})
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
            }
            await resp.write(f"data: {json.dumps(payload)}\n\n".encode())
            await asyncio.sleep(1)
    except (ConnectionResetError, asyncio.CancelledError):
        pass
    return resp


async def handle_set_params(req):
    try:
        updates = await req.json()
        from bot import _bot_instance
        if _bot_instance:
            changed = _bot_instance.apply_live_config(updates)
            return web.json_response({"ok": True, "changed": changed})
        # 如果 bot 未启动，直接改 config module
        import config as cm
        for k, v in updates.items():
            if hasattr(cm, k):
                setattr(cm, k, v)
        return web.json_response({"ok": True, "changed": list(updates.keys())})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})


async def handle_reset_circuit(req):
    rm = STATE.get("risk")
    if rm:
        rm.manual_reset()
        return web.json_response({"ok": True})
    return web.json_response({"ok": False, "error": "risk manager not init"})


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
    """后台异步执行网格搜索"""
    import config as cfg_module
    from core.exchange import BinanceREST
    from strategy.detector import SpikeDetector, Candle
    import statistics

    STATE["grid_running"]  = True
    STATE["grid_progress"] = 0
    STATE["grid_results"]  = []
    STATE["grid_best"]     = None

    try:
        # 1. 拉取历史数据
        ex = BinanceREST(cfg_module.API_KEY, cfg_module.API_SECRET, cfg_module.BASE_URL)
        days    = params.get("days", 2)
        symbol  = cfg_module.SYMBOL
        klines  = []
        end_time = None
        target_n = days * 86400
        batch    = 1000

        while len(klines) < target_n:
            p = {"symbol": symbol, "interval": "1s", "limit": batch}
            if end_time:
                p["endTime"] = end_time
            try:
                chunk = await ex.get_klines(symbol, "1s", batch)
                if not chunk:
                    break
                klines = chunk + klines
                end_time = chunk[0]["open_time"] - 1
                await asyncio.sleep(0.15)
            except Exception as e:
                logger.error(f"Grid: kline fetch error: {e}")
                break

        await ex.close()
        if len(klines) < 200:
            STATE["grid_running"] = False
            return

        # 2. 生成参数组合
        grid = {
            "SPIKE_RATIO":      params.get("spike_ratio", [3.0]),
            "SPIKE_VS_ATR":     params.get("spike_atr",   [2.5]),
            "RECOVERY_RATIO":   params.get("recovery",    [0.5]),
            "TP_RATIO":         params.get("tp",          [0.7]),
            "SL_RATIO":         params.get("sl",          [0.1]),
            "MAX_HOLD_SECONDS": params.get("hold",        [30]),
        }
        keys   = list(grid.keys())
        combos = list(itertools.product(*[grid[k] for k in keys]))
        STATE["grid_total"] = len(combos)
        target = params.get("target", "expectancy")

        class FakeCfg:
            ATR_PERIOD=20; MA_PERIOD=99; TREND_FILTER=False; MIN_SPIKE_PIPS=0.0001
            def __init__(self, base):
                for k in dir(base):
                    if not k.startswith("_"):
                        try: setattr(self,k,getattr(base,k))
                        except: pass

        results = []
        for idx, combo in enumerate(combos):
            fc = FakeCfg(cfg_module)
            for k, v in zip(keys, combo):
                setattr(fc, k, v)

            det = SpikeDetector(fc)
            trades = []
            for i in range(fc.ATR_PERIOD + 1, len(klines)):
                det.update(klines[max(0, i-200):i])
                k2 = klines[i]
                candle = Candle(open_time=k2["open_time"],open=k2["open"],
                                high=k2["high"],low=k2["low"],
                                close=k2["close"],volume=k2["volume"])
                sig = det.detect(candle)
                if sig:
                    future = klines[i+1:i+1+fc.MAX_HOLD_SECONDS]
                    pnl = _sim_trade(sig, future, fc)
                    trades.append(pnl)

            if len(trades) < 8:
                STATE["grid_progress"] = idx + 1
                if idx % 10 == 0:
                    await asyncio.sleep(0)
                continue

            wins      = sum(1 for p in trades if p > 0)
            win_rate  = wins / len(trades) * 100
            total_pnl = sum(trades)
            avg_win   = sum(p for p in trades if p > 0) / max(wins, 1)
            avg_loss  = abs(sum(p for p in trades if p < 0)) / max(len(trades)-wins, 1)
            expectancy= (wins/len(trades))*avg_win - ((len(trades)-wins)/len(trades))*avg_loss
            std       = statistics.stdev(trades) if len(trades) > 1 else 1e-9
            sharpe    = (sum(trades)/len(trades)) / std if std > 0 else 0
            m = {"n":len(trades),"win_rate":round(win_rate,1),
                 "total_pnl":round(total_pnl,5),"expectancy":round(expectancy,6),
                 "sharpe":round(sharpe,3),"avg_win":round(avg_win,6),"avg_loss":round(avg_loss,6)}
            p_dict = dict(zip(keys, combo))
            score  = m.get(target, 0)
            results.append({"score": score, "p": p_dict, "m": m})

            STATE["grid_progress"] = idx + 1
            if idx % 5 == 0:
                results.sort(key=lambda x: x["score"], reverse=True)
                STATE["grid_results"] = results[:10]
                STATE["grid_best"]    = results[0]["p"] if results else None
                await asyncio.sleep(0)

        results.sort(key=lambda x: x["score"], reverse=True)
        STATE["grid_results"] = results[:10]
        STATE["grid_best"]    = results[0]["p"] if results else None
        logger.info(f"网格搜索完成，共{len(results)}有效组合，最优: {STATE['grid_best']}")

    except Exception as e:
        logger.error(f"Grid search error: {e}", exc_info=True)
    finally:
        STATE["grid_running"] = False


def _sim_trade(sig, future, cfg) -> float:
    for k in future:
        hi, lo = k["high"], k["low"]
        if sig.direction == "BUY":
            if lo <= sig.stop_loss:  return sig.stop_loss - sig.entry_price
            if hi >= sig.take_profit: return sig.take_profit - sig.entry_price
        else:
            if hi >= sig.stop_loss:  return sig.entry_price - sig.stop_loss
            if lo <= sig.take_profit: return sig.entry_price - sig.take_profit
    ep  = future[-1]["close"] if future else sig.entry_price
    return (ep - sig.entry_price) if sig.direction == "BUY" else (sig.entry_price - ep)


async def run_web():
    app = web.Application()
    app.router.add_get("/",                   handle_index)
    app.router.add_get("/stream",             handle_stream)
    app.router.add_post("/api/set_params",    handle_set_params)
    app.router.add_post("/api/reset_circuit", handle_reset_circuit)
    app.router.add_post("/api/grid_search",   handle_grid_search)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, cfg_module.WEB_HOST, cfg_module.WEB_PORT)
    await site.start()
    logger.info(f"Dashboard: http://0.0.0.0:{cfg_module.WEB_PORT}")
    return runner
