#!/usr/bin/env python3
"""Generate static SVG bar charts from benchmark results.json (real measured data)."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = "/home/tim/git/rust-node-exporter/docs"
os.makedirs(os.path.join(DOCS, "assets"), exist_ok=True)

r = json.load(open(os.path.join(HERE, "results.json")))

GREEN = "#2ea043"   # rust
BLUE = "#58a6ff"    # node common
PURPLE = "#8957e5"  # node defaults
TXT = "#c9d1d9"
GRID = "#30363d"

# (file, title, subtitle, [(label, value, color)], unit, fmt)
MB = 1024 * 1024
charts = [
    ("memory.svg", "Memory (resident, after warmup)",
     "lower is better · scraped every second for 100 scrapes",
     [
         ("rust-node-exporter — common collectors", r["rust_common"]["rss_after_warmup_kb"] / 1024, GREEN),
         ("node_exporter — common collectors", r["node_common"]["rss_after_warmup_kb"] / 1024, BLUE),
         ("node_exporter — all default collectors", r["node_defaults"]["rss_after_warmup_kb"] / 1024, PURPLE),
     ], "MB", lambda v: f"{v:.1f} MB"),
    ("cpu.svg", "CPU time per scrape",
     "process utime+stime averaged over 100 scrapes · lower is better",
     [
         ("rust-node-exporter — common collectors", r["rust_common"]["cpu_ms_per_scrape"], GREEN),
         ("node_exporter — common collectors", r["node_common"]["cpu_ms_per_scrape"], BLUE),
         ("node_exporter — all default collectors", r["node_defaults"]["cpu_ms_per_scrape"], PURPLE),
     ], "ms CPU", lambda v: f"{v:.1f} ms"),
    ("latency.svg", "Scrape latency (mean of 100 sequential scrapes)",
     "TCP connect → full body read, localhost · lower is better",
     [
         ("rust-node-exporter — common collectors", r["rust_common"]["latency_mean_ms"], GREEN),
         ("node_exporter — common collectors", r["node_common"]["latency_mean_ms"], BLUE),
         ("node_exporter — all default collectors", r["node_defaults"]["latency_mean_ms"], PURPLE),
     ], "ms", lambda v: f"{v:.1f} ms"),
    ("binary.svg", "Binary size",
     "rust: release build with lto = true",
     [
         ("rust-node-exporter 0.2.5", r["binary_sizes"]["rust-node-exporter"] / MB, GREEN),
         ("node_exporter 1.13.1", r["binary_sizes"]["node_exporter"] / MB, BLUE),
     ], "MB", lambda v: f"{v:.1f} MB"),
]

W, LBL, GAP, BAR_H, PAD_L = 760, 300, 14, 34, 0
for fname, title, subtitle, bars, unit, fmt in charts:
    vmax = max(v for _, v, _ in bars) * 1.18
    chart_w = W - LBL - 90
    height = 60 + len(bars) * (BAR_H + GAP) + 10
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {height}" '
        f'font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif">',
        f'<rect width="{W}" height="{height}" fill="#0d1117" rx="8"/>',
        f'<text x="24" y="34" fill="#e6edf3" font-size="17" font-weight="600">{title}</text>',
        f'<text x="24" y="54" fill="#8b949e" font-size="12">{subtitle}</text>',
    ]
    y = 78
    for label, v, color in bars:
        bw = max(2, v / vmax * chart_w)
        parts.append(f'<text x="24" y="{y + BAR_H / 2 + 4}" fill="{TXT}" font-size="12.5">{label}</text>')
        parts.append(
            f'<rect x="{LBL}" y="{y}" width="{bw}" height="{BAR_H}" rx="4" fill="{color}" opacity="0.92"/>')
        parts.append(
            f'<text x="{LBL + bw + 8}" y="{y + BAR_H / 2 + 4}" fill="#e6edf3" '
            f'font-size="12.5" font-weight="600">{fmt(v)}</text>')
        y += BAR_H + GAP
    parts.append(f'<text x="{LBL}" y="{y + 2}" fill="#8b949e" font-size="11">0 {unit}</text>')
    parts.append(f'<text x="{LBL + chart_w}" y="{y + 2}" fill="#8b949e" font-size="11" text-anchor="end">{fmt(vmax / 1.18)}</text>')
    parts.append("</svg>")
    with open(os.path.join(DOCS, "assets", fname), "w") as f:
        f.write("".join(parts))
    print("wrote", fname)
