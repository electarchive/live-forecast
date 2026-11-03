import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INK = "#1f2328"
MUTED = "#656d76"
GRID = "#d0d7de"
REAL = "#0969da"
SIMULATED = "#8c959f"
FONT = "font-family='-apple-system, Segoe UI, Helvetica, Arial, sans-serif'"


def text(x: float, y: float, body: str, size: int = 12, anchor: str = "middle", fill: str = INK, weight: str = "normal") -> str:
    return f"<text x='{x:.1f}' y='{y:.1f}' font-size='{size}' text-anchor='{anchor}' fill='{fill}' font-weight='{weight}' {FONT}>{body}</text>"


def reliability(title: str, bins: list[list[float]], path: Path) -> None:
    size, left, top = 360, 56, 48
    width, height = left + size + 24, top + size + 64
    x = lambda value: left + value * size
    y = lambda value: top + size - value * size
    parts = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>"]
    parts.append(f"<rect width='{width}' height='{height}' fill='#ffffff'/>")
    parts.append(text(left, 24, title, 15, "start", INK, "600"))
    for tick in (0, 0.25, 0.5, 0.75, 1):
        parts.append(f"<line x1='{x(tick):.1f}' y1='{top}' x2='{x(tick):.1f}' y2='{top + size}' stroke='{GRID}'/>")
        parts.append(f"<line x1='{left}' y1='{y(tick):.1f}' x2='{left + size}' y2='{y(tick):.1f}' stroke='{GRID}'/>")
        parts.append(text(x(tick), top + size + 18, f"{tick:.0%}", 11, "middle", MUTED))
        parts.append(text(left - 8, y(tick) + 4, f"{tick:.0%}", 11, "end", MUTED))
    parts.append(f"<line x1='{x(0)}' y1='{y(0)}' x2='{x(1)}' y2='{y(1)}' stroke='{MUTED}' stroke-dasharray='4 4'/>")
    most = max(count for _, _, count in bins)
    line = " ".join(f"{x(p):.1f},{y(o):.1f}" for p, o, _ in bins)
    parts.append(f"<polyline points='{line}' fill='none' stroke='{REAL}' stroke-width='1.5'/>")
    for p, o, count in bins:
        radius = 3 + 9 * (count / most) ** 0.5
        parts.append(f"<circle cx='{x(p):.1f}' cy='{y(o):.1f}' r='{radius:.1f}' fill='{REAL}' fill-opacity='0.85' stroke='{REAL}' stroke-width='1.5'/>")
    parts.append(text(left + size / 2, top + size + 38, "Stated chance that the Democrat wins", 12))
    parts.append(f"<g transform='translate(16 {top + size / 2}) rotate(-90)'>{text(0, 0, 'Share of checkpoints the Democrat won', 12)}</g>")
    parts.append(text(left + size, top + size + 56, "Circle area shows checkpoints", 11, "end", MUTED))
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n")


def stages(title: str, scores: dict, path: Path) -> None:
    labels = {"0-0.5": "Under 50%", "0.5-0.8": "50 to 80%", "0.8-0.95": "80 to 95%", "0.95-9": "95% or more"}
    series = (("real", REAL), ("simulated", SIMULATED))
    rows = [(label, {name: scores[name]["stages"][stage] for name, _ in series}) for stage, label in labels.items()]
    left, top, band, chart = 120, 48, 52, 320
    width, height = left + chart + 120, top + band * len(rows) + 56
    most = max(found.get("log", 0.0) for _, values in rows for found in values.values())
    scale = chart / most
    parts = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>"]
    parts.append(f"<rect width='{width}' height='{height}' fill='#ffffff'/>")
    parts.append(text(16, 24, title, 15, "start", INK, "600"))
    for index, (label, values) in enumerate(rows):
        base = top + index * band
        parts.append(text(left - 10, base + 20, label, 12, "end", INK))
        for offset, (name, color) in zip((4, 22), series, strict=True):
            found = values[name]
            if not found:
                parts.append(text(left + 6, base + offset + 11, "no checkpoints", 11, "start", MUTED))
                continue
            value = found["log"]
            parts.append(f"<rect x='{left}' y='{base + offset}' width='{value * scale:.1f}' height='14' fill='{color}'/>")
            parts.append(text(left + value * scale + 6, base + offset + 11, f"{value:.3f} ({found['n']:,} checkpoints)", 11, "start", MUTED))
    legend = top + band * len(rows) + 20
    parts.append(f"<rect x='{left}' y='{legend - 10}' width='12' height='12' fill='{REAL}'/>")
    parts.append(text(left + 18, legend, "Real nights, 2020 and 2022", 12, "start", MUTED))
    parts.append(f"<rect x='{left + 200}' y='{legend - 10}' width='12' height='12' fill='{SIMULATED}'/>")
    parts.append(text(left + 218, legend, "Simulated nights", 12, "start", MUTED))
    parts.append(text(16, legend + 24, "Log loss by share of the final vote counted; lower is better", 11, "start", MUTED))
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n")


if __name__ == "__main__":
    scores = json.loads((ROOT / "outputs/scores.json").read_text())
    (ROOT / "figures").mkdir(exist_ok=True)
    reliability("Real nights: 2020 and 2022", scores["real"]["reliability"], ROOT / "figures/reliability-real.svg")
    reliability("Simulated nights", scores["simulated"]["reliability"], ROOT / "figures/reliability-simulated.svg")
    stages("Log loss as the count goes on", scores, ROOT / "figures/stages.svg")
