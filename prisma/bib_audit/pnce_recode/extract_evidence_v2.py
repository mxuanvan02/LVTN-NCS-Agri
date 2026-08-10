#!/usr/bin/env python3
"""Stricter per-field evidence extraction for PNCE full-text recoding.

Pass 1 (extract_evidence.py) matched bare keywords and produced false
positives, e.g. S06 matched "greenhouse" inside "greenhouse gas emissions" in
the acknowledgements. This version:

  * uses narrow, field-specific regexes instead of bare topic words;
  * records the nearest preceding *printed* page marker or section heading so
    every candidate carries a real locator;
  * keeps a short verbatim quote so a human coder can adjudicate without
    re-reading the whole article.

Output is candidate evidence only. It does NOT assign coded values: coding is
done by the human/agent reading these windows, so an unmatched field becomes
not_stated rather than a guess.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

AUDIT = Path(__file__).resolve().parents[1]
CACHE = AUDIT / "fulltext_cache"
OUT = Path(__file__).resolve().parent / "evidence_candidates.json"

# Printed page markers seen in these corpora, e.g.
#   "Sensors 2020, 20, 6865  5 of 24"      (MDPI)
#   "Appl. Sci. 2022, 12, 4235  15 of 18"  (MDPI)
#   "153244  VOLUME 12, 2024"              (IEEE Access)
PAGE_MARKERS = [
    re.compile(r"[A-Z][A-Za-z.\s]{2,40}\s(?:19|20)\d{2},\s*\d+,\s*\d+\s+(\d+)\s+of\s+(\d+)"),
    re.compile(r"\b(\d{4,6})\s+VOLUME\s+\d+,\s*(?:19|20)\d{2}"),
    re.compile(r"\bVOLUME\s+\d+,\s*(?:19|20)\d{2}\s+(\d{4,6})\b"),
]

SECTION = re.compile(
    r"(?m)^\s*((?:\d+(?:\.\d+){0,3})\.?\s+[A-Z][^\n]{3,70}"
    r"|(?:[IVX]+)\.\s+[A-Z][^\n]{3,70}"
    r"|(?:Abstract|Introduction|Conclusion|Conclusions|Discussion|Results|"
    r"Methods|Materials and Methods|Related Work|System Design|"
    r"Experimental Results|Data Availability Statement)\b[^\n]{0,60})\s*$"
)

TABLE_FIG = re.compile(r"\b(Table|Fig\.|Figure)\s*(\d+)\b")

# ---------------------------------------------------------------- field probes
# Each probe: (field, regex). Regexes are deliberately specific so that a hit
# is meaningful on its own; topic-only words are avoided.
PROBES: list[tuple[str, re.Pattern]] = [
    # --- P: plant / application -------------------------------------------
    ("p1_application", re.compile(r"\b(?:in|inside|within)\s+(?:the\s+|a\s+|an\s+)?greenhouse(?:s)?\b", re.I)),
    ("p1_application", re.compile(r"\bgreenhouse\s+(?:climate|microclimate|temperature|humidity|experiment|compartment|deployment)\b", re.I)),
    ("p1_application", re.compile(r"\b(?:drip|sprinkler|furrow|paddy|field|farmland|open[- ]field)\s+irrigation\b", re.I)),
    ("p1_application", re.compile(r"\b(?:hydroponic|aeroponic|soilless|vertical farm|controlled[- ]environment agriculture|CEA)\b", re.I)),
    ("p1_application", re.compile(r"\b(?:alternate wetting and drying|AWD)\b")),
    ("p1_application", re.compile(r"\b(?:VTOL|aircraft|inverted pendulum|academic example|benchmark oscillator)\b", re.I)),
    ("p1_crop", re.compile(r"\b(tomato|lettuce|strawberr\w+|cucumber|rice|paddy|alfalfa|citrus|maize|wheat|pepper|basil|chilli|chili)\b", re.I)),

    # --- P2/P3: dynamics model, time constant ------------------------------
    ("p2_dynamics_model", re.compile(r"\b(?:state[- ]space|transfer function|first[- ]order|second[- ]order|nonlinear|lineari[sz]ed)\s+(?:model|dynamics|system)\b", re.I)),
    ("p2_dynamics_model", re.compile(r"\b(?:ARIMA|ARX|LSTM|neural network|gaussian process|data[- ]driven)\s+model\b", re.I)),
    ("p2_dynamics_model", re.compile(r"\b(?:energy|mass)\s+balance\s+(?:equation|model)\b", re.I)),
    ("p3_time_constant", re.compile(r"\btime\s+constant[^.\n]{0,60}", re.I)),
    ("p3_time_constant", re.compile(r"\b(?:sampling|control|prediction)\s+(?:period|interval|time|horizon)\s*(?:of|=|is)?\s*\d+(?:\.\d+)?\s*(?:s|sec|seconds|min|minutes|h|hours)\b", re.I)),

    # --- N1: protocol ------------------------------------------------------
    ("n1_protocol", re.compile(r"\bLoRaWAN\b")),
    ("n1_protocol", re.compile(r"\bLoRa\b(?!WAN)")),
    ("n1_protocol", re.compile(r"\b(?:ZigBee|Zig[- ]Bee|IEEE\s*802\.15\.4|XBee)\b", re.I)),
    ("n1_protocol", re.compile(r"\b(?:Wi[- ]?Fi|IEEE\s*802\.11|ESP8266|ESP32)\b", re.I)),
    ("n1_protocol", re.compile(r"\b(?:NB[- ]IoT|LTE[- ]M|GSM|GPRS|3G|4G|5G|SIM800|SIM900)\b")),
    ("n1_protocol", re.compile(r"\b(?:Ethernet|switched Ethernet|CAN bus|Modbus|RS[- ]?485|PROFINET|EtherCAT)\b", re.I)),
    ("n1_protocol", re.compile(r"\b(?:MQTT|CoAP|HTTP\s+REST)\b")),
    ("n1_protocol_absent", re.compile(r"\bno\s+(?:communication\s+)?network\b", re.I)),

    # --- N2/N3: latency, packet loss ---------------------------------------
    ("n2_latency", re.compile(r"\b(?:end[- ]to[- ]end\s+)?(?:delay|latency|round[- ]trip time|RTT)\b[^.\n]{0,80}?\d+(?:\.\d+)?\s*(?:ms|s|milliseconds|seconds)", re.I)),
    ("n2_latency", re.compile(r"\d+(?:\.\d+)?\s*(?:ms|milliseconds)\b[^.\n]{0,60}(?:delay|latency)", re.I)),
    ("n3_packet_loss", re.compile(r"\b(?:packet\s+(?:loss|delivery|error)\s*(?:rate|ratio)?|PDR|PLR|packet\s+loss)\b[^.\n]{0,80}", re.I)),
    ("n3_packet_loss", re.compile(r"\b(?:RSSI|SNR)\b[^.\n]{0,70}", re.I)),

    # --- C1: control strategy ---------------------------------------------
    ("c1_strategy", re.compile(r"\b(?:model predictive control|MPC|NMPC|DMPC)\b")),
    ("c1_strategy", re.compile(r"\b(?:PID|PI)\s+(?:controller|control)\b")),
    ("c1_strategy", re.compile(r"\bfuzzy\s+(?:logic|controller|control|inference)\b", re.I)),
    ("c1_strategy", re.compile(r"\b(?:reinforcement learning|Q[- ]learning|deep\s+RL|SAC|DDPG|PPO|machine learning)\b", re.I)),
    ("c1_strategy", re.compile(r"\b(?:on[-/ ]off|threshold[- ]based|bang[- ]bang|hysteresis)\s+(?:control|controller|actuation|logic)?\b", re.I)),
    ("c1_strategy", re.compile(r"\boptimal control\b", re.I)),
    ("c1_strategy_monitoring_only", re.compile(r"\bmonitoring\s+(?:system|only|platform)\b[^.\n]{0,60}", re.I)),

    # --- C2: trigger -------------------------------------------------------
    ("c2_trigger", re.compile(r"\bevent[- ]triggered\b", re.I)),
    ("c2_trigger", re.compile(r"\bself[- ]triggered\b", re.I)),
    ("c2_trigger", re.compile(r"\b(?:time[- ]triggered|periodic(?:ally)?\s+sampl\w+|fixed\s+sampling)\b", re.I)),
    ("c2_trigger", re.compile(r"\btriggering\s+(?:condition|mechanism|rule|law)\b", re.I)),
    ("c2_trigger", re.compile(r"\b(?:remote(?:ly)?|manual(?:ly)?)\s+(?:control|actuat\w+|trigger\w+|switch\w+|turn\w*\s+on)\b", re.I)),

    # --- C3: architecture --------------------------------------------------
    ("c3_architecture", re.compile(r"\b(?:cloud|ThingSpeak|Firebase|AWS|Azure|Blynk|cloud\s+server|cloud\s+platform)\b", re.I)),
    ("c3_architecture", re.compile(r"\b(?:edge|fog)\s+(?:computing|node|gateway|layer|device)\b", re.I)),
    ("c3_architecture", re.compile(r"\b(?:Arduino|Raspberry Pi|STM32|microcontroller|PLC)\b", re.I)),
    ("c3_architecture", re.compile(r"\b(?:simulation|simulated)\s+(?:only|study|results?|environment|model)\b", re.I)),

    # --- Evidence type -----------------------------------------------------
    ("evidence_type", re.compile(r"\b(?:field|on[- ]farm|on[- ]site)\s+(?:trial|experiment|test|deployment|study)\b", re.I)),
    ("evidence_type", re.compile(r"\b(?:we|authors?)\s+(?:deployed|installed|implemented|conducted|performed)\b[^.\n]{0,90}", re.I)),
    ("evidence_type", re.compile(r"\b(?:greenhouse|plot|field)\s+experiment\b", re.I)),
    ("evidence_type", re.compile(r"\b(?:prototype|testbed|test bench|laboratory|lab[- ]scale|hardware[- ]in[- ]the[- ]loop|HIL)\b", re.I)),
    ("evidence_type", re.compile(r"\b(?:MATLAB|Simulink|Riverbed|OMNeT|NS[- ]?[23]|CasADi|IPOPT|GRAMPC|Xpress|TrueTime)\b")),
    ("evidence_type", re.compile(r"\bsimulation\s+(?:results?|study|scenario|run)s?\b", re.I)),

    # --- Article type ------------------------------------------------------
    ("article_type_flag", re.compile(r"(?m)^\s*(?:sensors|applied sciences|agronomy|electronics|actuators|energies)\s+(Review|Article|Communication)\s*$", re.I)),
    ("article_type_flag", re.compile(r"\b(?:this\s+)?(?:review|survey)\s+(?:paper\s+)?(?:presents|provides|summari[sz]es|covers)\b", re.I)),
    ("article_type_flag", re.compile(r"\bRESEARCH ARTICLE\b")),

    # --- Comparator --------------------------------------------------------
    ("comparator_present", re.compile(r"\bcompared?\s+(?:with|to|against)\b[^.\n]{0,90}", re.I)),
    ("comparator_present", re.compile(r"\b(?:baseline|benchmark|control group|conventional|traditional)\b[^.\n]{0,70}", re.I)),

    # --- E: outcomes -------------------------------------------------------
    ("e1_control_quality", re.compile(r"\b(?:RMSE|MAE|IAE|ISE|overshoot|settling time|steady[- ]state error|tracking error)\b[^.\n]{0,80}", re.I)),
    ("e1_control_quality", re.compile(r"\b(?:yield|dry weight|water\s+(?:sav\w+|use|consumption))\b[^.\n]{0,80}", re.I)),
    ("e2_network_resource", re.compile(r"\b(?:number of|reduc\w+|sav\w+)\s+(?:transmissions?|samples?|packets?|messages?|updates?)\b[^.\n]{0,80}", re.I)),
    ("e2_network_resource", re.compile(r"\b(?:duty cycle|airtime|bandwidth|throughput)\b[^.\n]{0,70}", re.I)),
    ("e3_energy", re.compile(r"\b(?:energy|power)\s+(?:consumption|saving|usage|efficiency)\b[^.\n]{0,80}", re.I)),
    ("e3_energy", re.compile(r"\b(?:battery\s+(?:life|lifetime)|mAh|mW|µA|uA|Wh|kWh|solar\s+panel)\b[^.\n]{0,70}", re.I)),
]


def normalise(raw: str) -> str:
    return re.sub(r"[ \t]+", " ", raw.replace("\r", "\n"))


def build_locator_index(text: str):
    """Return sorted lists of (offset, label) for page markers and headings."""
    marks = []
    for pat in PAGE_MARKERS:
        for m in pat.finditer(text):
            if m.re is PAGE_MARKERS[0]:
                marks.append((m.start(), f"printed p.{m.group(1)} of {m.group(2)}"))
            else:
                marks.append((m.start(), f"printed p.{m.group(1)}"))
    heads = [(m.start(), " ".join(m.group(1).split())) for m in SECTION.finditer(text)]
    marks.sort()
    heads.sort()
    return marks, heads


def nearest_before(index, pos):
    lo, hi, best = 0, len(index) - 1, None
    while lo <= hi:
        mid = (lo + hi) // 2
        if index[mid][0] <= pos:
            best = index[mid][1]
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def locator_for(pos, marks, heads, text):
    parts = []
    head = nearest_before(heads, pos)
    if head:
        parts.append(f"sec. '{head[:60]}'")
    page = nearest_before(marks, pos)
    if page:
        parts.append(page)
    window = text[max(0, pos - 400): pos + 400]
    tf = TABLE_FIG.findall(window)
    if tf:
        uniq = []
        for kind, num in tf:
            tag = f"{'Table' if kind == 'Table' else 'Fig.'} {num}"
            if tag not in uniq:
                uniq.append(tag)
        parts.append("near " + ", ".join(uniq[:3]))
    return "; ".join(parts) if parts else "no structural marker nearby"


def main():
    ids = sorted(
        (p.stem for p in CACHE.glob("S*.txt")),
        key=lambda s: int(s[1:]),
    )
    out = {}
    for rid in ids:
        text = normalise((CACHE / f"{rid}.txt").read_text(encoding="utf-8", errors="ignore"))
        marks, heads = build_locator_index(text)
        fields: dict[str, list[dict]] = {}
        for field, pat in PROBES:
            seen_quotes = set()
            for m in pat.finditer(text):
                start = max(0, m.start() - 170)
                quote = " ".join(text[start:m.end() + 200].split())
                key = quote[:80]
                if key in seen_quotes:
                    continue
                seen_quotes.add(key)
                fields.setdefault(field, []).append({
                    "match": " ".join(m.group(0).split())[:90],
                    "locator": locator_for(m.start(), marks, heads, text),
                    "quote": quote[:330],
                })
                if len(fields[field]) >= 6:
                    break
        out[rid] = {
            "chars": len(text),
            "head": " ".join(text[:340].split()),
            "n_page_markers": len(marks),
            "n_headings": len(heads),
            "fields": fields,
        }
        print(f"  {rid}: {len(text):>7} chars | pages {len(marks):>3} | heads {len(heads):>3} | fields {len(fields)}")

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(AUDIT.parent)} for {len(out)} records")


if __name__ == "__main__":
    main()
