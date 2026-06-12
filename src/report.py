# -*- coding: utf-8 -*-
"""
產生互動式 HTML 報告(output/report.html)。
把選股結果(含進場/停損/口數/加碼/形態)輸出成可搜尋、篩選、排序的網頁,
每檔附 K 線圖。圖以相對路徑(charts/代號_名稱.png)引用,報告放在 output/ 下即可開啟。
"""
import os
import json
import datetime as dt

import config


def _plan_dict(plan):
    """把一套進場計畫(es+sizing+pyramid)轉成前端用的扁平 dict;None 回 None。"""
    if not plan:
        return None
    es, sz, ad = plan.get("es"), plan.get("sizing"), plan.get("pyramid")
    if not es:
        return None
    return {
        "entry": es["entry"], "stop": es["stop"], "source": es["source"],
        "stage": es.get("stage"), "dist_pct": es.get("dist_pct"),
        "method": es.get("method", "突破買"),
        "lots": sz["lots"] if sz else None,
        "stop_per_lot": sz["stop_per_lot"] if sz else None,
        "position_cost": sz["position_cost"] if sz else None,
        "actual_loss": sz["actual_loss"] if sz else None,
        "risk_pct": sz["actual_risk_pct"] if sz else None,
        "size_note": sz["note"] if sz else "",
        "add_entry": ad["add_entry"] if (ad and ad.get("valid")) else None,
        "add_stop": ad["add_stop"] if (ad and ad.get("valid")) else None,
        "add_lots": ad["add_lots"] if (ad and ad.get("valid")) else None,
        "add_risk_pct": ad["actual_risk_pct"] if (ad and ad.get("valid")) else None,
        "risk_free": bool(ad["risk_free"]) if (ad and ad.get("valid")) else False,
        "actionable": bool(sz and sz["lots"] and sz["lots"] >= 1),
    }


def _result_to_dict(r):
    es, sz, ad = r.get("entry_stop"), r.get("sizing"), r.get("pyramid")
    code, name = r["code"], r["name"]
    chart_rel = f"charts/{code}_{name}.png"
    chart_plain = f"charts/{code}_{name}_plain.png"
    has_chart = os.path.exists(os.path.join(config.OUTPUT_DIR, chart_rel))
    pats = [{"name": p["name"], "confidence": round(p.get("confidence", 0), 2),
             "breakout": bool(p.get("breakout")), "target": p.get("target"),
             "note": p.get("note", "")} for p in r["patterns"]]
    d = {
        "code": code, "name": name, "market": r["market"],
        "close": r["close"], "lot_cost": r["lot_cost"], "score": r["score"],
        "tier": r.get("tier"), "timing": r.get("timing"),
        "stage": r.get("stage"), "dist_pct": r.get("dist_pct"),
        "setup_type": r.get("setup_type"), "rr": r.get("rr"),
        "target": r.get("target"), "near_high_pct": r.get("near_high_pct"),
        "patterns": pats,
        "pattern_names": [p["name"] for p in pats],
        "trend": r["trend"].get("signals", []),
        "has_chart": has_chart, "chart": chart_rel, "chart_plain": chart_plain,
        "entry": es["entry"] if es else None,
        "stop": es["stop"] if es else None,
        "source": es["source"] if es else None,
        "lots": sz["lots"] if sz else None,
        "stop_per_lot": sz["stop_per_lot"] if sz else None,
        "position_cost": sz["position_cost"] if sz else None,
        "actual_loss": sz["actual_loss"] if sz else None,
        "risk_pct": sz["actual_risk_pct"] if sz else None,
        "size_note": sz["note"] if sz else "",
        "add_entry": ad["add_entry"] if (ad and ad.get("valid")) else None,
        "add_stop": ad["add_stop"] if (ad and ad.get("valid")) else None,
        "add_lots": ad["add_lots"] if (ad and ad.get("valid")) else None,
        "add_risk_pct": ad["actual_risk_pct"] if (ad and ad.get("valid")) else None,
        "risk_free": bool(ad["risk_free"]) if (ad and ad.get("valid")) else False,
    }
    d["actionable"] = bool(sz and sz["lots"] and sz["lots"] >= 1)
    d["breakout"] = any(p["breakout"] for p in pats if "跳空" not in p["name"])
    # 兩種進場方式各一套計畫,供前端切換
    d["entry_method"] = r.get("entry_method")
    d["plans"] = {"突破買": _plan_dict(r.get("plan_breakout")),
                  "回測碰線買": _plan_dict(r.get("plan_pullback"))}
    return d


def write_report(results, path=None):
    path = path or os.path.join(config.OUTPUT_DIR, "report.html")
    data = [_result_to_dict(r) for r in results]
    actionable = sum(1 for d in data if d["actionable"])
    # 收集所有形態名稱供下拉選單
    all_pats = []
    for d in data:
        for n in d["pattern_names"]:
            if n not in all_pats:
                all_pats.append(n)
    setup_types = []
    for d in data:
        st = d.get("setup_type")
        if st and st not in setup_types:
            setup_types.append(st)
    meta = {
        "date": dt.date.today().isoformat(),
        "total": len(data), "actionable": actionable,
        "setup_types": setup_types,
        "capital": config.TOTAL_CAPITAL, "risk_pct": config.RISK_PCT * 100,
        "min_price": config.MIN_PRICE, "max_price": config.MAX_PRICE,
        "min_budget": int(config.MIN_PRICE * config.SHARES_PER_LOT),
        "max_budget": int(config.MAX_PRICE * config.SHARES_PER_LOT),
        "min_vol": config.MIN_AVG_VOLUME,
        "patterns": all_pats,
        "entrable_pullback": config.ENTRABLE_PULLBACK_MAX * 100,
        "entrable_breakout": config.ENTRABLE_BREAKOUT_MAX * 100,
        "near_entry_band": config.NEAR_ENTRY_BAND * 100,
    }
    html = (_TEMPLATE
            .replace("/*__DATA__*/", json.dumps(data, ensure_ascii=False))
            .replace("/*__META__*/", json.dumps(meta, ensure_ascii=False)))
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  → 網頁報告已存:{path}")
    return path


_TEMPLATE = r"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>台股做多選股報告</title>
<style>
:root{
  --bg:#0f1420; --panel:#171d2b; --panel2:#1e2536; --line:#2a3142;
  --txt:#e6e9f0; --mut:#9aa4b8; --blue:#3b82f6; --red:#ef4444;
  --green:#22c55e; --gold:#d4be8f; --chip:#252c3e;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);
  font-family:"PingFang TC","Heiti TC","Microsoft JhengHei",system-ui,sans-serif;}
header{padding:20px 24px;background:linear-gradient(180deg,#141a28,#0f1420);
  border-bottom:1px solid var(--line);position:sticky;top:0;z-index:50}
h1{margin:0 0 4px;font-size:24px;letter-spacing:1px}
.sub{color:var(--mut);font-size:16px}
.stats{display:flex;gap:18px;margin-top:10px;flex-wrap:wrap}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:10px;
  padding:8px 14px;font-size:16px}
.stat b{color:var(--gold);font-size:22px;margin-right:4px}
.controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:14px}
.controls input[type=text],.controls select{background:var(--panel2);color:var(--txt);
  border:1px solid var(--line);border-radius:8px;padding:7px 10px;font-size:16px}
.controls input[type=text]{min-width:180px}
.toggle{display:flex;align-items:center;gap:6px;font-size:16px;color:var(--mut);
  background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:6px 10px;cursor:pointer}
.toggle input{accent-color:var(--blue)}
#count{color:var(--mut);font-size:16px}
.filterbar{display:flex;align-items:center;gap:12px;margin-top:12px}
.fbtn{font-size:15px;font-weight:700;color:var(--txt);background:var(--panel2);
  border:1px solid var(--line);border-radius:8px;padding:7px 14px;cursor:pointer}
.fbtn:hover{background:#2a3450}
.filterbar #count{margin-left:auto;color:var(--mut);font-size:16px}
.sumbox{margin-top:10px;background:var(--panel);border:1px solid var(--line);
  border-radius:12px;padding:14px 18px}
.sumbox b{color:var(--gold);font-size:16px}
.sumchips{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}
.sumchip{font-size:14px;background:var(--panel2);border:1px solid var(--line);
  border-radius:20px;padding:4px 12px;color:#cdd5e6}
.sumlist{font-size:14px;color:var(--mut);line-height:1.8;border-top:1px solid var(--line);padding-top:10px}
.param{font-size:15px;color:var(--txt);background:var(--panel);border:1px solid var(--line);
  border-radius:8px;padding:6px 12px;font-weight:700}
.param input{background:var(--panel2);color:var(--gold);border:1px solid var(--line);
  border-radius:6px;padding:4px 6px;font-size:15px;font-weight:700;width:96px;margin:0 2px}
.param input#pmin,.param input#pmax{width:56px}
.expbtn{font-size:15px;font-weight:700;color:#0f1420;background:var(--gold);border:none;
  border-radius:8px;padding:8px 16px;cursor:pointer;margin-left:auto}
.expbtn:hover{filter:brightness(1.08)}
.expbtn:active{transform:scale(0.97)}
main{padding:18px 24px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(580px,1fr));gap:20px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;overflow:hidden;
  display:flex;flex-direction:column}
.card .imgwrap{background:#fff;display:flex;align-items:center;justify-content:center;min-height:120px}
.card img{width:100%;display:block;cursor:zoom-in}
.noimg{color:#888;font-size:16px;padding:40px}
.body{padding:12px 14px}
.title{display:flex;align-items:center;gap:8px;margin-bottom:8px}
.title .nm{font-size:19px;font-weight:700}
.title .mk{font-size:16px;color:var(--mut);border:1px solid var(--line);border-radius:6px;padding:1px 6px}
.badge{margin-left:auto;font-weight:700;color:#0f1420;background:var(--gold);
  border-radius:8px;padding:3px 9px;font-size:16px}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}
.chip{font-size:14px;background:var(--chip);border:1px solid var(--line);border-radius:20px;padding:3px 9px;color:#cdd5e6}
.chip.bk{border-color:var(--green);color:#bff0cf}
.stage{font-size:14px;font-weight:700;border-radius:20px;padding:3px 11px}
.stage.soon{background:#3a2a0a;color:#ffce6b;border:1px solid #6b4e12}
.stage.just{background:#0e2a1a;color:#7ee2a0;border:1px solid #1f5a3a}
.late{font-size:14px;font-weight:700;border-radius:20px;padding:3px 11px;background:#3a1212;color:#ff9b9b;border:1px solid #6a2020}
.tm{font-size:14px;font-weight:700;border-radius:20px;padding:3px 11px;background:#102a22;color:#7ff0c8;border:1px solid #1f6a4e}
.mtag{font-size:14px;font-weight:700;border-radius:20px;padding:3px 11px}
.mtag.mpb{background:#0c2436;color:#8fd3ff;border:1px solid #1f4a6a}
.mtag.mbk{background:#241a30;color:#cbb0ff;border:1px solid #4a3a6a}
.tier{font-size:14px;font-weight:700;border-radius:20px;padding:3px 11px}
.tier.main{background:#0e2a1a;color:#9bf0bf;border:1px solid #1f5a3a}
.tier.sub{background:#2a1d0a;color:#ffce6b;border:1px solid #6b4e12}
.tier.none{background:#22283a;color:#9aa4b8;border:1px solid var(--line)}
.stype{font-size:14px;font-weight:700;border-radius:20px;padding:3px 11px}
.stype.mom{background:#2a1030;color:#e6a8ff;border:1px solid #5a2470}
.stype.rev{background:#10202a;color:#8fd3ff;border:1px solid #1f4a5a}
.rr{font-size:14px;font-weight:700;border-radius:20px;padding:3px 11px;background:#22283a;color:#c9d3ea;border:1px solid var(--line)}
.rr.good{background:#0e2a1a;color:#9bf0bf;border:1px solid #1f5a3a}
.kv2{display:flex;gap:14px;flex-wrap:wrap;font-size:15px;color:var(--mut);margin-top:8px}
.kv2 b{color:var(--txt)}
.exit{margin-top:8px;font-size:14px;color:#a8d8ff;background:#0c1c2a;border:1px solid #1f3a4a;border-radius:8px;padding:6px 9px}
.exit i{font-style:normal;font-weight:700;color:#7fb2ff}
.kv{display:grid;grid-template-columns:1fr 1fr;gap:6px 14px;font-size:16px}
.kv .k{color:var(--mut)}
.kv .v{font-weight:600;text-align:right}
.v.blue{color:#7fb2ff}.v.red{color:#ff8a8a}.v.green{color:#7ee2a0}
.warn{margin-top:8px;font-size:14px;color:#ffd27a;background:#2a2410;border:1px solid #4a3d12;
  border-radius:8px;padding:6px 9px}
.free{color:#7ee2a0;font-weight:700}
.disclaimer{margin:26px 0 10px;color:var(--mut);font-size:14px;line-height:1.7;
  border-top:1px solid var(--line);padding-top:14px}
#lb{position:fixed;inset:0;background:rgba(0,0,0,.85);display:none;align-items:center;
  justify-content:center;z-index:100;cursor:zoom-out}
#lb img{max-width:96vw;max-height:96vh}
a{color:var(--blue)}
.hrow{display:flex;align-items:center;justify-content:space-between;gap:12px}
.navlink{font-size:16px;color:#a8d8ff;background:#0c1c2a;border:1px solid #1f3a4a;
  border-radius:8px;padding:6px 12px;text-decoration:none;white-space:nowrap}
.navlink:hover{background:#12283a}
</style>
</head>
<body>
<header>
  <div class="hrow"><h1>台股做多選股報告</h1><span style="display:flex;gap:10px"><a class="navlink" href="home.html">🏠 首頁</a><a class="navlink" href="trends.html">趨勢線說明 →</a></span></div>
  <div class="sub" id="subline"></div>
  <div class="stats" id="stats"></div>
  <div class="filterbar">
    <button id="toggleFilters" class="fbtn">🔍 篩選條件 ▲</button>
    <button id="toggleSummary" class="fbtn">📋 條件總覽</button>
    <span id="count"></span>
  </div>
  <div id="summaryBox" class="sumbox" style="display:none"></div>
  <div id="filters">
  <div class="controls" style="margin-bottom:6px">
    <span class="param">總資金 NT$<input type="number" id="capital" value="300000" step="10000" min="10000"></span>
    <span class="param">價格 NT$<input type="number" id="pmin" value="20" step="1" min="0"> ~ <input type="number" id="pmax" value="100" step="1" min="0"></span>
    <span style="color:var(--mut);font-size:14px">(改總資金→即時重算口數/風險;改價格→篩選顯示)</span>
  </div>
  <div class="controls">
    <input type="text" id="q" placeholder="搜尋代號 / 名稱…">
    <select id="tier">
      <option value="">全部名單</option>
      <option value="主要" selected>主要(順勢)</option>
      <option value="次要">次要(觸底反彈)</option>
      <option value="未分類">未分類</option>
    </select>
    <select id="entry" title="進場方式">
      <option value="柏仁優先">進場:回測碰線買(柏仁優先)</option>
      <option value="突破買">進場:突破買</option>
    </select>
    <select id="strat" style="display:none"></select>
    <select id="market"><option value="">全部市場</option><option value="上市">上市</option><option value="上櫃">上櫃</option></select>
    <select id="pat"><option value="">全部形態</option></select>
    <select id="sort">
      <option value="score">依形態信心</option>
      <option value="risk">依風險%(低→高)</option>
      <option value="cost">依一張成本(低→高)</option>
      <option value="lots">依建議口數(多→少)</option>
    </select>
    <select id="timing">
      <option value="">全部進場時機</option>
      <option value="breakout_high">① 帶量突破前高</option>
      <option value="pullback_ma">② 回測均線不破</option>
      <option value="volume_surge">③ 5MV翻揚</option>
      <option value="any">符合任一時機</option>
    </select>
    <label class="toggle"><input type="checkbox" id="onlyAct" checked>只看可進場(口數≥1)</label>
    <label class="toggle"><input type="checkbox" id="onlyTimely" checked>只看時效內(未追高)</label>
    <label class="toggle" style="gap:8px">貼近進場 ±<span id="bandVal" style="color:var(--gold);font-weight:700;min-width:20px;display:inline-block">8</span>%
      <input type="range" id="bandSlider" min="0" max="30" step="1" value="8" style="width:120px;accent-color:var(--gold)"></label>
    <label class="toggle"><input type="checkbox" id="onlyBk">只看已突破</label>
    <label class="toggle"><input type="checkbox" id="onlyChart">只看有圖</label>
    <label class="toggle"><input type="checkbox" id="showOutline" checked>型態輪廓線</label>
    <button id="exportBtn" class="expbtn">⬇️ 匯出名單(XQ)</button>
  </div>
  </div>
</header>
<main>
  <div class="grid" id="grid"></div>
  <div class="disclaimer" id="disc"></div>
</main>
<div id="lb"><img id="lbimg" src=""></div>
<script>
const DATA = /*__DATA__*/;
const META = /*__META__*/;

document.getElementById('subline').textContent =
  `產生日期 ${META.date}　|　單筆風險 ${META.risk_pct}%　|　總資金與價格區間可在下方調整(即時重算)`;

document.getElementById('stats').innerHTML =
  `<div class="stat"><b>${META.total}</b>命中標的</div>` +
  `<div class="stat"><b>${DATA.filter(d=>d.tier==='主要').length}</b>主要(順勢)</div>` +
  `<div class="stat"><b>${DATA.filter(d=>d.tier==='次要').length}</b>次要(觸底反彈)</div>` +
  `<div class="stat"><b id="actStat">${META.actionable}</b>可進場(口數≥1)</div>`;

const patSel = document.getElementById('pat');
META.patterns.forEach(p=>{const o=document.createElement('option');o.value=p;o.textContent=p;patSel.appendChild(o);});

const stratSel = document.getElementById('strat');
if(META.setup_types && META.setup_types.length){
  stratSel.style.display='';
  const labels={'動能突破':'動能突破(飆股)','底部反轉':'底部反轉(買低)'};
  stratSel.innerHTML='<option value="">全部進場策略</option>'+
    META.setup_types.map(s=>`<option value="${s}">${labels[s]||s}</option>`).join('');
  document.getElementById('sort').value='rr';   // 飆股模式預設依 R/R 排序
}

document.getElementById('disc').innerHTML =
  '⚠️ <b>重要聲明</b>:本報告為演算法自動偵測之「候選標的 + 信心分數」,<b>非買賣建議</b>。' +
  '趨勢線、頸線、形態為程式近似判讀,務必對照 K 線圖人工複核。形態學為機率性工具,' +
  '突破可能失敗(假突破);資料來源為免費 API,偶有缺漏。投資有風險,盈虧自負。';

const fmt = n => (n==null?'—':Number(n).toLocaleString());
const grid = document.getElementById('grid');

const LOT = 1000;  // 一張股數
const RISKPCT = (META.risk_pct||1)/100;
// 依「現在的總資金」即時重算第一批口數(對應 risk.first_entry)
function firstEntry(entry, stop, cap){
  const stopPerLot=(entry-stop)*LOT, costPerLot=entry*LOT;
  if(stopPerLot<=0) return null;
  const lots=Math.max(0, Math.min(Math.floor(cap*RISKPCT/stopPerLot), Math.floor(cap/costPerLot)));
  const loss=lots*stopPerLot;
  return {lots, position_cost:Math.round(lots*costPerLot), actual_loss:Math.round(loss),
          risk_pct:+(loss/cap*100).toFixed(3), actionable:lots>=1};
}
// 加碼(+2R 加碼、停損移 +1R;對應 risk.pyramid_auto)
function pyramidAuto(entry, stop, n1, cap){
  const R=entry-stop, addEntry=entry+2*R, addStop=entry+1*R;
  const firstProfit=(addStop-entry)*n1*LOT, addStopLot=(addEntry-addStop)*LOT;
  if(addStopLot<=0) return null;
  const remaining=cap-n1*entry*LOT;
  const n2=Math.max(0, Math.min(Math.floor((cap*RISKPCT+firstProfit)/addStopLot), Math.floor(remaining/(addEntry*LOT))));
  const r=n2*addStopLot-firstProfit;
  return {add_entry:+addEntry.toFixed(2), add_stop:+addStop.toFixed(2), add_lots:n2,
          add_risk_pct:+(r/cap*100).toFixed(3), risk_free:r<=0};
}
function planOf(d, method, cap){
  if(!d.plans) return null;
  const base = (method==='突破買') ? d.plans['突破買'] : (d.plans['回測碰線買']||d.plans['突破買']);
  if(!base || base.entry==null) return base||null;
  const fe=firstEntry(base.entry, base.stop, cap);
  if(!fe) return base;
  const pyr = fe.actionable ? pyramidAuto(base.entry, base.stop, fe.lots, cap) : null;
  return Object.assign({}, base, fe, pyr||{add_entry:null,add_stop:null,add_lots:null,add_risk_pct:null,risk_free:false});
}
function isTimely(p){
  // 進場時效:現價離進場太遠(追高)就不算時效內
  if(!p || p.dist_pct==null) return false;
  const lim = p.method==='回測碰線買' ? META.entrable_pullback : META.entrable_breakout;
  return p.dist_pct <= lim;
}

function card(d, p){
  const chips = d.patterns.map(x=>{
    const bk = (x.breakout && x.name.indexOf('跳空')<0) ? ' bk':'';
    const tag = x.name.indexOf('跳空')>=0 ? '' : (x.breakout?' ✓突破':' 形成中');
    return `<span class="chip${bk}">${x.name}${tag}</span>`;
  }).join('');
  const src = (document.getElementById('showOutline').checked ? d.chart : d.chart_plain);
  const img = d.has_chart
    ? `<div class="imgwrap"><img loading="lazy" src="${src}" onclick="zoom('${src}')"></div>`
    : `<div class="imgwrap"><div class="noimg">（此檔未產生 K 線圖,可調高 --max-charts）</div></div>`;
  let risk;
  if(!p){
    risk = `<div class="warn">非順勢標的(無上升支撐/軌道下緣),沒有「回測碰線買」買點。請切到「突破買」看進場。</div>`;
  } else if(p.actionable){
    risk = `<div class="kv">
      <span class="k">進場價</span><span class="v blue">${p.entry}</span>
      <span class="k">停損價</span><span class="v red">${p.stop}（${p.source}）</span>
      <span class="k">建議口數</span><span class="v">${p.lots} 張</span>
      <span class="k">投入金額</span><span class="v">${fmt(p.position_cost)}</span>
      <span class="k">觸損虧損</span><span class="v red">${fmt(p.actual_loss)}</span>
      <span class="k">實際風險</span><span class="v">${p.risk_pct}%</span>
      <span class="k">加碼(+2R)</span><span class="v">${p.add_lots!=null?p.add_lots+' 張':'—'}</span>
      <span class="k">加碼後風險</span><span class="v ${p.risk_free?'green':''}">${p.add_risk_pct!=null?p.add_risk_pct+'%':'—'}${p.risk_free?' 無風險':''}</span>
    </div>`;
  } else {
    risk = `<div class="kv">
      <span class="k">進場價</span><span class="v blue">${p.entry??'—'}</span>
      <span class="k">停損價</span><span class="v red">${p.stop??'—'}（${p.source}）</span></div>
      <div class="warn">停損過寬:在 ${META.risk_pct}% 風險下買 1 張即超標,不建議進場(可縮小停損或提高風險設定)。</div>`;
  }
  const methodTag = p
    ? `<span class="mtag ${p.method==='回測碰線買'?'mpb':'mbk'}">${p.method}</span>` : '';
  const stage = p ? p.stage : null;
  const lateBadge = (p && !isTimely(p))
    ? `<span class="late">追高·太晚 +${p.dist_pct}%</span>` : '';
  const stageBadge = stage
    ? `<span class="stage ${stage==='即將突破'?'soon':'just'}">${stage}${p.dist_pct!=null?` ${p.dist_pct>0?'+':''}${p.dist_pct}%`:''}</span>` : '';
  const tierLabel = {'主要':'主要·順勢','次要':'次要·觸底反彈','未分類':'未分類'};
  const tierCls = {'主要':'main','次要':'sub','未分類':'none'};
  const tierBadge = d.tier
    ? `<span class="tier ${tierCls[d.tier]||'none'}">${tierLabel[d.tier]||d.tier}</span>` : '';
  const t = d.timing || {};
  const timingBadges =
    (t.breakout_high?`<span class="tm">① 帶量突破前高${t.vol_ratio?` ${t.vol_ratio}x量`:''}</span>`:'')+
    (t.pullback_ma?`<span class="tm">② 回測${t.ma_label||'均線'}不破</span>`:'')+
    (t.volume_surge?`<span class="tm">③ 5MV翻揚</span>`:'');
  return `<div class="card">${img}<div class="body">
    <div class="title"><span class="nm">${d.code} ${d.name}</span>
      <span class="mk">${d.market}</span>
      <span class="badge">信心 ${d.score}</span></div>
    <div class="chips">${tierBadge}${methodTag}${lateBadge}${stageBadge}</div>
    ${timingBadges?`<div class="chips">${timingBadges}</div>`:''}
    <div class="chips">${chips}</div>
    ${risk}
  </div></div>`;
}

function render(){
  const q=document.getElementById('q').value.trim();
  const ti=document.getElementById('tier').value;
  const method=document.getElementById('entry').value;
  const mk=document.getElementById('market').value;
  const pat=document.getElementById('pat').value;
  const oa=document.getElementById('onlyAct').checked;
  const otl=document.getElementById('onlyTimely').checked;
  const band=+document.getElementById('bandSlider').value;
  document.getElementById('bandVal').textContent=band;
  const tmg=document.getElementById('timing').value;
  const ob=document.getElementById('onlyBk').checked;
  const oc=document.getElementById('onlyChart').checked;
  const sort=document.getElementById('sort').value;
  const cap=Math.max(10000, +document.getElementById('capital').value||300000);
  const pmin=+document.getElementById('pmin').value, pmax=+document.getElementById('pmax').value;
  let list = DATA.filter(d=>{
    if(q && !(d.code.includes(q)||d.name.includes(q))) return false;
    if(ti && d.tier!==ti) return false;
    if(mk && d.market!==mk) return false;
    if(pat && !d.pattern_names.includes(pat)) return false;
    if(ob && !d.breakout) return false;
    if(oc && !d.has_chart) return false;
    if(!isNaN(pmin) && d.close<pmin) return false;
    if(!isNaN(pmax) && pmax>0 && d.close>pmax) return false;
    return true;
  }).map(d=>({d, p:planOf(d, method, cap)}));
  if(oa) list = list.filter(x=>x.p && x.p.actionable);
  if(otl) list = list.filter(x=>isTimely(x.p));
  if(band < 30) list = list.filter(x=>x.p && x.p.entry!=null && Math.abs(x.d.close - x.p.entry)/x.p.entry <= band/100);
  if(tmg){ const t=x=>x.d.timing||{};
    if(tmg==='any') list=list.filter(x=>t(x).breakout_high||t(x).pullback_ma||t(x).volume_surge);
    else list=list.filter(x=>t(x)[tmg]); }
  list.sort((a,b)=>{
    if(sort==='risk') return ((a.p&&a.p.risk_pct)??99)-((b.p&&b.p.risk_pct)??99);
    if(sort==='cost') return a.d.lot_cost-b.d.lot_cost;
    if(sort==='lots') return ((b.p&&b.p.lots)??0)-((a.p&&a.p.lots)??0);
    return b.d.score-a.d.score;
  });
  window.__filtered = list.map(x=>({code:x.d.code, name:x.d.name}));
  grid.innerHTML = list.map(x=>card(x.d, x.p)).join('');
  document.getElementById('count').textContent = `顯示 ${list.length} / ${DATA.length} 檔`;
  const as=document.getElementById('actStat');
  if(as) as.textContent = DATA.filter(d=>{const pp=planOf(d, method, cap); return pp&&pp.actionable;}).length;
  // 條件總覽
  const S=[];
  S.push('名單:'+(ti?({'主要':'主要(順勢)','次要':'次要(觸底反彈)','未分類':'未分類'}[ti]):'全部'));
  S.push('進場方式:'+(method==='突破買'?'突破買':'回測碰線買(柏仁優先)'));
  S.push('總資金 NT$'+cap.toLocaleString()+'(單筆風險'+META.risk_pct+'%)');
  S.push('價格 NT$'+(isNaN(pmin)?0:pmin)+'~'+(isNaN(pmax)||pmax<=0?'∞':pmax));
  if(oa) S.push('只看可進場(口數≥1)');
  if(otl) S.push('只看時效內(未追高)');
  S.push('貼近進場 ±'+band+'%');
  if(tmg) S.push('進場時機:'+(({breakout_high:'① 帶量突破前高',pullback_ma:'② 回測均線不破',volume_surge:'③ 5MV翻揚',any:'符合任一'})[tmg]||tmg));
  if(mk) S.push('市場:'+mk);
  if(pat) S.push('形態:'+pat);
  if(ob) S.push('只看已突破');
  if(q) S.push('搜尋:'+q);
  document.getElementById('summaryBox').innerHTML =
    '<b>目前套用條件 → 共 '+list.length+' 檔符合</b>'+
    '<div class="sumchips">'+S.map(s=>'<span class="sumchip">'+s+'</span>').join('')+'</div>'+
    (list.length?'<div class="sumlist">'+list.map(x=>x.d.code+' '+x.d.name).join('　')+'</div>':'<div class="sumlist">(無符合標的,可放寬條件)</div>');
}
document.getElementById('toggleFilters').addEventListener('click',function(){
  const f=document.getElementById('filters'), hidden=f.style.display==='none';
  f.style.display=hidden?'block':'none';
  this.textContent='🔍 篩選條件 '+(hidden?'▲':'▼');
});
document.getElementById('toggleSummary').addEventListener('click',function(){
  const s=document.getElementById('summaryBox');
  s.style.display=s.style.display==='none'?'block':'none';
});
function exportXQ(){
  const items = window.__filtered || [];
  if(!items.length){ alert('目前篩選沒有標的可匯出'); return; }
  // XQ 自選股:純文字、每行一個代號(台股 4 碼,XQ 自動辨識)
  const txt = items.map(it=>it.code).join('\r\n') + '\r\n';
  const blob = new Blob([txt], {type:'text/plain;charset=utf-8'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'XQ自選股_' + String(META.date||'').replace(/-/g,'') + '_' + items.length + '檔.txt';
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(a.href);
}
document.getElementById('exportBtn').addEventListener('click', exportXQ);
['q','tier','entry','market','pat','sort','timing','bandSlider','capital','pmin','pmax','onlyAct','onlyTimely','onlyBk','onlyChart','showOutline'].forEach(id=>{
  document.getElementById(id).addEventListener('input',render);
  document.getElementById(id).addEventListener('change',render);
});
function zoom(src){const lb=document.getElementById('lb');document.getElementById('lbimg').src=src;lb.style.display='flex';}
document.getElementById('lb').addEventListener('click',()=>document.getElementById('lb').style.display='none');
render();
</script>
</body>
</html>"""
