from pathlib import Path
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

def plot(summary,path):
    source=summary["source"]
    labels=["Reviewed source rows","Outside prior manifests","Allocated to screening","Functional controls passed","Repeated student error","Confirmed teacher gap"]
    counts=[source["tool_scope"],source["fresh_relative_to_manifests"],source["split_counts"]["train"],len(summary["student"]),len(summary["first_repeatable_semantic_ids"]),len(summary["confirmed_ids"])]
    fig,(left,right)=plt.subplots(1,2,figsize=(12.2,6.25),gridspec_kw={"width_ratios":[1,1.25]})
    left.barh(range(len(labels)),counts,color=["#5e7694"]*3+["#34614f"]*3,height=.55)
    for i,k in enumerate(counts):left.text(k+3,i,str(k),va="center",fontsize=10)
    left.set(yticks=range(len(labels)),yticklabels=labels,xlim=(0,max(counts)*1.15),xlabel="Source questions")
    left.invert_yaxis()
    left.set_title("Screening and confirmation",loc="left")
    palette={"pass":"#27785e","semantic":"#bd4d37","constraint":"#ac6a04","unresolved":"#737483","format":"#5581ad","truncated":"#974f89"}
    rows=summary["student"]
    for y,row in enumerate(rows):
        for x,draw in enumerate(row["draws"]):
            right.scatter(x,y,s=133,marker="s",color=palette[draw["functional"]],edgecolors="white",linewidth=.8)
    right.set(xticks=range(3),xticklabels=[str(s) for s in summary["first_seeds"]],yticks=range(len(rows)),yticklabels=[r["id"].replace("sample_","#")+"   "+r["tool"] for r in rows],xlim=(-.55,2.55),xlabel="Decoding seed")
    right.invert_yaxis()
    right.set_title("Original Qwen3-8B on screened TRAIN items",loc="left")
    states=[k for k in palette if summary["first_verdict_counts"].get(k,0)]
    fig.legend([Patch(facecolor=palette[k]) for k in states],states,loc="lower center",ncol=min(6,len(states)),frameon=False)
    for ax in (left,right):
        for s in ("top","right","left"):ax.spines[s].set_visible(False)
        ax.tick_params(axis="y",length=0)
    fig.subplots_adjust(left=.165,right=.97,top=.86,bottom=.19,wspace=.72)
    fig.suptitle("KaliBench TRAIN • offline inventory pilot",fontsize=16,x=.05,ha="left",fontweight="bold")
    fig.savefig(path,dpi=160,facecolor="white");plt.close(fig)
if __name__=="__main__":
    here=Path(__file__).parent
    plot(json.loads((here/"summary.json").read_text()),here/"screening.png")
