"""Generate a local, score-blind text viewer for abstracts taller than an Excel row."""
import argparse
import html
import json
from pathlib import Path

TEMPLATE = """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>P10 · 证据原文</title><style>
body{font:17px/1.65 system-ui,sans-serif;max-width:850px;margin:24px auto;padding:0 18px;color:#192f36}
nav{background:#e5f0f1;padding:14px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}
input,button{font:inherit;padding:3px 8px} h1{font-size:24px}h2{font-size:17px;margin-bottom:2px}
p{margin:0 0 16px}article{border-bottom:1px solid #b9c9ca;padding:14px 0}
@media print{nav{display:none}}
</style><h1>P10 · 盲标证据原文</h1><nav><label>题号 <input type="search" id="search" placeholder="如 modal_strengthen-001"></label><button id="go">定位</button><button id="prev">上一题</button><button id="next">下一题</button><span id="status" role="status"></span></nav>
<p>题号与工作簿一致，标签请填在工作簿。可用浏览器查找功能或输入完整题号。</p>
"""
SCRIPT = """<script>
const rows=Array.from(document.querySelectorAll('article'));
const input=document.getElementById('search'), statusText=document.getElementById('status');
let current=0;
function showNext(i) {
  if(i<0||i>=rows.length)return;
  current=i;
  rows.forEach((row,j)=>{row.hidden=j!==current});
  input.value=rows[current].id;
  statusText.textContent=(current+1)+' / '+rows.length;
}
function locate(){let i=rows.findIndex(r=>r.id===input.value.trim());if(i>=0)showNext(i);else statusText.textContent='未找到该题号';}
document.getElementById('go').onclick=locate;
input.onkeydown=e=>{if(e.key==='Enter')locate()};
document.getElementById('prev').onclick=()=>showNext(current-1);
document.getElementById('next').onclick=()=>showNext(current+1);
let fromHash=rows.findIndex(r=>r.id===location.hash.slice(1));showNext(fromHash<0?0:fromHash);
</script></html>"""


def render(rows):
    order=["modal_strengthen","hedge_adverb_drop","scope_drop","causal_upgrade","quantifier_inflate","weaken","negate"]
    parts=[TEMPLATE]
    for r in sorted(rows,key=lambda r:(order.index(r["edit"]),r["order"])):
        ident=html.escape(r["id"],quote=True)
        parts.append(f'<article id="{ident}"><h1>{ident}</h1>')
        for label,key in (("原句","source"),("改写","edited"),("完整摘要","abstract")):
            parts.append(f"<h2>{label}</h2><p lang='en'>{html.escape(r[key])}</p>")
        parts.append("</article>")
    return "".join(parts)+SCRIPT


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("roster",type=Path)
    ap.add_argument("out",type=Path)
    a=ap.parse_args()
    a.out.write_text(render(list(map(json.loads,a.roster.read_text(encoding="utf-8").splitlines()))),encoding="utf-8")
