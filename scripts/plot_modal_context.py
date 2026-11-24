"""Render the manuscript context figure from the published aggregate counts."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
report = json.loads((ROOT/"reports/matched_context.json").read_text())
fig, ax = plt.subplots(figsize=(7.0, 2.7))
contrasts = [("abstract_minus_sentence","Abstract − sentence"), ("filler_minus_sentence","Donor text − sentence"),
             ("abstract_minus_filler","Abstract − donor text")]
styles = [("minicheck_roberta_large","RoBERTa","#164c78","o",.13),
          ("minicheck_deberta_v3_large","DeBERTa","#a54c1e","s",-.13)]
for model, label, color, marker, offset in styles:
    for i,(key, _) in enumerate(contrasts):
        row = report["models"][model]["comparisons"]["complete"][key]
        mid = 100*row["difference"]
        lo,hi = (100*n for n in row["interval95"])
        ax.errorbar(mid, 2-i+offset, xerr=[[mid-lo],[hi-mid]], fmt=marker, color=color,
                    markersize=5, capsize=3, label=label if i==0 else None)
ax.axvline(0,color="#60717b",lw=.9)
ax.set_yticks([2,1,0],[l for _,l in contrasts])
ax.set_ylim(-.45,2.65)
ax.set_xlim(-7,70)
ax.set_xticks(range(0,71,10))
ax.set_xlabel("Paired difference in acceptance (percentage points)")
ax.grid(axis="x",alpha=.24)
ax.set_axisbelow(True)
ax.tick_params(axis="both",length=0,pad=5)
ax.spines[["left","right","top"]].set_visible(False)
ax.spines["bottom"].set_color("#a1adb2")
ax.legend(loc="upper center", bbox_to_anchor=(.52,1.17),frameon=False,ncol=2)
fig.subplots_adjust(left=.29,right=.975,bottom=.26,top=.84)
fig.savefig(ROOT/"paper/matched-context.png",dpi=300,facecolor="white")
