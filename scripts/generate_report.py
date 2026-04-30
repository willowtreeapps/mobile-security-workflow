#!/usr/bin/env python3
"""
Mobile DAST PDF Report Generator
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Usage:
    python3.12 generate_report.py <findings.json> <output.pdf>

One-time setup:
    pip install weasyprint jinja2 --break-system-packages

The findings.json schema is documented in:
    /Users/cassio.junior/Desktop/mobile-dast/scripts/findings_schema.json
"""

import sys
import json
import math
import base64
import os
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Dependency check ─────────────────────────────────────────────────────────

try:
    from jinja2 import Environment, BaseLoader
    from weasyprint import HTML, CSS
except ImportError:
    print("[-] Missing dependencies. Run:")
    print("    pip install weasyprint jinja2 --break-system-packages")
    sys.exit(1)

# ── Asset paths ───────────────────────────────────────────────────────────────

SCC_ASSETS   = Path(
    "/Users/cassio.junior/Documents/SourceCode/SCC/scc"
    "/services/frontend/src/assets/report"
)
LOCAL_ASSETS = Path("/Users/cassio.junior/Desktop/mobile-dast/assets")
# Use local assets/ first (always accessible); fall back to SCC path
DEFAULT_ASSETS = LOCAL_ASSETS if LOCAL_ASSETS.exists() else SCC_ASSETS

# ── Design tokens (mirrors theme.ts) ─────────────────────────────────────────

SEVERITY_ORDER = ["Critical", "High", "Medium", "Low", "Info"]

SEVERITY_COLOR = {
    "Critical": "#B91C1C",
    "High":     "#EA580C",
    "Medium":   "#C28300",
    "Low":      "#2F6FEB",
    "Info":     "#6B7280",
}

SEVERITY_BG = {
    "Critical": "#FEE2E2",
    "High":     "#FFEDD5",
    "Medium":   "#FEF3C7",
    "Low":      "#DBEAFE",
    "Info":     "#F3F4F6",
}

SEVERITY_RUBRIC = [
    {
        "s": "Critical",
        "d": ("Direct compromise of the device or backend — e.g. remote code execution, "
              "plaintext credential storage in a banking app, or account takeover without "
              "user interaction."),
    },
    {
        "s": "High",
        "d": ("Sensitive data exposure, authentication bypass on a non-trivial flow, or an "
              "exported component that performs privileged actions."),
    },
    {
        "s": "Medium",
        "d": ("Weak cryptography without an immediate exploit path, missing certificate "
              "pinning on a non-sensitive endpoint, or log leakage of moderately sensitive "
              "data."),
    },
    {
        "s": "Low",
        "d": ("Defense-in-depth gap — e.g. no root detection on a non-sensitive app — or "
              "a minor information disclosure."),
    },
    {
        "s": "Info",
        "d": ("Best-practice deviation with no current security risk. Informational findings "
              "highlight improvement opportunities for future hardening."),
    },
]

MASVS_DESCRIPTIONS = {
    "MASVS-STORAGE":    "Sensitive data stored locally — shared preferences, SQLite databases, files, and the Android Keystore.",
    "MASVS-CRYPTO":     "Cryptographic primitives: algorithm strength, key management, randomness sources, and correct use of the Android Keystore.",
    "MASVS-AUTH":       "Authentication and session management — token storage, session expiry, brute-force protection, and biometric binding.",
    "MASVS-NETWORK":    "Network communication security — TLS configuration, certificate pinning, and cleartext traffic.",
    "MASVS-PLATFORM":   "Interaction with Android platform — exported components, deep links, WebView configuration, and content providers.",
    "MASVS-CODE":       "Code quality and binary protections — debug flags, stack canaries, RELRO, and dynamic code loading.",
    "MASVS-RESILIENCE": "Anti-reverse-engineering controls — root detection, debugger detection, emulator detection, and anti-tampering.",
    "MASVS-PRIVACY":    "Privacy controls — excessive permissions, pre-consent analytics collection, and PII in logs or analytics.",
}

# ── Helper functions ──────────────────────────────────────────────────────────

def normalize_severity(s: str) -> str:
    s = (s or "").strip().lower()
    for level in SEVERITY_ORDER:
        if s == level.lower():
            return level
    return "Info"


def map_status(s: str) -> str:
    s = (s or "").strip().lower()
    mapping = {
        "open":           "Pending",
        "":               "Pending",
        "resolved":       "Fixed",
        "fixed":          "Fixed",
        "ignored":        "Ignored",
        "false positive": "False Positive",
    }
    return mapping.get(s, (s or "Pending").capitalize())


def format_date(iso: Optional[str]) -> str:
    if not iso:
        return "—"
    try:
        return datetime.fromisoformat(iso).strftime("%m/%d/%Y")
    except Exception:
        return str(iso)


def format_long_date(iso: Optional[str]) -> str:
    if not iso:
        return "—"
    try:
        return datetime.fromisoformat(iso).strftime("%B %d, %Y")
    except Exception:
        return str(iso)


def count_by_severity(findings: list) -> dict:
    counts = {s: 0 for s in SEVERITY_ORDER}
    for f in findings:
        counts[normalize_severity(f.get("severity", ""))] += 1
    return counts


def severity_rank(s: str) -> int:
    try:
        return SEVERITY_ORDER.index(normalize_severity(s))
    except ValueError:
        return len(SEVERITY_ORDER)


def img_to_data_uri(path: Path) -> Optional[str]:
    if not path or not path.exists():
        return None
    mime = {
        ".png":  "image/png",
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg":  "image/svg+xml",
    }.get(path.suffix.lower(), "image/png")
    data = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{data}"


def evidence_screenshot_uri(ev: dict) -> Optional[str]:
    if ev.get("screenshotBase64") and ev.get("screenshotMimeType"):
        return f"data:{ev['screenshotMimeType']};base64,{ev['screenshotBase64']}"
    p = ev.get("screenshotPath")
    if p:
        return img_to_data_uri(Path(p))
    return None


def auto_attach_screenshots(findings: list, screenshots_dir: Path) -> None:
    """
    Scan *screenshots_dir* for image files and attach them to findings.

    Matching rules (applied in order):
    1. Filename starts with the finding id (case-insensitive, dashes/underscores
       normalised).  Example: ``F01_login_success.png`` → finding id ``F-01``.
    2. Filename contains the finding id anywhere.
    3. Any remaining images (not matched to a specific finding) are appended as
       an extra evidence item on the *first* finding, so they are at least
       visible in the report.

    Only images whose ``screenshotPath`` / ``screenshotBase64`` are not already
    set in an existing evidence item are attached (no duplicates).
    """
    if not screenshots_dir or not screenshots_dir.is_dir():
        return

    IMG_EXTS = {".png", ".jpg", ".jpeg"}

    def _norm_id(s: str) -> str:
        return s.lower().replace("-", "").replace("_", "").replace(" ", "")

    all_images = sorted(
        p for p in screenshots_dir.iterdir()
        if p.is_file() and p.suffix.lower() in IMG_EXTS
    )
    if not all_images:
        return

    # Collect paths already referenced so we don't double-attach.
    referenced: set = set()
    for f in findings:
        for ev in f.get("evidence", []):
            if ev.get("screenshotPath"):
                referenced.add(str(Path(ev["screenshotPath"]).resolve()))

    # Build a normalised-id → finding index map.
    id_map: dict = {}
    for idx, f in enumerate(findings):
        fid = f.get("id", "")
        if fid:
            id_map[_norm_id(fid)] = idx

    unmatched: list = []

    for img in all_images:
        img_str = str(img.resolve())
        if img_str in referenced:
            continue  # already in the JSON

        stem_norm = _norm_id(img.stem)
        matched_idx = None

        # Rule 1: stem starts with normalised finding id
        for nid, idx in id_map.items():
            if stem_norm.startswith(nid):
                matched_idx = idx
                break

        # Rule 2: stem contains finding id anywhere
        if matched_idx is None:
            for nid, idx in id_map.items():
                if nid in stem_norm:
                    matched_idx = idx
                    break

        ev_item = {"screenshotPath": str(img), "title": img.stem}

        if matched_idx is not None:
            findings[matched_idx].setdefault("evidence", []).append(ev_item)
            referenced.add(img_str)
        else:
            unmatched.append(ev_item)

    # Rule 3: attach unmatched images to the first finding (if any exist).
    if unmatched and findings:
        findings[0].setdefault("evidence", []).extend(unmatched)
        print(f"[!] {len(unmatched)} screenshot(s) could not be matched to a "
              "specific finding by ID — attached to the first finding.")

# ── SVG donut chart ───────────────────────────────────────────────────────────

def _polar(cx: float, cy: float, r: float, deg: float):
    rad = math.radians(deg - 90)
    return cx + r * math.cos(rad), cy + r * math.sin(rad)


def build_donut_svg(counts: dict, size: int = 160) -> str:
    cx = cy = size / 2
    R, r = 70, 42
    total = sum(counts.values())

    if total == 0:
        d = (f"M {cx} {cy - R} A {R} {R} 0 1 1 {cx - 0.01:.3f} {cy - R} "
             f"L {cx - 0.01:.3f} {cy - r} A {r} {r} 0 1 0 {cx} {cy - r} Z")
        return (f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
                f'<path d="{d}" fill="#EAEAEA"/></svg>')

    paths = []
    start = 0.0
    for label in SEVERITY_ORDER:
        count = counts.get(label, 0)
        if count == 0:
            continue
        sweep = count / total * 360
        end = start + sweep
        eff_end = start + 359.999 if sweep >= 359.999 else end
        ox1, oy1 = _polar(cx, cy, R, start)
        ox2, oy2 = _polar(cx, cy, R, eff_end)
        ix2, iy2 = _polar(cx, cy, r, eff_end)
        ix1, iy1 = _polar(cx, cy, r, start)
        la = 1 if sweep > 180 else 0
        d = (f"M {ox1:.3f} {oy1:.3f} A {R} {R} 0 {la} 1 {ox2:.3f} {oy2:.3f} "
             f"L {ix2:.3f} {iy2:.3f} A {r} {r} 0 {la} 0 {ix1:.3f} {iy1:.3f} Z")
        paths.append(f'<path d="{d}" fill="{SEVERITY_COLOR[label]}"/>')
        start = end

    inner = "".join(paths)
    return f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">{inner}</svg>'

# ── Jinja2 template ───────────────────────────────────────────────────────────

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
/* ── Reset ──────────────────────────────────────────────────────────────── */
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: Helvetica, Arial, sans-serif;
    font-size: 10pt;
    color: #202020;
    line-height: 1.5;
}

/* ── Page layout ─────────────────────────────────────────────────────────── */
@page {
    size: A4;
    margin: 52pt 56pt 60pt 56pt;
    @bottom-left { content: element(page-footer); margin-bottom: 8pt; }
}
/* Cover page: no margins, no footer */
@page :first { margin: 0; }

/* ── Running footer ──────────────────────────────────────────────────────── */
#running-footer {
    position: running(page-footer);
    width: 483pt;
    border-top: 0.5pt solid #202020;
    padding-top: 6pt;
    font-size: 8pt;
}
.footer-inner {
    position: relative;
    width: 483pt;
    height: 14pt;
}
.footer-brand {
    position: absolute;
    left: 0;
    top: 0;
    display: inline-block;
}
.footer-pagenum {
    position: absolute;
    right: 0;
    top: 0;
}
.footer-divider {
    display: inline-block;
    width: 0.5pt; height: 10pt;
    background: #202020;
    margin: 0 4pt;
    vertical-align: middle;
}

.footer-pagenum::after { content: counter(page); }

/* ── Page breaks ─────────────────────────────────────────────────────────── */
.page-break { page-break-before: always; }
.no-break   { page-break-inside: avoid; }

/* ── Cover page ──────────────────────────────────────────────────────────── */
.cover { width: 100%; display: flex; flex-direction: column; height: 100vh; }
.cover-top {
    flex: 1;
    padding: 52pt 56pt 20pt 56pt;
    display: flex;
    flex-direction: column;
}
.cover-logo   { width: 130pt; display: block; }
.cover-spacer { height: 72pt; }
.cover-title {
    font-size: 36pt;
    font-weight: bold;
    color: #202020;
    line-height: 1.18;
    margin-bottom: 12pt;
}
.cover-subtitle {
    font-size: 22pt;
    font-weight: bold;
    color: #66CC00;
}
.cover-meta { font-size: 9pt; color: #555555; margin-top: 18pt; }
.cover-hero { height: 420pt; overflow: hidden; }
.cover-hero img {
    width: 100%; height: 100%;
    object-fit: cover;
    object-position: right top;
    display: block;
}
.cover-hero-fallback {
    height: 420pt;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
}

/* ── Typography ──────────────────────────────────────────────────────────── */
h1 { font-size: 28pt; font-weight: bold; color: #202020; margin-bottom: 20pt; }
h2 { font-size: 18pt; font-weight: bold; color: #202020; margin-top: 24pt; margin-bottom: 10pt; }
h3 { font-size: 13pt; font-weight: bold; color: #202020; margin-top: 16pt; margin-bottom: 6pt; }
p  { margin-bottom: 10pt; text-align: justify; }
a  { color: #4B286D; }

/* ── Table of contents ───────────────────────────────────────────────────── */
.toc-row {
    display: flex;
    justify-content: space-between;
    border-bottom: 0.5pt dotted #D8D8D8;
    padding: 4pt 0;
}
.toc-row.indent {
    padding-left: 16pt;
    color: #555555;
    border-bottom-color: #EAEAEA;
    font-size: 9.5pt;
    padding-top: 3pt;
    padding-bottom: 3pt;
}

/* ── Tables ──────────────────────────────────────────────────────────────── */
table {
    width: 100%;
    border-collapse: collapse;
    border-top: 1pt solid #D8D8D8;
    margin-top: 8pt;
    font-size: 10pt;
}
thead tr { border-bottom: 1pt solid #D8D8D8; }
th {
    text-align: left;
    padding: 8pt 10pt;
    font-size: 9pt;
    font-weight: bold;
    color: #555555;
}
td {
    padding: 8pt 10pt;
    border-bottom: 1pt solid #EAEAEA;
    vertical-align: top;
}

/* ── Severity & status badges ────────────────────────────────────────────── */
.badge {
    display: inline-block;
    padding: 2pt 10pt;
    border-radius: 10pt;
    font-size: 9pt;
    font-weight: bold;
    line-height: 1.4;
    white-space: nowrap;
}
.badge-critical      { background:#FEE2E2; color:#B91C1C; }
.badge-high          { background:#FFEDD5; color:#EA580C; }
.badge-medium        { background:#FEF3C7; color:#C28300; }
.badge-low           { background:#DBEAFE; color:#2F6FEB; }
.badge-info          { background:#F3F4F6; color:#6B7280; }
.badge-pending       { background:#FEE2E2; color:#B91C1C; }
.badge-fixed         { background:#DCFCE7; color:#15803D; }
.badge-ignored       { background:#F3F4F6; color:#6B7280; }
.badge-false.badge-positive { background:#F3F4F6; color:#6B7280; }
.badge-confirmed     { background:#DCFCE7; color:#15803D; }
.badge-likely        { background:#DBEAFE; color:#1D4ED8; }

/* ── Donut chart ─────────────────────────────────────────────────────────── */
.donut-wrap { display: flex; align-items: center; margin: 8pt 0 16pt 0; }
.donut-legend { margin-left: 24pt; flex: 1; }
.legend-row { display: flex; align-items: center; margin-bottom: 5pt; font-size: 10pt; }
.legend-swatch { width: 10pt; height: 10pt; border-radius: 2pt; margin-right: 8pt; flex-shrink: 0; }
.legend-label  { flex: 1; }
.legend-count  { color: #555555; }

/* ── Finding detail card ─────────────────────────────────────────────────── */
.detail-table { width: 100%; border-top: 1pt solid #D8D8D8; margin-top: 8pt; }
.detail-row   { display: flex; border-bottom: 1pt solid #EAEAEA; }
.detail-label {
    width: 130pt;
    flex-shrink: 0;
    padding: 12pt 10pt;
    font-size: 9pt;
    font-weight: bold;
    color: #555555;
}
.detail-value { flex: 1; padding: 12pt 10pt; font-size: 10pt; line-height: 1.55; }
.detail-value .sub { font-size: 9pt; color: #555555; margin-top: 2pt; }

/* ── Code blocks ─────────────────────────────────────────────────────────── */
.code-label {
    font-size: 9pt;
    font-weight: bold;
    color: #555555;
    margin-top: 8pt;
    margin-bottom: 2pt;
}
.code-block {
    background: #F4F4F6;
    border-radius: 3pt;
    padding: 6pt 8pt;
    margin-bottom: 6pt;
    font-family: "Courier New", Courier, monospace;
    font-size: 7.5pt;
    color: #1A1A2E;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-all;
}

/* ── Evidence ────────────────────────────────────────────────────────────── */
.evidence-block    { margin-bottom: 14pt; }
.evidence-title    { font-weight: bold; margin-bottom: 4pt; font-size: 10pt; }
.evidence-img {
    width: 100%;
    max-height: 260pt;
    object-fit: contain;
    border-radius: 3pt;
    margin-top: 4pt;
    margin-bottom: 8pt;
    display: block;
}

/* ── Utility ─────────────────────────────────────────────────────────────── */
.muted { color: #555555; }
.bold  { font-weight: bold; }
.small { font-size: 9pt; }
.mono  { font-family: "Courier New", Courier, monospace; font-size: 9pt; }
</style>
</head>
<body>

{# Running footer — appears on every page except the cover (@page :first) #}
<div id="running-footer">
    <div class="footer-inner">
        <div class="footer-brand">
            {% if logo_black_uri %}
            <img src="{{ logo_black_uri }}" style="height:12pt; vertical-align:middle;">
            <span class="footer-divider"></span>
            {% endif %}
            <span>Confidential</span>
        </div>
        <div class="footer-pagenum"></div>
    </div>
</div>

{# ═══ COVER PAGE ══════════════════════════════════════════════════════════ #}
<div class="cover">
    <div class="cover-top">
        {% if logo_color_uri %}
        <img class="cover-logo" src="{{ logo_color_uri }}">
        {% endif %}
        <div class="cover-spacer"></div>
        <div>
            <div class="cover-title">Mobile Application<br>Security Assessment</div>
            <div class="cover-subtitle">{{ target.name }}</div>
            <div class="cover-meta">
                {{ target.packageName }}&nbsp;&nbsp;•&nbsp;&nbsp;{{ start_long }} — {{ finish_long }}
            </div>
        </div>
    </div>
    {% if hero_uri %}
    <div class="cover-hero"><img src="{{ hero_uri }}" alt=""></div>
    {% else %}
    <div class="cover-hero-fallback"></div>
    {% endif %}
</div>

{# ═══ TABLE OF CONTENTS ════════════════════════════════════════════════════ #}
<div class="page-break">
<h1>Table of Contents</h1>

<div class="toc-row"><span>Executive Summary</span><span>2</span></div>
<div class="toc-row indent"><span>Scope</span><span>2</span></div>
<div class="toc-row indent"><span>Engagement Summary</span><span>2</span></div>
<div class="toc-row indent"><span>Summary of Findings</span><span>3</span></div>
<div class="toc-row indent"><span>Vulnerabilities Prioritization for Remediation</span><span>3</span></div>
<div class="toc-row"><span>Discovered Vulnerabilities Details</span><span>4</span></div>
{% for f in sorted_findings %}
<div class="toc-row indent">
    <span>{{ loop.index }}. {{ f.title }}</span>
    <span>{{ 3 + loop.index }}</span>
</div>
{% endfor %}
{% set appendix_page = 4 + sorted_findings | length %}
<div class="toc-row"><span>Appendices</span><span>{{ appendix_page }}</span></div>
<div class="toc-row indent"><span>Appendix A — Defining Severity</span><span>{{ appendix_page }}</span></div>
<div class="toc-row indent"><span>Appendix B — MASVS Category Reference</span><span>{{ appendix_page }}</span></div>
</div>

{# ═══ EXECUTIVE SUMMARY ════════════════════════════════════════════════════ #}
<div class="page-break">
<h1>Executive Summary</h1>
<p>
This document presents the results of a Mobile Application Security Assessment for
<strong>{{ target.name }}</strong>. The engagement aimed to identify security vulnerabilities
that could negatively impact the application, the data it handles, and consequently, the
business. The {{ team_name }} systematically applied OWASP MASTG-aligned tests to assess the
application's resilience against real-life attack scenarios.
</p>
<p>
Our security analysis combined static reverse-engineering (jadx decompilation), dynamic
instrumentation (Frida hooking), UI-driven functional testing, and network
traffic interception (mitmproxy). Risk severity ratings follow the OWASP MASVS v2 framework.
Severity classifications reflect each issue's potential impact on business operations,
particularly regarding data exposure, authentication bypass, and privacy violations.
</p>

<h2>Scope</h2>
<p>
The mobile application <strong>{{ target.name }}</strong> underwent a security-focused
assessment targeting the
<strong>{{ target.get("functionality") or "whole-app" }}</strong> functionality.
The scope of the evaluation included:
</p>
<table>
    <thead>
        <tr>
            <th>Application</th>
            <th>Package</th>
            <th>Version</th>
            <th>Android</th>
            <th>Environment</th>
        </tr>
    </thead>
    <tbody>
        <tr class="no-break">
            <td>{{ target.name }}</td>
            <td class="mono">{{ target.packageName }}</td>
            <td>{{ target.versionName }}{% if target.get("versionCode") %} ({{ target.versionCode }}){% endif %}</td>
            <td>{{ (target.get("androidVersion") or "—").replace(" — Genymotion", "").replace(" - Genymotion", "") }}</td>
            <td>{{ environment }}</td>
        </tr>
    </tbody>
</table>

<h2>Engagement Summary</h2>
<p>
The security assessment was conducted from <strong>{{ start_date }}</strong> to
<strong>{{ finish_date }}</strong>, culminating in this final report.
</p>
<p>
Testing activities combined automated static analysis with comprehensive manual dynamic
testing on an Android emulator. During the engagement,
<strong>{{ total }} finding{% if total != 1 %}s{% endif %}</strong> threatening the
confidentiality, integrity, or availability of {{ target.name }}'s information
{% if total == 1 %}was{% else %}were{% endif %} identified
{% if total > 0 %}({{ counts_line }}){% endif %}.
</p>

</div>

{# ═══ SUMMARY OF FINDINGS ══════════════════════════════════════════════════ #}
<div class="page-break">
<h1>Summary of Findings</h1>
<p>
The findings were systematically categorized based on their severity levels, determined
through a combination of in-house expertise and OWASP MASVS / MASTG rating methodologies.
For further details, please refer to Appendix A.
</p>
<p>
We identified {{ counts.Critical }} finding{% if counts.Critical != 1 %}s{% endif %}
classified as critical-risk, {{ counts.High }} as high-risk,
{{ counts.Medium }} as medium-risk, {{ counts.Low }} as low-risk, and
{{ counts.Info }} as informational.
</p>

<h3>Vulnerabilities by Severity Level</h3>
<div class="donut-wrap">
    {{ donut_svg }}
    <div class="donut-legend">
        {% for label in severity_order %}
        <div class="legend-row">
            <div class="legend-swatch" style="background:{{ severity_color[label] }};"></div>
            <span class="legend-label">{{ label }}</span>
            <span class="legend-count">
                {{ counts[label] }}&nbsp;&nbsp;•&nbsp;&nbsp;{% if total > 0 %}{{ "%.1f"|format(counts[label] / total * 100) }}%{% else %}0.0%{% endif %}
            </span>
        </div>
        {% endfor %}
    </div>
</div>

<h2>Vulnerabilities Prioritization for Remediation</h2>
<p>
The following table provides a comprehensive prioritization of the vulnerabilities, ordered
by criticality and recommended remediation sequence.
</p>

{% if total == 0 %}
<p class="muted">No findings were identified during this engagement.</p>
{% else %}
<table>
    <thead>
        <tr>
            <th style="width:36pt;">Priority</th>
            <th style="width:64pt;">Severity</th>
            <th>Vulnerability</th>
            <th style="width:110pt;">MASVS</th>
            <th style="width:60pt;">Status</th>
        </tr>
    </thead>
    <tbody>
        {% for f in sorted_findings %}
        <tr class="no-break">
            <td>{{ loop.index }}</td>
            <td><span class="badge badge-{{ f.severity | lower }}">{{ f.severity }}</span></td>
            <td>{{ f.title }}</td>
            <td class="muted small">{{ f.masvs }}</td>
            <td><span class="badge badge-{{ f.status_label | lower | replace(" ","") }}">{{ f.status_label }}</span></td>
        </tr>
        {% endfor %}
    </tbody>
</table>
{% endif %}
</div>

{# ═══ FINDING DETAIL PAGES ════════════════════════════════════════════════= #}
{% for f in sorted_findings %}
<div class="page-break">
<h2>{{ loop.index }}. {{ f.title }}</h2>
<div class="detail-table">

    <div class="detail-row no-break">
        <div class="detail-label">Severity</div>
        <div class="detail-value">
            <span class="badge badge-{{ f.severity | lower }}">{{ f.severity }}</span>
        </div>
    </div>

    <div class="detail-row no-break">
        <div class="detail-label">Confidence</div>
        <div class="detail-value">
            <span class="badge badge-{{ (f.confidence or "likely") | lower }}">{{ f.confidence or "Likely" }}</span>
        </div>
    </div>

    <div class="detail-row no-break">
        <div class="detail-label">MASVS</div>
        <div class="detail-value">
            <div>{{ f.masvs }}</div>
            {% if f.get("mastgTest") %}<div class="sub">{{ f.mastgTest }}</div>{% endif %}
        </div>
    </div>

    {% if f.get("cwe") %}
    <div class="detail-row no-break">
        <div class="detail-label">CWE</div>
        <div class="detail-value">{{ f.cwe }}</div>
    </div>
    {% endif %}

    <div class="detail-row">
        <div class="detail-label">Description</div>
        <div class="detail-value">{{ f.get("description") or "—" }}</div>
    </div>

    {% if f.get("evidence") %}
    <div class="detail-row">
        <div class="detail-label">Evidence</div>
        <div class="detail-value">
            {% for ev in f.evidence %}
            <div class="evidence-block">
                {% if ev.get("title") %}
                <div class="evidence-title">{{ ev.title }}</div>
                {% endif %}

                {% if ev.get("command") %}
                <div class="code-label">Command</div>
                <div class="code-block">{{ ev.command }}</div>
                {% endif %}

                {% if ev.get("output") %}
                <div class="code-label">Output</div>
                <div class="code-block">{{ ev.output }}</div>
                {% endif %}

                {% if ev.get("fridaLogExcerpt") %}
                <div class="code-label">Frida hook log</div>
                <div class="code-block">{{ ev.fridaLogExcerpt }}</div>
                {% endif %}

                {% if ev.get("jadxSource") %}
                <div class="code-label">Source (jadx)</div>
                <div class="code-block">{{ ev.jadxSource }}</div>
                {% endif %}

                {% if ev.get("networkSample") %}
                <div class="code-label">Network capture</div>
                <div class="code-block">{{ ev.networkSample }}</div>
                {% endif %}

                {% if ev.get("screenshot_uri") %}
                <img class="evidence-img" src="{{ ev.screenshot_uri }}" alt="Screenshot">
                {% endif %}
            </div>
            {% endfor %}
        </div>
    </div>
    {% endif %}

    {% if f.get("remediation") %}
    <div class="detail-row">
        <div class="detail-label">Recommendations</div>
        <div class="detail-value">{{ f.remediation }}</div>
    </div>
    {% endif %}

    {% if f.get("references") %}
    <div class="detail-row no-break">
        <div class="detail-label">References</div>
        <div class="detail-value">
            {% for ref in f.references %}
            <div><a href="{{ ref }}">{{ ref }}</a></div>
            {% endfor %}
        </div>
    </div>
    {% endif %}

    <div class="detail-row no-break">
        <div class="detail-label">Status</div>
        <div class="detail-value">
            <span class="badge badge-{{ f.status_label | lower | replace(" ","") }}">{{ f.status_label }}</span>
        </div>
    </div>

</div>
</div>
{% endfor %}

{# ═══ APPENDICES ══════════════════════════════════════════════════════════= #}
<div class="page-break">
<h1>Appendices</h1>

<h2>Appendix A — Defining Severity</h2>
<p>
Severity ratings are determined using in-house expertise and industry-standard methodologies
including the OWASP Mobile Application Security Verification Standard (MASVS), the OWASP
Mobile Application Security Testing Guide (MASTG), and the Common Vulnerability Scoring
System (CVSS). The severity of each finding is determined independently; vulnerabilities
assigned a higher severity have a more significant technical and business impact.
</p>
<table>
    <thead>
        <tr>
            <th style="width:70pt;">Severity</th>
            <th>Description</th>
        </tr>
    </thead>
    <tbody>
        {% for row in severity_rubric %}
        <tr class="no-break">
            <td><span class="badge badge-{{ row.s | lower }}">{{ row.s }}</span></td>
            <td>{{ row.d }}</td>
        </tr>
        {% endfor %}
    </tbody>
</table>

<h2>Appendix B — MASVS Category Reference</h2>
<p>
Each finding maps to one or more OWASP MASVS v2 categories. The table below provides
a brief description of each category used in this report.
</p>
<table>
    <thead>
        <tr>
            <th style="width:110pt;">Category</th>
            <th>Description</th>
        </tr>
    </thead>
    <tbody>
        {% for cat, desc in masvs_descriptions.items() %}
        <tr class="no-break">
            <td class="bold small">{{ cat }}</td>
            <td>{{ desc }}</td>
        </tr>
        {% endfor %}
    </tbody>
</table>
</div>

</body>
</html>"""

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Mobile DAST PDF Report Generator")
    parser.add_argument("input",  help="Path to findings JSON file")
    parser.add_argument("output", help="Path for the output PDF")
    parser.add_argument(
        "--assets-dir",
        default=str(DEFAULT_ASSETS),
        help="Path to the SCC report assets directory (logos, hero image)",
    )
    parser.add_argument(
        "--screenshots-dir",
        default=None,
        help=(
            "Path to the evidence screenshots directory.  Images are automatically "
            "matched to findings by filename prefix (e.g. F01_*.png → finding F-01). "
            "Defaults to <input-dir>/screenshots/ when that directory exists."
        ),
    )
    args = parser.parse_args()

    # ── Load findings ──────────────────────────────────────────────────────────
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[-] Input file not found: {input_path}")
        sys.exit(1)

    data = json.loads(input_path.read_text())
    target      = data.get("target", {})
    raw_findings = data.get("findings", [])
    environment = data.get("environment", "Development")
    team_name   = data.get("teamName", "TELUS Digital Solutions Security team")

    # ── Auto-attach screenshots ────────────────────────────────────────────────
    screenshots_dir: Optional[Path] = None
    if args.screenshots_dir:
        screenshots_dir = Path(args.screenshots_dir)
    else:
        # Default: look for a screenshots/ sibling of the input file
        candidate = input_path.parent / "screenshots"
        if candidate.is_dir():
            screenshots_dir = candidate
            print(f"[*] Auto-detected screenshots directory: {screenshots_dir}")

    if screenshots_dir:
        auto_attach_screenshots(raw_findings, screenshots_dir)

    # ── Sort findings by severity ──────────────────────────────────────────────
    sorted_findings = sorted(
        raw_findings,
        key=lambda f: (severity_rank(f.get("severity", "")), (f.get("title") or "").lower()),
    )

    # ── Enrich findings for template ───────────────────────────────────────────
    for f in sorted_findings:
        f["severity"]     = normalize_severity(f.get("severity", ""))
        f["status_label"] = map_status(f.get("status", ""))
        f["confidence"]   = f.get("confidence", "Likely")
        # Resolve screenshot URIs for each evidence item
        for ev in f.get("evidence", []):
            ev["screenshot_uri"] = evidence_screenshot_uri(ev)

    # ── Counts / donut ─────────────────────────────────────────────────────────
    counts = count_by_severity(raw_findings)
    total  = sum(counts.values())
    counts_line = ", ".join(
        f"{counts[s]} {s.lower()}" for s in SEVERITY_ORDER
    )

    # ── Asset resolution ───────────────────────────────────────────────────────
    assets_dir = Path(args.assets_dir)
    logo_color_uri = img_to_data_uri(assets_dir / "telus-digital-logo.png")
    logo_black_uri = img_to_data_uri(assets_dir / "telus-digital-logo-black.png")
    hero_uri       = img_to_data_uri(assets_dir / "cover-hero.png")

    if not logo_color_uri:
        print(f"[!] Color logo not found at {assets_dir}/telus-digital-logo.png — skipping")
    if not logo_black_uri:
        print(f"[!] Black logo not found at {assets_dir}/telus-digital-logo-black.png — skipping")
    if not hero_uri:
        print(f"[!] Cover hero not found at {assets_dir}/cover-hero.png — using fallback gradient")

    # ── Render template ────────────────────────────────────────────────────────
    env = Environment(loader=BaseLoader())
    tmpl = env.from_string(TEMPLATE)

    html_str = tmpl.render(
        target          = target,
        sorted_findings = sorted_findings,
        counts          = counts,
        total           = total,
        counts_line     = counts_line,
        environment     = environment,
        team_name       = team_name,
        start_date      = format_date(target.get("startDate")),
        finish_date     = format_date(target.get("finishDate")),
        start_long      = format_long_date(target.get("startDate")),
        finish_long     = format_long_date(target.get("finishDate")),
        donut_svg       = build_donut_svg(counts),
        severity_order  = SEVERITY_ORDER,
        severity_color  = SEVERITY_COLOR,
        severity_rubric = SEVERITY_RUBRIC,
        masvs_descriptions = MASVS_DESCRIPTIONS,
        logo_color_uri  = logo_color_uri,
        logo_black_uri  = logo_black_uri,
        hero_uri        = hero_uri,
    )

    # ── Generate PDF ───────────────────────────────────────────────────────────
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[*] Rendering PDF → {output_path}")
    HTML(string=html_str, base_url=str(output_path.parent)).write_pdf(str(output_path))
    print(f"[+] Report saved: {output_path}")
    print(f"[+] Findings: {total}  (", end="")
    print("  ".join(f"{s}: {counts[s]}" for s in SEVERITY_ORDER if counts[s] > 0), end=")\n")


if __name__ == "__main__":
    main()
