"""README용 그림 생성 (docs/figures/). 수집해 둔 data/ 캐시만 쓰고 DART API는 부르지 않는다.

실행 (프로젝트 폴더에서):  .venv\\Scripts\\python scripts\\make_figures.py
- 대조군은 현재 상장 기업이므로 그림에 기업명을 넣지 않는다 (research_design.md 9절)
- 밝은·어두운 테마 그림을 각각 만들어 GitHub 화면 테마에 맞춰 보이게 한다
"""
import ast
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import requests  # noqa: E402


def _no_api(*args, **kwargs):
    raise RuntimeError("그림 생성 중 API 호출 차단: data/ 캐시에 없는 자료입니다")


requests.get = _no_api

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

import src.pilot as pilot  # noqa: E402
from src.mscore import THRESHOLD  # noqa: E402

pilot.get_financials = _no_api
OUT = ROOT / "docs" / "figures"

THEMES = {   # 기본 팔레트 (분류색 1·2번, 표면·글자·보조선)
    "light": dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781",
                  grid="#e1e0d9", axis="#c3c2b7", s1="#2a78d6", s2="#eb6834"),
    "dark": dict(surface="#1a1a19", ink="#f0efec", ink2="#c3c2b7", muted="#898781",
                 grid="#2c2c2a", axis="#383835", s1="#3987e5", s2="#d95926"),
}


def _font():
    for name in ("Malgun Gothic", "NanumGothic", "AppleGothic", "Noto Sans CJK KR"):
        if any(f.name == name for f in font_manager.fontManager.ttflist):
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False


def pilot_points():
    """파일럿 사건 8개·대조군 8개의 직전 2개 연도 M-Score (research_design.md 8절)"""
    sample, _ = pilot.pick_events()
    ev = pilot.run_pilot(sample)
    m = pd.read_csv(ROOT / "data" / "pilot_control_map.csv", dtype={"대조군 corp_code": str})
    m["사업연도"] = m["사업연도"].map(ast.literal_eval)
    ct = pilot.run_controls(m)
    return pd.concat([
        pd.DataFrame({"군": "사건군", "기업": ev["회사명"], "시점": ev["시점"], "M": ev["M-Score"]}),
        pd.DataFrame({"군": "대조군", "기업": ct["대조군 ID"], "시점": ct["시점"], "M": ct["M-Score"]}),
    ], ignore_index=True)


def pilot_figure(pts, theme, path):
    t = THEMES[theme]
    fig, ax = plt.subplots(figsize=(9, 3.6), dpi=200)
    fig.patch.set_facecolor(t["surface"])
    ax.set_facecolor(t["surface"])

    rows = [("사건군", 1, t["s1"], "상장폐지 기업 8개"), ("대조군", 0, t["s2"], "같은 시장·업종·규모 정상기업 8개")]
    rng = np.random.default_rng(7)
    for grp, y, color, desc in rows:
        g = pts[pts["군"] == grp]
        jitter = rng.uniform(-0.13, 0.13, len(g))
        for (_, r), j in zip(g.iterrows(), jitter):
            filled = r["시점"] == "t-1"
            ax.scatter(r["M"], y + j, s=58, zorder=3, linewidths=1.6,
                       facecolor=color if filled else t["surface"], edgecolor=color)
        med = g["M"].median()
        ax.plot([med, med], [y - 0.28, y + 0.28], color=t["ink2"], lw=2, zorder=2, solid_capstyle="round")
        ax.text(med - 0.15, y - 0.36, f"중앙값 {med:.2f}", ha="right", va="top", fontsize=8.5, color=t["ink2"])
        firms = g.groupby("기업")["M"].apply(lambda s: (s > THRESHOLD).any())
        ax.text(1.01, y, f"경보 {int(firms.sum())}/{len(firms)}개 기업\n({firms.mean():.1%})",
                transform=ax.get_yaxis_transform(), va="center", ha="left", fontsize=10,
                color=t["ink"], fontweight="bold")
        ax.text(-0.01, y - 0.17, desc, transform=ax.get_yaxis_transform(), va="center", ha="right",
                fontsize=8, color=t["muted"])

    ax.axvline(THRESHOLD, color=t["ink2"], lw=1.2, ls=(0, (4, 3)), zorder=1)
    ax.text(THRESHOLD + 0.15, 1.52, f"경보 기준 {THRESHOLD}  →  이익조정 의심", fontsize=8.5,
            color=t["ink2"], va="center")

    ax.set_yticks([1, 0], ["사건군", "대조군"], fontsize=11, color=t["ink"], fontweight="bold")
    ax.tick_params(axis="y", length=0, pad=8)
    ax.tick_params(axis="x", colors=t["muted"], labelsize=9, length=0)
    ax.set_ylim(-0.65, 1.65)
    lo, hi = pts["M"].min(), pts["M"].max()
    ax.set_xlim(np.floor(lo) - 0.5, np.ceil(hi) + 0.5)
    ax.set_xlabel("Beneish M-Score (클수록 이익조정 가능성 높음)", fontsize=9, color=t["muted"])
    ax.grid(axis="x", color=t["grid"], lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(t["axis"])

    leg = [plt.Line2D([], [], ls="", marker="o", ms=7, mfc=t["ink2"], mec=t["ink2"], label="t-1 (폐지 직전 연도)"),
           plt.Line2D([], [], ls="", marker="o", ms=7, mfc=t["surface"], mec=t["ink2"], mew=1.6, label="t-2")]
    ax.legend(handles=leg, loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=2, frameon=False,
              fontsize=8.5, labelcolor=t["ink2"], handletextpad=0.3, columnspacing=1.2)
    fig.suptitle("파일럿: 상장폐지 직전 2개 사업연도의 M-Score", x=0.02, ha="left", fontsize=12.5,
                 color=t["ink"], fontweight="bold")
    fig.text(0.02, 0.885, "점 하나 = 기업-연도 · 세로 막대 = 중앙값 · 폐지일 이전에 공시된 사업보고서만 사용",
             fontsize=8.5, color=t["ink2"])
    fig.subplots_adjust(left=0.2, right=0.84, top=0.78, bottom=0.17)
    fig.savefig(path, facecolor=t["surface"])
    plt.close(fig)


def main():
    _font()
    OUT.mkdir(parents=True, exist_ok=True)
    pts = pilot_points()
    for theme in THEMES:
        pilot_figure(pts, theme, OUT / f"pilot_mscore_{theme}.png")
    print(f"저장: {OUT}")


if __name__ == "__main__":
    main()
