"""Matplotlib charts for the Analytics page (TkAgg)."""

from __future__ import annotations

import matplotlib

matplotlib.use("TkAgg")

from dataclasses import dataclass
from datetime import date, timedelta

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


@dataclass(frozen=True)
class ChartPalette:
    fig_face: str
    ax_face: str
    text: str
    muted: str
    accent: str
    grid: str
    tick: str


def _fmt_day_short(d: date) -> str:
    return d.strftime("%m-%d")


def render_trigger_figure(
    fig: Figure,
    *,
    palette: ChartPalette,
    mode: str,
    days_map: dict[str, dict],
    today_key: str,
    empty_msg: str,
    xlabel_today: str,
    xlabel_week: str,
    ylabel: str,
) -> None:
    fig.clear()
    fig.patch.set_facecolor(palette.fig_face)
    ax = fig.add_subplot(111)
    ax.set_facecolor(palette.ax_face)
    for spine in ax.spines.values():
        spine.set_color(palette.grid)
    ax.tick_params(colors=palette.tick, labelsize=9)
    ax.yaxis.label.set_color(palette.text)
    ax.xaxis.label.set_color(palette.text)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.grid(True, color=palette.grid, alpha=0.35)

    today_d = date.fromisoformat(today_key)

    if mode == "today":
        ax.set_xlabel(xlabel_today, fontsize=9)
        raw = days_map.get(today_key) or {}
        hrs = raw.get("hourly_nudges")
        hourly = list(hrs) if isinstance(hrs, list) and len(hrs) == 24 else [0] * 24
        xs = list(range(24))
        total = sum(hourly)
        if total == 0:
            ax.text(
                0.5,
                0.5,
                empty_msg,
                ha="center",
                va="center",
                transform=ax.transAxes,
                color=palette.muted,
                fontsize=10,
            )
            ax.set_xticks([0, 6, 12, 18, 23])
            ax.set_xlim(-0.5, 23.5)
        else:
            ax.plot(
                xs,
                hourly,
                color=palette.accent,
                linewidth=1.8,
                marker="o",
                markersize=3,
            )
            ax.set_xticks([0, 6, 12, 18, 23])
            ax.set_xlim(-0.5, 23.5)
            ymax = max(hourly)
            ax.set_ylim(0, max(1.0, ymax * 1.15))
    else:
        ax.set_xlabel(xlabel_week, fontsize=9)
        labels: list[str] = []
        counts: list[int] = []
        for i in range(6, -1, -1):
            d = today_d - timedelta(days=i)
            key = d.isoformat()
            labels.append(_fmt_day_short(d))
            raw = days_map.get(key) or {}
            hrs = raw.get("hourly_nudges")
            hourly = list(hrs) if isinstance(hrs, list) and len(hrs) == 24 else [0] * 24
            counts.append(sum(int(x) for x in hourly))
        total_w = sum(counts)
        xs = list(range(len(labels)))
        if total_w == 0:
            ax.text(
                0.5,
                0.5,
                empty_msg,
                ha="center",
                va="center",
                transform=ax.transAxes,
                color=palette.muted,
                fontsize=10,
            )
            ax.set_xticks(xs)
            ax.set_xticklabels(labels, rotation=25, ha="right")
        else:
            ax.plot(
                xs,
                counts,
                color=palette.accent,
                linewidth=1.8,
                marker="o",
                markersize=4,
            )
            ax.set_xticks(xs)
            ax.set_xticklabels(labels, rotation=25, ha="right")
            ymax = max(counts)
            ax.set_ylim(0, max(1.0, ymax * 1.15))

    fig.tight_layout()


def render_runtime_figure(
    fig: Figure,
    *,
    palette: ChartPalette,
    days_map: dict[str, dict],
    today_key: str,
    empty_msg: str,
    xlabel: str,
    ylabel_min: str,
    bar_days: int,
) -> None:
    fig.clear()
    fig.patch.set_facecolor(palette.fig_face)
    ax = fig.add_subplot(111)
    ax.set_facecolor(palette.ax_face)
    for spine in ax.spines.values():
        spine.set_color(palette.grid)
    ax.tick_params(colors=palette.tick, labelsize=9)
    ax.yaxis.label.set_color(palette.text)
    ax.xaxis.label.set_color(palette.text)
    ax.set_xlabel(xlabel, fontsize=9)
    ax.set_ylabel(ylabel_min, fontsize=9)
    ax.grid(True, axis="y", color=palette.grid, alpha=0.35)

    today_d = date.fromisoformat(today_key)
    labels: list[str] = []
    minutes: list[float] = []
    for i in range(bar_days - 1, -1, -1):
        d = today_d - timedelta(days=i)
        key = d.isoformat()
        labels.append(_fmt_day_short(d))
        raw = days_map.get(key) or {}
        sec = float(raw.get("runtime_sec", 0.0) or 0.0)
        minutes.append(sec / 60.0)

    xs = range(len(labels))
    total_m = sum(minutes)
    if total_m <= 0:
        ax.text(
            0.5,
            0.5,
            empty_msg,
            ha="center",
            va="center",
            transform=ax.transAxes,
            color=palette.muted,
            fontsize=10,
        )
        ax.set_xticks(list(xs))
        ax.set_xticklabels(labels, rotation=30, ha="right")
    else:
        ax.bar(
            list(xs),
            minutes,
            color=palette.accent,
            edgecolor=palette.grid,
            linewidth=0.5,
            alpha=0.85,
        )
        ax.set_xticks(list(xs))
        ax.set_xticklabels(labels, rotation=30, ha="right")
        ymax = max(minutes)
        ax.set_ylim(0, max(1.0, ymax * 1.12))

    fig.tight_layout()


def render_patterns_figure(
    fig: Figure,
    *,
    palette: ChartPalette,
    days_map: dict[str, dict],
    labels: tuple[str, str, str],
    empty_msg: str,
) -> None:
    fig.clear()
    fig.patch.set_facecolor(palette.fig_face)
    ax = fig.add_subplot(111)
    ax.set_facecolor(palette.ax_face)

    total_h = total_c = total_s = 0
    for _key, raw in days_map.items():
        if not isinstance(raw, dict):
            continue
        pat = raw.get("pattern")
        if not isinstance(pat, dict):
            continue
        total_h += int(pat.get("horizontal", 0) or 0)
        total_c += int(pat.get("circle", 0) or 0)
        total_s += int(pat.get("square", 0) or 0)

    sizes = [total_h, total_c, total_s]
    total = sum(sizes)

    if total == 0:
        ax.text(
            0.5,
            0.5,
            empty_msg,
            ha="center",
            va="center",
            transform=ax.transAxes,
            color=palette.muted,
            fontsize=10,
        )
        ax.axis("off")
    else:
        colors_pie = ("#58A6FF", "#3FB950", "#E3B341")
        explode = (0.02, 0.02, 0.02)
        ax.pie(
            sizes,
            labels=labels,
            autopct="%1.0f%%",
            startangle=90,
            colors=colors_pie,
            explode=explode,
            textprops={"color": palette.text, "fontsize": 9},
            wedgeprops={"linewidth": 0.5, "edgecolor": palette.grid},
        )
        ax.axis("equal")

    fig.tight_layout()


def attach_canvas(fig: Figure, master: object) -> FigureCanvasTkAgg:
    canvas = FigureCanvasTkAgg(fig, master=master)
    canvas.draw()
    widget = canvas.get_tk_widget()
    widget.configure(highlightthickness=0, bd=0)
    widget.pack(fill="both", expand=True)
    return canvas
