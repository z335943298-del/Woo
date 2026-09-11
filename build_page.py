# -*- coding: utf-8 -*-
"""补抓概念净流出真榜单 + 生成单页 HTML（零依赖，内联 SVG/CSS）"""
import requests, json, time, html as H
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
S = requests.Session(); S.headers.update({"User-Agent": UA, "Referer": "https://quote.eastmoney.com/"})
S.mount("https://", HTTPAdapter(max_retries=Retry(total=3, connect=3, read=3, backoff_factor=0.6)))
FIELDS = "f3,f12,f14,f62,f104,f105,f184,f128,f136"
NOISE = {"B股", "ST股", "融资融券", "AH股", "富时罗素", "标准普尔", "MSCI中国", "深股通", "沪股通",
         "大盘股", "中盘股", "小盘股", "东方财富热股", "机构重仓", "基金重仓", "预盈预增", "次新股",
         "举牌", "昨日涨停", "昨日连板", "昨日首板", "高送转", "壳资源"}
NOISE_SUB = ("风格", "成长", "价值", "500", "300", "180", "100", "50_", "预增", "预盈", "预亏",
             "摘帽", "破净", "重仓", "做市商", "ETF", "指数", "MSCI", "股通")

snap = json.load(open("data/snapshot.json", encoding="utf-8"))

def clist(fs, fid, po, pz, label, tries=6):
    for i in range(tries):
        h = ["https://push2delay.eastmoney.com", "https://push2.eastmoney.com"][i % 2]
        try:
            r = S.get(h + "/api/qt/clist/get",
                      params={"pn": "1", "pz": str(pz), "po": str(po), "np": "1", "fltt": "2", "invt": "2",
                              "fid": fid, "fs": fs, "fields": FIELDS}, timeout=15)
            items = (r.json().get("data") or {}).get("diff") or []
            if items:
                print(f"[OK] {label} got={len(items)}")
                return items
        except Exception as e:
            print(f"[EE] {label} {type(e).__name__}")
        time.sleep(1.2)
    return []

raw_out = clist("m:90+t:3", "f62", 0, 100, "概念净流出全量")
clean_out = []
for i in raw_out:
    n = i.get("f14") or ""
    if n in NOISE or "_" in n or any(s in n for s in NOISE_SUB):
        continue
    clean_out.append({"name": n, "main_net_yi": round((i.get("f62") or 0) / 1e8, 2),
                      "pct": i.get("f3"), "up": i.get("f104"), "down": i.get("f105")})
    if len(clean_out) >= 8:
        break
if clean_out:
    snap["concepts"]["bottom_flow"] = clean_out
    print("净流出榜:", [(r["name"], r["main_net_yi"]) for r in clean_out])

json.dump(snap, open("data/snapshot.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ============ 生成 HTML ============
d = snap

def idx(name):
    for i in d["indices"]:
        if i["name"] == name: return i
    return None

sh, sz = idx("上证指数"), idx("深证综指")
total_amt = round(sh["amount_yi"] + sz["amount_yi"], 1)
br = d["breadth"]
up_ratio = round(br["up"] / (br["up"] + br["down"]) * 100, 1)
m = d["margin_raw"]
margin_last = m[0]
series = list(reversed(m))  # 升序

def pct_cls(v):
    return "up" if v > 0 else ("down" if v < 0 else "flat")

def sign(v, unit="%"):
    return f"+{v}{unit}" if v > 0 else f"{v}{unit}"

# 指数卡片
CARD_ORDER = ["上证指数", "深证成指", "创业板指", "沪深300", "上证50", "中证1000", "科创50", "北证50"]
cards = ""
for n in CARD_ORDER:
    i = idx(n)
    if not i: continue
    cards += f'''<div class="card {pct_cls(i["pct"])}">
      <div class="cname">{n}</div>
      <div class="cval">{i["close"]:,.2f}</div>
      <div class="cpct">{sign(i["pct"])}</div>
    </div>'''

# 大小盘条形
SIZE_ORDER = ["上证50", "沪深300", "中证500", "中证1000", "北证50"]
maxabs = max(abs(idx(n)["pct"]) for n in SIZE_ORDER) or 1
size_bars = ""
for n in SIZE_ORDER:
    i = idx(n)
    w = abs(i["pct"]) / maxabs * 100
    size_bars += f'''<div class="row">
      <div class="rlabel">{n}</div>
      <div class="rtrack"><div class="rbar {pct_cls(i["pct"])}" style="width:{w:.1f}%"></div></div>
      <div class="rval {pct_cls(i["pct"])}">{sign(i["pct"])}</div>
    </div>'''

# 概念涨幅
cg = d["concepts"]["top_gain"][:10]
maxg = max(abs(r["pct"]) for r in cg) or 1
gain_bars = ""
for r in cg:
    w = abs(r["pct"]) / maxg * 100
    lead = f'{r["leader"]} {sign(r["leader_pct"]) if r["leader_pct"] is not None else ""}'
    gain_bars += f'''<div class="row">
      <div class="rlabel">{H.escape(r["name"])}</div>
      <div class="rtrack"><div class="rbar {pct_cls(r["pct"])}" style="width:{w:.1f}%"></div></div>
      <div class="rval {pct_cls(r["pct"])}">{sign(r["pct"])}</div>
      <div class="rnote">领涨 {H.escape(lead)}</div>
    </div>'''

# 概念资金流入
cf = d["concepts"]["top_flow"][:10]
maxf = max(abs(r["main_net_yi"] or 0) for r in cf) or 1
flow_bars = ""
for r in cf:
    v = r["main_net_yi"] or 0
    w = abs(v) / maxf * 100
    flow_bars += f'''<div class="row">
      <div class="rlabel">{H.escape(r["name"])}</div>
      <div class="rtrack"><div class="rbar {pct_cls(v)}" style="width:{w:.1f}%"></div></div>
      <div class="rval {pct_cls(v)}">{sign(v,"亿")}</div>
      <div class="rnote">板块内 {r["up"]}涨/{r["down"]}跌</div>
    </div>'''

# 概念资金流出
cout = d["concepts"]["bottom_flow"][:8]
maxo = max(abs(r["main_net_yi"] or 0) for r in cout) or 1
out_bars = ""
for r in cout:
    v = r["main_net_yi"] or 0
    w = abs(v) / maxo * 100
    out_bars += f'''<div class="row">
      <div class="rlabel">{H.escape(r["name"])}</div>
      <div class="rtrack"><div class="rbar {pct_cls(v)}" style="width:{w:.1f}%"></div></div>
      <div class="rval {pct_cls(v)}">{sign(v,"亿")}</div>
    </div>'''

# 行业涨幅
ind_bars = ""
for r in d["industries"][:8]:
    v = r["pct"]
    ind_bars += f'''<div class="row">
      <div class="rlabel">{H.escape(r["name"])}</div>
      <div class="rtrack"><div class="rbar {pct_cls(v)}" style="width:{abs(v)/max(abs(x["pct"]) for x in d["industries"][:8] or [1])*100:.1f}%"></div></div>
      <div class="rval {pct_cls(v)}">{sign(v)}</div>
      <div class="rnote">主力 {sign(r["main_net_yi"] or 0,"亿")}</div>
    </div>'''

# 两融折线（SVG）
W, Hh, PAD = 620, 180, 40
vals = [r["RZYE"] / 1e8 for r in series]
lo, hi = min(vals) - 60, max(vals) + 60
n = len(vals)
pts = []
for k, v in enumerate(vals):
    x = PAD + k * (W - 2 * PAD) / (n - 1)
    y = Hh - PAD - (v - lo) / (hi - lo) * (Hh - 2 * PAD)
    pts.append((x, y))
poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#c0392b"/>' for x, y in pts)
labels = "".join(
    f'<text x="{x:.1f}" y="{Hh-14}" font-size="10" fill="#8a8a8a" text-anchor="middle">{series[k]["DIM_DATE"][5:10]}</text>'
    for k, (x, y) in enumerate(pts))
vals_txt = "".join(
    f'<text x="{x:.1f}" y="{y-9:.1f}" font-size="10" fill="#333" text-anchor="middle">{vals[k]:.0f}</text>'
    for k, (x, y) in enumerate(pts))
rzi = margin_last["RZJME"] / 1e8
margin_svg = f'''<svg viewBox="0 0 {W} {Hh}" width="100%" role="img">
<title>融资余额近8个交易日走势</title>
<line x1="{PAD}" y1="{Hh-PAD}" x2="{W-PAD}" y2="{Hh-PAD}" stroke="#e5e5e5" stroke-width="1"/>
<polyline points="{poly}" fill="none" stroke="#c0392b" stroke-width="2"/>
{dots}{labels}{vals_txt}
</svg>'''

ts = sh["ts"]
ts_fmt = f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]} {ts[8:10]}:{ts[10:12]}"

HTML = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>A股市场速读 · {ts_fmt[:10]}</title>
<style>
  :root {{ --up:#c0392b; --down:#0f9d58; --ink:#222; --muted:#7b7b7b; --line:#e8e6e1; --bg:#faf9f7; --card:#fff; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; padding:24px 16px 60px; background:var(--bg); color:var(--ink);
         font-family:-apple-system,"Segoe UI","Microsoft YaHei","PingFang SC",sans-serif; line-height:1.6; }}
  .wrap {{ max-width:900px; margin:0 auto; }}
  h1 {{ font-size:22px; margin:0 0 4px; font-weight:600; }}
  h2 {{ font-size:16px; margin:28px 0 10px; font-weight:600; }}
  .sub {{ color:var(--muted); font-size:12px; margin-bottom:18px; }}
  .lead {{ background:var(--card); border:1px solid var(--line); border-left:4px solid #c0392b;
           border-radius:8px; padding:14px 16px; font-size:15px; }}
  .grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:8px; padding:10px 12px; }}
  .cname {{ font-size:12px; color:var(--muted); }}
  .cval {{ font-size:17px; font-weight:600; margin:2px 0; }}
  .cpct {{ font-size:13px; font-weight:600; }}
  .up {{ color:var(--up); }} .down {{ color:var(--down); }} .flat {{ color:var(--muted); }}
  .card.up {{ border-top:3px solid var(--up); }} .card.down {{ border-top:3px solid var(--down); }}
  .panel {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px 18px; margin-top:12px; }}
  .row {{ display:grid; grid-template-columns:110px 1fr 74px 116px; align-items:center; gap:8px; margin:7px 0; font-size:13px; }}
  .rlabel {{ color:#333; }}
  .rtrack {{ background:#f1efec; border-radius:4px; height:14px; overflow:hidden; }}
  .rbar {{ height:100%; border-radius:4px; }}
  .rbar.up {{ background:var(--up); }} .rbar.down {{ background:var(--down); }}
  .rval {{ text-align:right; font-variant-numeric:tabular-nums; font-weight:600; }}
  .rnote {{ color:var(--muted); font-size:11px; }}
  .kpi {{ display:flex; flex-wrap:wrap; gap:18px; margin-bottom:6px; }}
  .kpi div {{ font-size:13px; color:var(--muted); }}
  .kpi b {{ display:block; font-size:20px; color:var(--ink); font-weight:600; }}
  .note {{ background:#fff8e6; border:1px solid #f0e0b8; border-radius:8px; padding:12px 14px; font-size:12.5px; color:#5c4a1a; }}
  .glossary dt {{ font-weight:600; font-size:13px; margin-top:8px; }}
  .glossary dd {{ margin:2px 0 0; font-size:12.5px; color:#555; }}
  footer {{ margin-top:26px; font-size:11.5px; color:var(--muted); border-top:1px solid var(--line); padding-top:12px; }}
  @media (max-width:640px) {{
    .grid {{ grid-template-columns:repeat(2,1fr); }}
    .row {{ grid-template-columns:88px 1fr 66px; }}
    .rnote {{ display:none; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <h1>A股市场速读 · {ts_fmt[:10]}</h1>
  <div class="sub">数据抓取时间 {ts_fmt}（A股当日已收盘）· 所有数字均来自公开行情接口，无估算、无填充</div>

  <div class="lead">
    <b>一句话看懂：</b>今天是个"多数股票在跌"的日子——全市场 {br['up']} 只上涨、{br['down']} 只在跌，
    大约每 6 只股票里只有 1 只在涨。下跌的时候，<b>大公司的股票明显比小公司抗跌</b>（上证50 {sign(idx('上证50')['pct'])} vs 中证1000 {sign(idx('中证1000')['pct'])}）。
    钱在往电力、PCB、存储芯片这些方向集中，而机器人概念是今天最大的资金流出方向。
  </div>

  <h2>一、大盘温度：钱有多少、情绪多热</h2>
  <div class="panel">
    <div class="kpi">
      <div>沪深两市成交额<b>{total_amt/10000:.2f} 万亿</b></div>
      <div>上涨家数<b class="up">{br['up']}</b></div>
      <div>下跌家数<b class="down">{br['down']}</b></div>
      <div>上涨占比<b>{up_ratio}%</b></div>
    </div>
    <div class="note">成交额就是"今天一共成交了多少钱"。它本身不分好坏，代表市场的活跃程度——只有和平时比才有意义，所以这一版先只给你原始数字。</div>
    <div class="grid" style="margin-top:14px">{cards}</div>
  </div>

  <h2>二、大小盘：跌的时候，谁更抗跌</h2>
  <div class="panel">
    {size_bars}
    <div class="note">从上到下 = 公司规模从大到小。<b>负得越少 = 越抗跌</b>。今天规律很清楚：公司越大越抗跌，小公司（中证1000）和北交所（北证50）跌得最狠。</div>
  </div>

  <h2>三、概念板块：钱在往哪里跑</h2>
  <div class="panel">
    <div style="font-size:13px;color:var(--muted);margin-bottom:6px">涨幅居前的概念（涨幅 = 板块内股票平均涨了多少）</div>
    {gain_bars}
  </div>
  <div class="panel">
    <div style="font-size:13px;color:var(--muted);margin-bottom:6px">主力资金<b>净流入</b>居前（主力 = 大资金，净流入 = 买入减卖出）</div>
    {flow_bars}
  </div>
  <div class="panel">
    <div style="font-size:13px;color:var(--muted);margin-bottom:6px">主力资金<b>净流出</b>居前（这些方向在被卖）</div>
    {out_bars}
  </div>

  <h2>四、行业涨幅前八（细分行业，供交叉验证）</h2>
  <div class="panel">{ind_bars}</div>

  <h2>五、两融余额：加杠杆的人在做什么</h2>
  <div class="panel">
    <div class="kpi">
      <div>融资余额<b>{margin_last['RZYE']/1e8/10000:.2f} 万亿</b></div>
      <div>当日融资净买入<b class="{pct_cls(rzi)}">{sign(round(rzi,1),'亿')}</b></div>
      <div>融资余额占流通市值<b>{margin_last['RZYEZB']:.2f}%</b></div>
      <div>数据日期<b>{margin_last['DIM_DATE'][:10]}</b></div>
    </div>
    {margin_svg}
    <div class="note">"两融"= 借钱买股票（融资）+ 借股票卖出（融券）。融资余额上升说明借钱进场的人在增加，下降说明他们在撤退。
    今天这个数字是 <b>{margin_last['DIM_DATE'][:10]}</b> 的——两融数据比行情晚一天公布，这是数据源的限制，不是我们偷懒。</div>
  </div>

  <h2>六、名词对照表（非专业版）</h2>
  <div class="panel glossary">
    <dl>
      <dt>主力净流入</dt><dd>大资金当天买入金额减去卖出金额。正数=净买，负数=净卖。</dd>
      <dt>成交额</dt><dd>当天所有成交的总金额，衡量市场热闹程度。</dd>
      <dt>上证50 / 中证1000</dt><dd>上证50 = 上海最大的 50 家公司；中证1000 = 1000 家较小的公司。用它们的涨跌对比，就能看出"大盘股 vs 小盘股"谁更强。</dd>
      <dt>两融余额</dt><dd>投资者借来的钱和股票的总量。它是市场情绪的放大镜：涨的时候推波助澜，跌的时候加速下跌。</dd>
      <dt>概念板块</dt><dd>按"题材"给股票分组，比如机器人口袋里装的是所有跟机器人沾边的公司。它比行业板块更敏感，波动也更大。</dd>
    </dl>
  </div>

  <h2>七、这一版没有的东西（诚实说明）</h2>
  <div class="panel">
    <div class="note">
      <b>北向资金（外资）没有放进来，不是忘了，是数据源层面已经拿不到了。</b>
      沪深股通自 2024 年 8 月起调整了信息披露机制，不再实时公布"买入/卖出金额"，只保留每日收盘后公布的成交总额。
      我这次抓到的字段里，净买入相关字段确实全部为空——如果页面硬要给你显示一个"北向实时净流入 XX 亿"，
      那个数字只能是编的。<b>为了守住"零幻觉"，宁可少一个面板。</b>
    </div>
  </div>

  <footer>
    数据来源：腾讯财经（指数行情）、东方财富（概念/行业板块、两融）· 抓取时间 {ts_fmt} ·
    行情为当日收盘快照，两融为 T+1 披露 · 本页仅为个人学习用途，不构成任何投资建议。数据可能存在上游延迟或错误，交易决策请以券商行情为准。
  </footer>
</div>
</body>
</html>
'''

open("market-dashboard-20260910.html", "w", encoding="utf-8").write(HTML)
print("已生成 market-dashboard-20260910.html", len(HTML), "字节")
