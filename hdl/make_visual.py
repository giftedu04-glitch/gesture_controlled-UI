"""Generate the visual HTML test report (circuit, gestures, waveform, results).

Reads the Icarus VCD dump plus the cocotb/pytest JUnit XML files and writes a
self-contained HTML page. Used by .github/workflows/hdl.yml, which uploads the
page as the `visual-test-results` artifact of every run.

Usage:
    python hdl/make_visual.py [--vcd PATH] [--hdl-xml PATH]
                              [--pytest-xml PATH] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# (vcd signal name, lane label, kind, colour)
SIGNALS = [
    ("clk", "clk", "bit", "#58a6ff"),
    ("rst", "rst", "bit", "#f85149"),
    ("hall_1", "hall sensor 1 (D9)", "bit", "#3fb950"),
    ("hall_2", "hall sensor 2 (D10)", "bit", "#3fb950"),
    ("rx_valid", "bt rx valid", "bit", "#39d353"),
    ("rx_data", "bt rx byte", "bus", "#39d353"),
    ("tx_valid", "bt tx valid", "bit", "#d2a8ff"),
    ("tx_data", "bt tx byte", "bus", "#d2a8ff"),
    ("led", "LED (D13)", "bit", "#ffab70"),
]

GESTURES = [
    ("LOW", "LOW", 1, True, True),
    ("HIGH", "LOW", 2, False, True),
    ("LOW", "HIGH", 3, True, False),
    ("HIGH", "HIGH", 4, False, False),
]


# ----------------------------------------------------------------- VCD parsing
def parse_vcd(path: Path) -> dict[str, list[tuple[int, int]]]:
    ids, changes = {}, {}
    t, in_defs = 0, True
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        if in_defs:
            if line.startswith("$var"):
                p = line.split()
                ids[p[3]] = p[4]
                changes[p[3]] = []
            elif line.startswith("$enddefinitions"):
                in_defs = False
            continue
        if line.startswith("#"):
            t = int(line[1:])
        elif line.startswith("$"):
            continue
        elif line[0] in "bB":
            v, sid = line[1:].split()
            try:
                val = int(v, 2)
            except ValueError:
                val = None
            changes[sid].append((t, val))
        elif len(line) > 1:
            changes[line[1:]].append((t, 1 if line[0] == "1" else 0))
    return {ids[s]: c for s, c in changes.items() if s in ids}


# -------------------------------------------------------------- JUnit parsing
def load_suite(path: Path) -> list[dict]:
    root = ET.parse(path).getroot()
    suites = root.findall("testsuite") if root.tag == "testsuites" else [root]
    out = []
    for ts in suites:
        for tc in ts.findall("testcase"):
            failed = tc.find("failure") is not None or tc.find("error") is not None
            skipped = tc.find("skipped") is not None
            props = {
                p.get("name"): p.get("value")
                for p in tc.findall("./properties/property")
            }
            out.append(
                {
                    "cls": tc.get("classname", ""),
                    "name": tc.get("name", ""),
                    "time": tc.get("time", "0"),
                    "status": "SKIP" if skipped else ("FAIL" if failed else "PASS"),
                    "sim_start": float(props.get("sim_time_start", "nan")),
                    "sim_stop": float(props.get("sim_time_stop", "nan")),
                }
            )
    return out


def build_bands(hdl_tests: list[dict]) -> list[tuple[float, float, str]]:
    bands = []
    for t in hdl_tests:
        if t["sim_start"] == t["sim_start"] and t["sim_stop"] == t["sim_stop"]:
            name = t["name"].removeprefix("test_")
            bands.append((t["sim_start"], t["sim_stop"], name))
    return bands


def lookup(changes, t_ps):
    val = changes[0][1] if changes else 0
    for tt, vv in changes:
        if tt > t_ps:
            break
        val = vv
    return val


def commit_meta() -> tuple[str, str]:
    sha = os.environ.get("GITHUB_SHA", "")
    if not sha:
        try:
            sha = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=REPO,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        except Exception:
            sha = "local"
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    url = (
        f"https://github.com/{repo}/actions/runs/{run_id}" if run_id and repo else ""
    )
    return sha[:7], url


# ----------------------------------------------------------------- HTML pieces
def suite_rows(tests: list[dict]) -> str:
    rows = []
    for t in tests:
        c = {"PASS": "#3fb950", "FAIL": "#f85149", "SKIP": "#8b949e"}[t["status"]]
        mark = {"PASS": "\u2713", "FAIL": "\u2717", "SKIP": "\u25cb"}[t["status"]]
        secs = float(t["time"] or 0)
        tm = f"{secs * 1000:.0f} ms" if secs < 1 else f"{secs:.2f} s"
        cls = t["cls"].rsplit(".", 1)[-1]
        rows.append(
            f'<div class="trow"><span class="mark" style="color:{c}">{mark}</span>'
            f'<span class="tname">{cls} :: {t["name"]}</span>'
            f'<span class="ttime">{tm}</span></div>'
        )
    return "\n".join(rows) or '<div class="trow">no results</div>'


def gesture_cards() -> str:
    cards = []
    for h1, h2, byte, k1, k2 in GESTURES:
        d1 = "#3fb950" if h1 == "HIGH" else "#484f58"
        d2 = "#3fb950" if h2 == "HIGH" else "#484f58"
        p1 = "on" if k1 else "off"
        p2 = "on" if k2 else "off"
        cards.append(
            f'<div class="gcard"><div class="dots">'
            f'<div class="dot" style="background:{d1}"><span>S1</span></div>'
            f'<div class="dot" style="background:{d2}"><span>S2</span></div></div>'
            f'<div class="byte">{byte}</div>'
            f'<div class="gvals">{h1} / {h2}</div>'
            f'<div class="pills"><span class="pill {p1}">key 1 {k1}</span>'
            f'<span class="pill {p2}">key 2 {k2}</span></div></div>'
        )
    return "".join(cards)


def circuit_svg() -> str:
    return """
<svg viewBox="0 0 1240 250" width="100%" style="max-height:270px">
 <defs><marker id="a" markerWidth="9" markerHeight="9" refX="8" refY="3" orient="auto">
  <path d="M0,0 L0,6 L8,3 z" fill="#8b949e"/></marker></defs>
 <rect x="14" y="34" width="230" height="180" rx="12" fill="#21262d" stroke="#30363d"/>
 <text x="129" y="58" text-anchor="middle" fill="#e6edf3" font-size="14" font-weight="700">Gesture glove</text>
 <circle cx="66" cy="110" r="17" fill="#d29922"/><text x="66" y="114" text-anchor="middle" font-size="10" fill="#0d1117" font-weight="700">mag</text>
 <text x="66" y="142" text-anchor="middle" fill="#8b949e" font-size="10.5">thumb</text>
 <rect x="120" y="92" width="102" height="30" rx="7" fill="#238636"/>
 <text x="171" y="111" text-anchor="middle" fill="#fff" font-size="11" font-weight="600">A3144 hall 1</text>
 <rect x="120" y="146" width="102" height="30" rx="7" fill="#238636"/>
 <text x="171" y="165" text-anchor="middle" fill="#fff" font-size="11" font-weight="600">A3144 hall 2</text>
 <text x="129" y="200" text-anchor="middle" fill="#8b949e" font-size="10.5">index / middle finger</text>
 <line x1="222" y1="107" x2="316" y2="92" stroke="#8b949e" stroke-width="1.6" marker-end="url(#a)"/>
 <line x1="222" y1="161" x2="316" y2="172" stroke="#8b949e" stroke-width="1.6" marker-end="url(#a)"/>
 <text x="268" y="88" fill="#8b949e" font-size="10.5">D9</text>
 <text x="268" y="192" fill="#8b949e" font-size="10.5">D10</text>
 <rect x="320" y="34" width="240" height="180" rx="12" fill="#161b22" stroke="#58a6ff"/>
 <text x="440" y="58" text-anchor="middle" fill="#58a6ff" font-size="14" font-weight="700">Arduino Nano</text>
 <text x="340" y="88" fill="#c9d1d9" font-size="11.5">loop(): read hall D9/D10</text>
 <text x="340" y="110" fill="#c9d1d9" font-size="11.5">on change -&gt; write byte 1-4</text>
 <text x="340" y="132" fill="#c9d1d9" font-size="11.5">read BT: 'y'/'n' -&gt; LED</text>
 <text x="340" y="162" fill="#8b949e" font-size="11">SoftwareSerial 9600 (D11/D12)</text>
 <circle cx="352" cy="190" r="9" fill="#ffab70"><animate attributeName="opacity" values="1;.25;1" dur="1.6s" repeatCount="indefinite"/></circle>
 <text x="370" y="194" fill="#ffab70" font-size="11.5" font-weight="600">LED D13</text>
 <line x1="560" y1="110" x2="646" y2="110" stroke="#8b949e" stroke-width="1.6" marker-end="url(#a)"/>
 <line x1="646" y1="140" x2="560" y2="140" stroke="#8b949e" stroke-width="1.6" marker-end="url(#a)"/>
 <text x="603" y="102" text-anchor="middle" fill="#8b949e" font-size="10.5">D11 TX</text>
 <text x="603" y="160" text-anchor="middle" fill="#8b949e" font-size="10.5">D12 RX</text>
 <rect x="650" y="70" width="150" height="90" rx="12" fill="#21262d" stroke="#30363d"/>
 <text x="725" y="104" text-anchor="middle" fill="#e6edf3" font-size="13.5" font-weight="700">HC-05</text>
 <text x="725" y="126" text-anchor="middle" fill="#8b949e" font-size="11">Bluetooth</text>
 <path d="M810 88 q18 26 0 52" stroke="#3fb950" fill="none" stroke-width="2" opacity=".85"/>
 <path d="M828 76 q28 40 0 80" stroke="#3fb950" fill="none" stroke-width="2" opacity=".5"/>
 <path d="M846 64 q38 52 0 108" stroke="#3fb950" fill="none" stroke-width="2" opacity=".25"/>
 <rect x="880" y="34" width="346" height="180" rx="12" fill="#161b22" stroke="#30363d"/>
 <text x="1053" y="58" text-anchor="middle" fill="#e6edf3" font-size="14" font-weight="700">Desktop app (Python + webcam)</text>
 <text x="900" y="88" fill="#c9d1d9" font-size="11.5">colour tracker -&gt; pointer follows your hand</text>
 <text x="900" y="112" fill="#c9d1d9" font-size="11.5">bytes 1-4 -&gt; key 1 / key 2 gestures</text>
 <text x="900" y="136" fill="#c9d1d9" font-size="11.5">Paint screen - LED screen - drag icons</text>
 <text x="900" y="166" fill="#3fb950" font-size="11.5">sends 'y' / 'n' when you toggle the LED</text>
</svg>"""


def wave_section(waves, bands, t_max, width):
    """Return (svg markup, JS data, JS signal list, height) or None."""
    if not waves:
        return None
    present = [(k, l, kind, c) for k, l, kind, c in SIGNALS if k in waves]
    if not present:
        return None
    x0, x1 = 138, 1606
    row = 34
    y0 = 62
    height = y0 + row * len(present) + 14

    def tx(t_ns):
        return x0 + (t_ns / t_max) * (x1 - x0)

    svg = []
    for i, (b0, b1, name) in enumerate(bands):
        x, w = tx(b0), tx(b1) - tx(b0)
        fill = "#161b22" if i % 2 == 0 else "#1c2129"
        svg.append(f'<rect x="{x:.1f}" y="0" width="{w:.1f}" height="{height}" fill="{fill}"/>')
        svg.append(
            f'<line x1="{x:.1f}" y1="0" x2="{x:.1f}" y2="{height}" '
            f'stroke="#30363d" stroke-dasharray="3,3"/>'
        )
        if w > 40:
            svg.append(
                f'<text x="{x + w / 2:.1f}" y="17" text-anchor="middle" class="band">'
                f"{i + 1}. {name}</text>"
            )
    svg.append(
        f'<line x1="{tx(t_max):.1f}" y1="0" x2="{tx(t_max):.1f}" y2="{height}" '
        f'stroke="#30363d" stroke-dasharray="3,3"/>'
    )

    svg.append(f'<line x1="{x0}" y1="44" x2="{x1}" y2="44" stroke="#30363d"/>')
    step = next(s for s in (10, 20, 50, 100, 200, 500, 1000) if t_max / s <= 16)
    t = 0
    while t <= t_max:
        x = tx(t)
        svg.append(f'<line x1="{x:.1f}" y1="40" x2="{x:.1f}" y2="48" stroke="#484f58"/>')
        svg.append(f'<text x="{x:.1f}" y="38" text-anchor="middle" class="axis">{t:g}</text>')
        t += step
    svg.append(f'<text x="{x1}" y="60" text-anchor="end" class="axis">time (ns)</text>')

    js_data, js_sigs = {}, []
    for r, (key, label, kind, color) in enumerate(present):
        y = y0 + r * row
        hi, lo = y + 9, y + row - 9
        svg.append(f'<text x="12" y="{y + row // 2 + 4}" class="sig" fill="{color}">{label}</text>')
        svg.append(f'<line x1="{x0}" y1="{y + row - 1}" x2="{x1}" y2="{y + row - 1}" stroke="#21262d"/>')
        ch = waves[key]
        js_data[key] = ch
        js_sigs.append((key, kind))
        if kind == "bit":
            pts = [(0, ch[0][1] if ch else 0)] + [(t, v) for t, v in ch if v is not None]
            lastv = pts[0][1]
            d = [f"M {tx(0):.1f} {hi if lastv else lo}"]
            for t_ps, v in pts[1:]:
                t_ns = t_ps / 1000.0
                d.append(f"L {tx(t_ns):.1f} {hi if lastv else lo}")
                d.append(f"L {tx(t_ns):.1f} {hi if v else lo}")
                lastv = v
            d.append(f"L {tx(t_max):.1f} {hi if lastv else lo}")
            sw = 4 if key in ("led", "tx_valid") else 2.4
            svg.append(
                f'<path d="{" ".join(d)}" fill="none" stroke="{color}" '
                f'stroke-width="{sw}" stroke-linejoin="round"/>'
            )
            if key == "tx_valid":
                for i2, (t_ps, v) in enumerate(ch):
                    if v == 1 and (i2 == 0 or ch[i2 - 1][1] == 0):
                        t_ns = t_ps / 1000.0
                        byte = lookup(waves.get("tx_data", []), t_ps)
                        svg.append(
                            f'<g><rect x="{tx(t_ns) - 13:.1f}" y="{y - 13}" width="26" '
                            f'height="16" rx="4" fill="#6e40c9"/>'
                            f'<text x="{tx(t_ns):.1f}" y="{y - 1}" text-anchor="middle" '
                            f'class="chip">{byte}</text></g>'
                        )
        else:
            pts = [(0, ch[0][1] if ch else 0)] + ch
            for i2 in range(len(pts)):
                t0 = pts[i2][0] / 1000.0
                t1 = pts[i2 + 1][0] / 1000.0 if i2 + 1 < len(pts) else t_max
                v = pts[i2][1]
                x, w = tx(t0), tx(t1) - tx(t0)
                if w < 1.2:
                    continue
                svg.append(
                    f'<rect x="{x:.1f}" y="{y + 8}" width="{w:.1f}" height="{row - 16}" '
                    f'rx="3" fill="{color}22" stroke="{color}66"/>'
                )
                if w > 34 and v is not None:
                    txt = chr(v) if key == "rx_data" and 32 <= v < 127 else str(v)
                    svg.append(
                        f'<text x="{x + w / 2:.1f}" y="{y + row / 2 + 4}" '
                        f'text-anchor="middle" class="bus">{txt}</text>'
                    )

    svg.append(
        f'<line id="cursor" x1="0" y1="0" x2="0" y2="{height}" stroke="#ffab70" '
        f'stroke-width="1.4" visibility="hidden"/>'
    )
    return "\n".join(svg), js_data, js_sigs, height, x0, x1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vcd", type=Path, default=REPO / "hdl" / "sim_build" / "waves.vcd")
    ap.add_argument("--hdl-xml", type=Path, default=REPO / "hdl" / "results.xml")
    ap.add_argument("--pytest-xml", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=REPO / "docs" / "test_results.html")
    args = ap.parse_args()

    waves = parse_vcd(args.vcd) if args.vcd.is_file() else {}
    hdl_tests = load_suite(args.hdl_xml) if args.hdl_xml.is_file() else []
    py_tests = load_suite(args.pytest_xml) if args.pytest_xml and args.pytest_xml.is_file() else []
    bands = build_bands(hdl_tests)

    all_tests = hdl_tests + py_tests
    total = sum(1 for t in all_tests if t["status"] != "SKIP")
    passed = sum(1 for t in all_tests if t["status"] == "PASS")
    sha, run_url = commit_meta()

    # t_max: prefer the cocotb sim timeline, else the last VCD event
    t_max = max([b[1] for b in bands], default=0)
    if not t_max and waves:
        t_max = max(t for ch in waves.values() for t, _ in ch) / 1000.0
    if not t_max:
        t_max = 1.0
    t_max = round(t_max, 3)

    wave = wave_section(waves, bands, t_max, 0) if waves else None
    if wave:
        svg_markup, js_data, js_sigs, height, x0, x1 = wave
        wave_html = f"""
<div class="wavebox" id="wavebox">
<svg id="wsvg" width="1620" height="{height}" viewBox="0 0 1620 {height}">
{svg_markup}
</svg>
<div id="tip"></div>
</div>
<div class="legend">
 <span><b>hover the waveform</b> for signal values at any instant</span>
 <span style="color:#ffab70">&#9632; LED (D13)</span>
 <span style="color:#d2a8ff">&#9632; Bluetooth tx bytes (annotated 1-4)</span>
 <span style="color:#3fb950">&#9632; Bluetooth rx ('y'/'n'/'x')</span>
</div>"""
    else:
        js_data, js_sigs, x0, x1 = {}, [], 0, 0
        wave_html = '<div class="card">waveform unavailable (no VCD dump found)</div>'

    if py_tests:
        cards = f"""<div class="grid">
 <div class="card"><h2>HDL &mdash; cocotb + Icarus ({len(hdl_tests)})</h2>{suite_rows(hdl_tests)}</div>
 <div class="card"><h2>Python &mdash; pytest ({len(py_tests)})</h2>{suite_rows(py_tests)}</div>
</div>"""
    else:
        cards = f"""<div class="grid one">
 <div class="card"><h2>HDL &mdash; cocotb + Icarus ({len(hdl_tests)})</h2>{suite_rows(hdl_tests)}</div>
</div>"""

    run_html = (
        f' &middot; <a href="{run_url}">workflow run</a>' if run_url else ""
    )
    wave_heading = (
        f"<h2>Simulated waveform &mdash; {len(hdl_tests)} cocotb tests, "
        f"0&ndash;{t_max:g} ns</h2>"
        if wave
        else "<h2>Simulated waveform</h2>"
    )

    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>gesture_controlled-UI - visual results</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:#0d1117;color:#e6edf3;font-family:'Segoe UI',Roboto,sans-serif}}
.wrap{{max-width:1680px;margin:0 auto;padding:28px 24px 60px}}
h1{{font-size:24px;margin:0 0 4px}} h2{{font-size:15px;margin:0 0 12px;color:#e6edf3;
 text-transform:uppercase;letter-spacing:.08em}}
.sub{{color:#8b949e;font-size:13px;margin-bottom:18px}} .sub a{{color:#58a6ff}}
.badge{{display:inline-block;background:#238636;color:#fff;padding:7px 16px;border-radius:20px;
 font-weight:700;font-size:15px;margin-bottom:26px}}
.badge.bad{{background:#cf222e}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:26px}}
.grid.one{{grid-template-columns:1fr}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:16px}}
.gcards{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:26px}}
.gcard{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px;text-align:center}}
.dots{{display:flex;gap:14px;justify-content:center;margin-bottom:8px}}
.dot{{width:44px;height:44px;border-radius:50%;display:flex;align-items:center;justify-content:center;
 font-size:11px;color:#0d1117;font-weight:700;box-shadow:0 0 10px #0006 inset}}
.byte{{font-size:44px;font-weight:800;color:#58a6ff;line-height:1}}
.gvals{{color:#8b949e;font-size:12px;margin:4px 0 8px}}
.pills{{display:flex;gap:6px;justify-content:center}}
.pill{{font-size:11px;padding:3px 9px;border-radius:10px;background:#21262d;color:#8b949e}}
.pill.on{{background:#238636;color:#fff}}
.trow{{display:flex;align-items:center;gap:9px;padding:5px 2px;border-bottom:1px solid #21262d;
 font-size:12.5px}} .trow:last-child{{border-bottom:none}}
.mark{{width:14px;font-weight:700}} .tname{{flex:1;color:#c9d1d9;overflow:hidden;
 text-overflow:ellipsis;white-space:nowrap}} .ttime{{color:#8b949e;font-size:11px}}
.wavebox{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px;overflow-x:auto;
 position:relative;margin-bottom:14px}} .wavebox svg{{display:block}}
.band{{fill:#8b949e;font-size:10.5px;font-weight:600}}
.axis{{fill:#6e7681;font-size:9.5px}} .sig{{font-size:11.5px;font-weight:600}}
.bus{{fill:#e6edf3;font-size:11px;font-weight:600}} .chip{{fill:#fff;font-size:10.5px;font-weight:700}}
#tip{{position:absolute;background:#0d1117f2;border:1px solid #f85149;border-radius:8px;padding:8px 11px;
 font-size:11.5px;pointer-events:none;display:none;z-index:9;white-space:nowrap;line-height:1.55;
 box-shadow:0 6px 18px #000a}} #tip b{{color:#ffab70}}
.circuit{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px;margin-bottom:26px}}
.legend{{display:flex;gap:16px;flex-wrap:wrap;font-size:11.5px;color:#8b949e;margin:0 2px 26px}}
.foot{{color:#484f58;font-size:11.5px;margin-top:26px}}
</style></head><body><div class="wrap">

<h1>gesture_controlled-UI &mdash; visual test results</h1>
<div class="sub">commit {sha} &middot; generated {datetime.now():%Y-%m-%d %H:%M} UTC
{run_html} &middot; cocotb 2.1.0 + Icarus Verilog (VCD dump)</div>
<div class="badge{' bad' if passed != total else ''}">{passed}/{total} TESTS PASSING</div>

<h2>Gesture gloves &rarr; circuit (Circuit Digest BOM)</h2>
<div class="circuit">{circuit_svg()}</div>

<h2>Key state mapping &mdash; what each gesture sends</h2>
<div class="gcards">{gesture_cards()}</div>

{wave_heading}
{wave_html}

<h2 style="margin-top:30px">Test detail</h2>
{cards}

<div class="foot">generated by hdl/make_visual.py from the Icarus VCD dump
and JUnit XML results of this run</div>
</div>

<script>
const DATA = {json.dumps(js_data)};
const T_MAX = {t_max};
const X0 = {x0}, X1 = {x1};
const SIGS = {json.dumps(js_sigs)};
function lookupCh(ch, t) {{
  let v = ch.length ? ch[0][1] : 0;
  for (const [tt, vv] of ch) {{ if (tt / 1000 > t) break; v = vv; }}
  return v;
}}
const box = document.getElementById('wavebox');
const svgEl = document.getElementById('wsvg');
if (svgEl) {{
  const tip = document.getElementById('tip');
  const cursor = document.getElementById('cursor');
  const FMT = (k, v) => {{
    if (k === 'rx_data' || k === 'tx_data')
      return (v >= 32 && v < 127 ? "'" + String.fromCharCode(v) + "' " : '') +
             v + ' (0x' + Number(v).toString(16) + ')';
    return v;
  }};
  svgEl.addEventListener('mousemove', (e) => {{
    const pt = svgEl.getBoundingClientRect();
    const sx = (e.clientX - pt.left) * (1620 / pt.width);
    if (sx < X0 || sx > X1) {{ tip.style.display = 'none'; cursor.setAttribute('visibility', 'hidden'); return; }}
    const t = (sx - X0) / (X1 - X0) * T_MAX;
    cursor.setAttribute('x1', sx); cursor.setAttribute('x2', sx);
    cursor.setAttribute('visibility', 'visible');
    let rows = '<b>t = ' + t.toFixed(1) + ' ns</b>';
    for (const [k, kind] of SIGS) {{
      const v = lookupCh(DATA[k], t * 1000);
      rows += '<br>' + k + ': ' + (kind === 'bus' ? FMT(k, v) : (v ? '1 / HIGH' : '0 / LOW'));
    }}
    tip.innerHTML = rows;
    tip.style.display = 'block';
    const bx = box.getBoundingClientRect();
    let lx = e.clientX - bx.left + box.scrollLeft + 18;
    if (lx + 250 > box.scrollLeft + box.clientWidth) lx -= 285;
    tip.style.left = lx + 'px';
    tip.style.top = (e.clientY - bx.top + 14) + 'px';
  }});
  svgEl.addEventListener('mouseleave', () => {{
    tip.style.display = 'none'; cursor.setAttribute('visibility', 'hidden');
  }});
}}
</script>
</body></html>"""

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")
    print(f"wrote {args.out} ({passed}/{total} tests, {len(waves)} signals)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
