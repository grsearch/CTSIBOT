"""
Web Dashboard - 完整版
aiohttp + SSE 实时推送 + 风控面板 + 手动熔断控制
访问 http://YOUR_IP:8888
"""
import asyncio
import json
import logging
import time

from aiohttp import web

import config
from bot import STATE

logger = logging.getLogger(__name__)


HTML = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CTSI Spike Bot</title>
<style>
:root{--bg:#0a0c10;--s1:#111318;--s2:#181c24;--bd:#22283a;
--green:#00d48a;--red:#ff3d5a;--blue:#3d8eff;--amber:#ffb020;
--purple:#a855f7;--text:#dde3f0;--muted:#4a5568;--r:10px}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:'SF Mono','Fira Code','Consolas',monospace;font-size:12px;min-height:100vh}
header{background:var(--s1);border-bottom:1px solid var(--bd);padding:10px 20px;display:flex;align-items:center;gap:12px;position:sticky;top:0;z-index:10}
h1{font-size:14px;font-weight:700;letter-spacing:.12em;color:var(--blue)}
.dot{width:8px;height:8px;border-radius:50%;background:var(--muted);flex-shrink:0}
.dot.on{background:var(--green);box-shadow:0 0 8px var(--green);animation:blink 1.8s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}
.price{margin-left:auto;font-size:20px;font-weight:800;color:var(--amber);letter-spacing:.04em}
.time{font-size:10px;color:var(--muted)}

main{padding:16px 20px;display:flex;flex-direction:column;gap:14px}

.row{display:grid;gap:10px}
.r4{grid-template-columns:repeat(4,1fr)}
.r3{grid-template-columns:repeat(3,1fr)}
.r2{grid-template-columns:1fr 1fr}
@media(max-width:780px){.r4,.r3{grid-template-columns:repeat(2,1fr)}.r2{grid-template-columns:1fr}}

.card{background:var(--s1);border:1px solid var(--bd);border-radius:var(--r);padding:14px 16px}
.card-head{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);margin-bottom:10px;display:flex;align-items:center;gap:8px}

.stat .label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-bottom:5px}
.stat .val{font-size:24px;font-weight:800;line-height:1}
.stat .sub{font-size:10px;color:var(--muted);margin-top:4px}
.g{color:var(--green)}.r{color:var(--red)}.b{color:var(--blue)}.a{color:var(--amber)}.p{color:var(--purple)}

table{width:100%;border-collapse:collapse}
th{padding:6px 10px;text-align:left;font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid var(--bd);white-space:nowrap}
td{padding:7px 10px;border-bottom:1px solid #151922;font-size:11px;white-space:nowrap}
tr:last-child td{border:none}
tr:hover td{background:#13171f}

.tag{display:inline-block;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:700;letter-spacing:.04em}
.tag.buy{background:rgba(0,212,138,.12);color:var(--green)}
.tag.sell{background:rgba(255,61,90,.12);color:var(--red)}
.tag.tp{background:rgba(0,212,138,.12);color:var(--green)}
.tag.sl{background:rgba(255,61,90,.12);color:var(--red)}
.tag.timeout{background:rgba(61,142,255,.12);color:var(--blue)}
.tag.open{background:rgba(255,176,32,.12);color:var(--amber)}

.risk-bar{height:6px;border-radius:3px;background:var(--s2);margin-top:6px;overflow:hidden}
.risk-fill{height:100%;border-radius:3px;transition:width .5s}

.circuit{border:1px solid var(--red);border-radius:var(--r);padding:12px 16px;background:rgba(255,61,90,.06)}
.circuit.ok{border-color:var(--green);background:rgba(0,212,138,.06)}

.logbox{height:140px;overflow-y:auto;padding:10px 12px;font-size:10px;line-height:1.8;background:var(--s2);border-radius:6px}
.logbox .e{color:var(--red)}.logbox .w{color:var(--amber)}.logbox .i{color:var(--muted)}

button{background:transparent;border:1px solid var(--bd);color:var(--text);padding:6px 14px;border-radius:6px;cursor:pointer;font-size:11px;font-family:inherit;transition:all .15s}
button:hover{border-color:var(--blue);color:var(--blue)}
button.danger{border-color:var(--red);color:var(--red)}
button.danger:hover{background:rgba(255,61,90,.1)}
button.success{border-color:var(--green);color:var(--green)}
button.success:hover{background:rgba(0,212,138,.1)}

.badge{display:inline-block;padding:1px 8px;border-radius:10px;font-size:10px;font-weight:700}
.badge.on{background:rgba(0,212,138,.15);color:var(--green)}
.badge.off{background:rgba(255,61,90,.15);color:var(--red)}
</style>
</head>
<body>
<header>
  <div class="dot" id="dot"></div>
  <h1>CTSI · SPIKE BOT</h1>
  <span class="time" id="tickTime"></span>
  <div class="price" id="price">—</div>
</header>
<main>

  <!-- 收益指标 -->
  <div class="row r4">
    <div class="card stat"><div class="label">今日收益</div><div class="val" id="dayPnl">0.00</div><div class="sub">USDT</div></div>
    <div class="card stat"><div class="label">总收益</div><div class="val" id="totPnl">0.00</div><div class="sub">USDT</div></div>
    <div class="card stat"><div class="label">胜率</div><div class="val b" id="wr">0%</div><div class="sub" id="wl">0W / 0L</div></div>
    <div class="card stat"><div class="label">信号/拦截</div><div class="val a" id="sigCount">0</div><div class="sub" id="sigBlocked">拦截 0</div></div>
  </div>

  <!-- 风控状态 -->
  <div class="card">
    <div class="card-head">
      风控状态
      <span class="badge" id="tradeBadge">检查中</span>
      <button id="resetBtn" class="danger" style="margin-left:auto" onclick="resetCircuit()">解除熔断</button>
    </div>
    <div class="row r3" style="gap:12px">
      <div>
        <div style="color:var(--muted);font-size:10px;margin-bottom:4px">今日亏损</div>
        <div style="font-size:16px;font-weight:700" id="dayLoss">0.00 / <span style="color:var(--muted)">__</span> USDT</div>
        <div class="risk-bar"><div class="risk-fill" id="lossBar" style="background:var(--red);width:0%"></div></div>
      </div>
      <div>
        <div style="color:var(--muted);font-size:10px;margin-bottom:4px">回撤</div>
        <div style="font-size:16px;font-weight:700" id="ddPct">0.00%</div>
        <div class="risk-bar"><div class="risk-fill" id="ddBar" style="background:var(--amber);width:0%"></div></div>
      </div>
      <div>
        <div style="color:var(--muted);font-size:10px;margin-bottom:4px">连续亏损</div>
        <div style="font-size:16px;font-weight:700" id="consLoss">0 次</div>
        <div class="risk-bar"><div class="risk-fill" id="consBar" style="background:var(--purple);width:0%"></div></div>
      </div>
    </div>
    <div style="margin-top:10px;font-size:11px;color:var(--muted)" id="riskReason"></div>
  </div>

  <!-- 仓位 + 成交 -->
  <div class="row r2">
    <div class="card">
      <div class="card-head">当前持仓 <span id="openCnt" style="color:var(--amber)">0</span></div>
      <table>
        <thead><tr><th>#</th><th>方向</th><th>入场</th><th>TP</th><th>SL</th><th>持时</th><th>分</th></tr></thead>
        <tbody id="openTb"><tr><td colspan="7" style="text-align:center;color:var(--muted);padding:16px">无持仓</td></tr></tbody>
      </table>
    </div>
    <div class="card">
      <div class="card-head">最近成交</div>
      <table>
        <thead><tr><th>#</th><th>方向</th><th>入场</th><th>出场</th><th>原因</th><th>盈亏</th></tr></thead>
        <tbody id="tradeTb"><tr><td colspan="6" style="text-align:center;color:var(--muted);padding:16px">暂无</td></tr></tbody>
      </table>
    </div>
  </div>

  <!-- 日志 -->
  <div class="card">
    <div class="card-head">错误日志</div>
    <div class="logbox" id="logbox"><div class="i">等待运行...</div></div>
  </div>

</main>
<script>
const CFG_DAILY_LIMIT = """ + str(config.DAILY_LOSS_LIMIT_USDT) + r""";
const CFG_MAX_DD      = """ + str(config.MAX_DRAWDOWN_PCT) + r""";
const CFG_MAX_CONS    = """ + str(config.MAX_CONSECUTIVE_LOSSES) + r""";

function fmt(v, d=4){ return (v>=0?'+':'')+v.toFixed(d); }
function fmtP(v){ return (v>=0?'+':'')+v.toFixed(6); }
function clamp(v,lo,hi){ return Math.min(Math.max(v,lo),hi); }

const es = new EventSource('/stream');
es.onmessage = e => {
  const d = JSON.parse(e.data);

  document.getElementById('dot').className = 'dot'+(d.running?' on':'');
  document.getElementById('price').textContent = d.last_price ? d.last_price.toFixed(6) : '—';
  document.getElementById('tickTime').textContent =
    d.last_tick ? new Date(d.last_tick*1000).toLocaleTimeString('zh') : '';

  // 收益
  const tp = d.stats.total_pnl;
  const dp = d.risk ? d.risk.daily_pnl : 0;
  const tpEl = document.getElementById('totPnl');
  tpEl.textContent = fmt(tp,4);
  tpEl.className = 'val '+(tp>=0?'g':'r');
  const dpEl = document.getElementById('dayPnl');
  dpEl.textContent = fmt(dp,4);
  dpEl.className = 'val '+(dp>=0?'g':'r');
  document.getElementById('wr').textContent = d.stats.win_rate+'%';
  document.getElementById('wl').textContent = d.stats.win+'W / '+d.stats.loss+'L';
  document.getElementById('sigCount').textContent = d.signals_found;
  document.getElementById('sigBlocked').textContent = '拦截 '+d.signals_blocked;

  // 风控
  if(d.risk){
    const rk = d.risk;
    const badge = document.getElementById('tradeBadge');
    badge.textContent = rk.can_trade ? '✓ 正常' : '✗ 熔断';
    badge.className = 'badge '+(rk.can_trade?'on':'off');

    const lossAbs = Math.abs(Math.min(rk.daily_pnl, 0));
    document.getElementById('dayLoss').innerHTML =
      `${lossAbs.toFixed(2)} / <span style="color:var(--muted)">${CFG_DAILY_LIMIT}</span> USDT`;
    document.getElementById('lossBar').style.width =
      clamp(lossAbs/CFG_DAILY_LIMIT*100,0,100)+'%';

    document.getElementById('ddPct').textContent = rk.drawdown_pct.toFixed(2)+'%';
    document.getElementById('ddBar').style.width =
      clamp(rk.drawdown_pct/CFG_MAX_DD*100,0,100)+'%';

    document.getElementById('consLoss').textContent = rk.consecutive_losses+' 次';
    document.getElementById('consBar').style.width =
      clamp(rk.consecutive_losses/CFG_MAX_CONS*100,0,100)+'%';

    document.getElementById('riskReason').textContent =
      rk.circuit_broken ? '熔断原因: '+rk.circuit_reason : '';
    document.getElementById('resetBtn').style.display =
      rk.circuit_broken ? 'inline-block' : 'none';
  }

  // 持仓
  document.getElementById('openCnt').textContent = d.stats.open_count;
  const ob = document.getElementById('openTb');
  ob.innerHTML = d.open_positions.length === 0
    ? '<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:16px">无持仓</td></tr>'
    : d.open_positions.map(p=>`<tr>
        <td>${p.id}</td>
        <td><span class="tag ${p.direction.toLowerCase()}">${p.direction}</span></td>
        <td>${fmtP(p.entry_price)}</td>
        <td class="g">${fmtP(p.take_profit)}</td>
        <td class="r">${fmtP(p.stop_loss)}</td>
        <td>${p.age_seconds.toFixed(0)}s</td>
        <td class="a">${p.signal_score||'—'}</td>
      </tr>`).join('');

  // 成交
  const tb = document.getElementById('tradeTb');
  tb.innerHTML = d.recent_trades.length === 0
    ? '<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:16px">暂无</td></tr>'
    : [...d.recent_trades].reverse().map(t=>{
        const pc = t.pnl_usdt>=0?'var(--green)':'var(--red)';
        return `<tr>
          <td>${t.id}</td>
          <td><span class="tag ${t.direction.toLowerCase()}">${t.direction}</span></td>
          <td>${fmtP(t.entry_price)}</td>
          <td>${fmtP(t.close_price)}</td>
          <td><span class="tag ${t.close_reason.toLowerCase()}">${t.close_reason}</span></td>
          <td style="color:${pc};font-weight:700">${fmt(t.pnl_usdt,4)}</td>
        </tr>`;
      }).join('');

  // 日志
  if(d.errors && d.errors.length){
    document.getElementById('logbox').innerHTML =
      d.errors.map(e=>`<div class="e">✗ ${e}</div>`).join('');
  }
};

function resetCircuit(){
  fetch('/api/reset_circuit', {method:'POST'})
    .then(r=>r.json()).then(d=>console.log('reset:', d));
}
</script>
</body>
</html>"""


async def handle_index(request):
    return web.Response(text=HTML, content_type="text/html")


async def handle_stream(request):
    resp = web.StreamResponse()
    resp.headers["Content-Type"]  = "text/event-stream"
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["Connection"]    = "keep-alive"
    await resp.prepare(request)
    try:
        while True:
            pm   = STATE.get("positions")
            rm   = STATE.get("risk")
            stats = {"total_trades":0,"win":0,"loss":0,"win_rate":0,"total_pnl":0,"open_count":0}
            open_pos, recent_trades = [], []

            if pm:
                stats = pm.stats
                for p in pm.open_positions:
                    open_pos.append({
                        "id": p.id, "direction": p.direction,
                        "entry_price": p.entry_price, "take_profit": p.take_profit,
                        "stop_loss": p.stop_loss, "age_seconds": round(p.age_seconds,1),
                        "signal_score": p.signal_score,
                    })
                for t in pm.get_recent_trades(15):
                    recent_trades.append({
                        "id": t.id, "direction": t.direction,
                        "entry_price": t.entry_price, "close_price": t.close_price,
                        "close_reason": t.close_reason, "pnl_usdt": t.pnl_usdt,
                    })

            payload = {
                "running":         STATE.get("running", False),
                "last_price":      STATE.get("last_price", 0),
                "last_tick":       STATE.get("last_tick", 0),
                "signals_found":   STATE.get("signals_found", 0),
                "signals_blocked": STATE.get("signals_blocked", 0),
                "stats":           stats,
                "open_positions":  open_pos,
                "recent_trades":   recent_trades,
                "risk":            rm.status_dict if rm else None,
                "errors":          STATE.get("errors", [])[-12:],
            }
            await resp.write(f"data: {json.dumps(payload)}\n\n".encode())
            await asyncio.sleep(1)
    except (ConnectionResetError, asyncio.CancelledError):
        pass
    return resp


async def handle_reset_circuit(request):
    rm = STATE.get("risk")
    if rm:
        rm.manual_reset()
        return web.json_response({"ok": True, "msg": "熔断已解除"})
    return web.json_response({"ok": False, "msg": "风控模块未初始化"})


async def run_web():
    app = web.Application()
    app.router.add_get("/",                  handle_index)
    app.router.add_get("/stream",            handle_stream)
    app.router.add_post("/api/reset_circuit", handle_reset_circuit)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, config.WEB_HOST, config.WEB_PORT)
    await site.start()
    logger.info(f"Dashboard: http://0.0.0.0:{config.WEB_PORT}")
    return runner
