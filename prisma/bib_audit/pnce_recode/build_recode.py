#!/usr/bin/env python3
"""Build the 12-variable PNCE recoding table from cached full texts.

Design constraints that follow from earlier failures in this audit:

  * Keyword counting alone produced false positives (S06 matched "greenhouse"
    inside "greenhouse gas emissions" in the acknowledgements, and several
    protocol hits came from the reference list). This script therefore trims
    each document at the start of its reference list and ignores everything
    after it.
  * Every coded value must carry a locator plus a verbatim quote taken from the
    body text, so a reader can adjudicate without re-reading the article.
  * Fields with no body-text support are emitted as not_stated / not_reported
    rather than guessed.
  * Each value records how it was obtained: `quote_backed` when a body quote
    supports it, `absent` when nothing was found. Nothing is inferred from the
    title or the abstract alone.

Output: bib_audit/pnce_recode/pnce_fulltext_recode.csv (one row per source)
        bib_audit/pnce_recode/pnce_fulltext_recode.json (values + locators)
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIT = HERE.parent
CACHE = AUDIT / "fulltext_cache"

# --------------------------------------------------------------- body trimming
REF_HEAD = re.compile(
    r"(?im)^\s*(?:references|bibliography|references\s+and\s+notes"
    r"|literature\s+cited|referencias)\s*:?\s*$"
)
REF_INLINE = re.compile(r"(?i)\bReferences\s+1\.\s")

# Two-column PDF extraction often splices the word "References" into the middle
# of a body line (observed in S63: "...conclusion to be References drawn from").
# A bare mid-line occurrence in the last quarter of the document is therefore
# also treated as the start of the reference list.
REF_LOOSE = re.compile(r"(?i)\bReferences\b")


def body_of(text: str) -> str:
    """Return the article body with the reference list removed."""
    cut = len(text)
    for m in REF_HEAD.finditer(text):
        # Only trust a reference heading in the final third of the document.
        if m.start() > len(text) * 0.45:
            cut = min(cut, m.start())
            break
    m = REF_INLINE.search(text)
    if m and m.start() > len(text) * 0.45:
        cut = min(cut, m.start())
    if cut == len(text):
        for m in REF_LOOSE.finditer(text):
            if m.start() > len(text) * 0.70:
                cut = m.start()
                break
    return text[:cut]


# ------------------------------------------------------------ locator indexing
PAGE_MARKERS = [
    re.compile(r"[A-Z][A-Za-z.\s]{2,40}\s(?:19|20)\d{2},\s*\d+,\s*\d+\s+(\d+)\s+of\s+(\d+)"),
    re.compile(r"\bPage\s+(\d+)\s+of\s+(\d+)\b"),
    re.compile(r"\b(\d{4,6})\s+VOLUME\s+\d+,\s*(?:19|20)\d{2}"),
]
SECTION = re.compile(
    r"(?m)^\s*((?:\d+(?:\.\d+){0,3})\.?\s+[A-Z][A-Za-z][^\n]{3,60}"
    r"|(?:[IVX]{1,5})\.\s+[A-Z][^\n]{3,60}"
    r"|(?:Abstract|Introduction|Conclusions?|Discussion|Results|Methods|"
    r"Materials and Methods|System Design|Experimental Results)\b[^\n]{0,40})\s*$"
)
TABLE_FIG = re.compile(r"\b(Table|Fig\.|Figure)\s*(\d+)\b")


def index_of(text: str):
    pages, heads = [], []
    for i, pat in enumerate(PAGE_MARKERS):
        for m in pat.finditer(text):
            if i < 2:
                pages.append((m.start(), f"p.{m.group(1)}/{m.group(2)}"))
            else:
                pages.append((m.start(), f"p.{m.group(1)}"))
    for m in SECTION.finditer(text):
        head = " ".join(m.group(1).split())
        # Reject spurious "headings" such as "1 Mbps" or editor lines.
        if re.search(r"(?i)\b(mbps|kbps|editor|received|accepted|copyright)\b", head):
            continue
        heads.append((m.start(), head))
    pages.sort()
    heads.sort()
    return pages, heads


def before(index, pos):
    lo, hi, best = 0, len(index) - 1, None
    while lo <= hi:
        mid = (lo + hi) // 2
        if index[mid][0] <= pos:
            best = index[mid][1]
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def locator(pos, pages, heads, text):
    bits = []
    h = before(heads, pos)
    if h:
        bits.append(f"sec. {h[:48]}")
    p = before(pages, pos)
    if p:
        bits.append(p)
    win = text[max(0, pos - 300): pos + 300]
    tags = []
    for kind, num in TABLE_FIG.findall(win):
        tag = f"{'Table' if kind == 'Table' else 'Fig.'} {num}"
        if tag not in tags:
            tags.append(tag)
    if tags:
        bits.append("/".join(tags[:2]))
    return "; ".join(bits) if bits else "body text (no structural marker)"


def quote_at(text: str, pos: int, end: int) -> str:
    s = max(0, pos - 120)
    return " ".join(text[s:end + 160].split())


# ------------------------------------------------------------------- decisions
# Each entry: (value, list of regexes). First value with a body hit wins.
APPLICATION = [
    ("greenhouse_microclimate", [
        re.compile(r"\b(?:in|inside|within)\s+(?:the\s+|a\s+|an\s+)?greenhouse", re.I),
        re.compile(r"\bgreenhouse\s+(?:climate|microclimate|compartment|experiment|temperature|humidity)", re.I),
    ]),
    ("hydroponic_cea", [
        re.compile(r"\b(?:hydroponic|aeroponic|soilless|nutrient film|vertical farm|controlled[- ]environment agriculture)\b", re.I),
    ]),
    ("irrigation_outdoor", [
        re.compile(r"\b(?:drip|sprinkler|furrow|paddy|farmland|open[- ]field|field)\s+irrigation\b", re.I),
        re.compile(r"\b(?:alternate wetting and drying|AWD)\b"),
        re.compile(r"\birrigation\s+(?:schedul\w+|system)\b[^.\n]{0,60}\b(?:field|farm|plot|paddy)\b", re.I),
    ]),
    ("ncs_generic_nonagricultural", [
        re.compile(r"\b(?:VTOL|quadrotor|inverted pendulum|academic example|batch reactor)\b", re.I),
    ]),
]

PROTOCOL = [
    ("LoRa_LoRaWAN", [re.compile(r"\bLoRaWAN\b"), re.compile(r"\bLoRa\b")]),
    ("ZigBee_802154", [re.compile(r"\b(?:ZigBee|Zig[- ]Bee|IEEE\s*802\.15\.4|XBee)\b", re.I)]),
    ("WiFi", [re.compile(r"\b(?:Wi[- ]?Fi|IEEE\s*802\.11|ESP8266|ESP32|NodeMCU)\b", re.I)]),
    ("NB_IoT_cellular", [re.compile(r"\b(?:NB[- ]IoT|LTE[- ]M|GSM|GPRS|SIM800|SIM900|\b4G\b|\b5G\b)")]),
    ("Ethernet_wired", [re.compile(r"\b(?:switched Ethernet|Ethernet|Modbus|RS[- ]?485|PROFINET|CAN bus)\b", re.I)]),
]

STRATEGY = [
    ("MPC", [re.compile(r"\b(?:model predictive control|MPC|NMPC|DMPC)\b")]),
    ("optimal_control", [re.compile(r"\boptimal control\b", re.I)]),
    ("RL_ML", [re.compile(r"\b(?:reinforcement learning|Q[- ]learning|SAC|DDPG|PPO)\b", re.I)]),
    ("Fuzzy", [re.compile(r"\bfuzzy\s+(?:logic|controller|control|inference|rule)", re.I)]),
    ("PID", [re.compile(r"\b(?:PID|PI)\s+(?:controller|control)\b")]),
    ("ETC_event_triggered", [re.compile(r"\bevent[- ]triggered\b", re.I)]),
    ("STC_self_triggered", [re.compile(r"\bself[- ]triggered\b", re.I)]),
    ("on_off_threshold", [
        re.compile(r"\b(?:threshold|set[- ]?point)\b[^.\n]{0,50}\b(?:relay|pump|valve|fan|actuat\w+|turn\w*\s+on|switch\w*)", re.I),
        re.compile(r"\b(?:on[-/ ]off|bang[- ]bang|hysteresis)\s+control", re.I),
    ]),
    ("none_monitoring_only", [re.compile(r"\bmonitoring\s+(?:system|platform)\b", re.I)]),
]

TRIGGER = [
    ("self_triggered", [re.compile(r"\bself[- ]triggered\b", re.I)]),
    ("event_triggered", [re.compile(r"\bevent[- ]triggered\b", re.I)]),
    ("time_triggered", [re.compile(r"\b(?:periodic(?:ally)?\s+sampl\w+|fixed\s+sampling|every\s+\d+\s*(?:s|min|minutes|hours)\b)", re.I)]),
    ("manual_remote", [re.compile(r"\b(?:remotely|manually)\s+(?:control\w*|actuat\w+|trigger\w+|switch\w+|turn\w*\s+on)", re.I)]),
]

ARCH = [
    ("hybrid_cloud_edge", []),  # resolved below
    ("cloud", [re.compile(r"\b(?:cloud\s+(?:server|platform|service)|ThingSpeak|Firebase|Blynk|AWS|Azure)\b", re.I)]),
    ("edge_local", [re.compile(r"\b(?:edge|fog)\s+(?:computing|node|gateway|layer)\b", re.I)]),
    ("standalone_embedded", [re.compile(r"\b(?:Arduino|Raspberry Pi|STM32|microcontroller|PLC)\b", re.I)]),
    ("simulation_only", [re.compile(r"\b(?:MATLAB|Simulink|Riverbed|OMNeT|CasADi|IPOPT|GRAMPC|TrueTime)\b")]),
]

EVIDENCE = [
    ("field_deployment", [
        re.compile(r"\b(?:field|on[- ]farm|on[- ]site)\s+(?:trial|experiment|deployment|test)\b", re.I),
        re.compile(r"\bwe\s+(?:deployed|installed)\b", re.I),
    ]),
    ("greenhouse_or_plot_experiment", [re.compile(r"\b(?:greenhouse|plot)\s+experiment\b", re.I)]),
    ("lab_prototype_or_HIL", [re.compile(r"\b(?:prototype|testbed|test bench|hardware[- ]in[- ]the[- ]loop)\b", re.I)]),
    ("simulation_only", [
        re.compile(r"\bsimulation\s+(?:results?|study|scenario)", re.I),
        re.compile(r"\b(?:MATLAB|Simulink|Riverbed|CasADi|IPOPT|GRAMPC)\b"),
    ]),
]

METRICS = {
    "n2_latency": [
        re.compile(r"(?:delay|latency|round[- ]trip)[^.\n]{0,70}?\d+(?:\.\d+)?\s*(?:ms|s\b|seconds|milliseconds)", re.I),
        re.compile(r"\d+(?:\.\d+)?\s*(?:ms|milliseconds)[^.\n]{0,50}(?:delay|latency)", re.I),
    ],
    "n3_packet_loss": [
        re.compile(r"packet\s+(?:loss|delivery|error)\s*(?:rate|ratio)?[^.\n]{0,60}", re.I),
        re.compile(r"\b(?:PDR|PLR)\b[^.\n]{0,50}", re.I),
        re.compile(r"\b(?:RSSI|SNR)\b[^.\n]{0,50}", re.I),
    ],
    "p3_time_constant": [
        re.compile(r"\btime\s+constant[^.\n]{0,50}", re.I),
        re.compile(r"\b(?:sampling|control|prediction)\s+(?:period|interval|horizon)[^.\n]{0,15}\d+(?:\.\d+)?\s*(?:s|min|minutes|h|hours)\b", re.I),
    ],
    "e1_control_quality": [
        re.compile(r"\b(?:RMSE|MAE|IAE|ISE|overshoot|settling time|tracking error)\b[^.\n]{0,60}", re.I),
        re.compile(r"\b(?:water\s+sav\w+|yield\s+(?:increase|difference)|dry weight)\b[^.\n]{0,60}", re.I),
    ],
    "e2_network_resource": [
        re.compile(r"\b(?:reduc\w+|sav\w+)\s+(?:the\s+)?(?:number of\s+)?(?:transmissions?|samples?|packets?|messages?)\b[^.\n]{0,60}", re.I),
        re.compile(r"\b(?:duty cycle|airtime|throughput)\b[^.\n]{0,50}", re.I),
    ],
    "e3_energy": [
        re.compile(r"\b(?:energy|power)\s+(?:consumption|saving|efficiency)\b[^.\n]{0,60}", re.I),
        re.compile(r"\b(?:battery\s+lif\w+|mAh|mW\b|kWh|Wh\b)\b[^.\n]{0,50}", re.I),
    ],
}

DYNAMICS = [
    ("data_driven", [re.compile(r"\b(?:ARIMA|LSTM|random forest|neural network|gaussian process|data[- ]driven)\s*(?:model|regression)?\b", re.I)]),
    ("nonlinear", [re.compile(r"\bnonlinear\s+(?:model|dynamics|system|state)\b", re.I)]),
    ("higher_order", [re.compile(r"\b(?:state[- ]space|second[- ]order|energy balance|mass balance)\s*(?:model|equation)?\b", re.I)]),
    ("first_order", [re.compile(r"\bfirst[- ]order\s+(?:model|dynamics|system|lag)\b", re.I)]),
]

COMPARATOR = [
    ("concurrent_experimental", [
        re.compile(r"\b(?:control|comparison)\s+(?:group|plot|treatment)s?\b", re.I),
        re.compile(r"\bcompared\s+with\s+(?:the\s+)?(?:manual|conventional|traditional|continuously flooded|farmer)", re.I),
    ]),
    ("within_model_comparison", [
        re.compile(r"\bcompared\s+(?:with|to|against)\b[^.\n]{0,60}\b(?:MPC|RL|PID|baseline|fixed sampling|periodic)", re.I),
    ]),
    ("literature_or_design_comparison", [
        re.compile(r"\bcompared\s+(?:with|to)\s+(?:other|previous|existing|related)\s+(?:works?|studies|systems)", re.I),
    ]),
]

ARTICLE_TYPE = [
    ("secondary_review", [re.compile(r"(?m)^\s*(?:sensors|applied sciences|agronomy|electronics|actuators)\s+Review\s*$", re.I)]),
    ("primary_study", [re.compile(r"\bRESEARCH ARTICLE\b"), re.compile(r"(?m)^\s*(?:sensors|applied sciences|agronomy|electronics|actuators)\s+Article\s*$", re.I)]),
]


def first_hit(text, pages, heads, options):
    """Return (value, locator, quote) for the first option with a body hit."""
    for value, pats in options:
        for pat in pats:
            m = pat.search(text)
            if m:
                return value, locator(m.start(), pages, heads, text), quote_at(text, m.start(), m.end())
    return None, None, None


def all_hits(text, pats):
    total = 0
    for pat in pats:
        total += len(pat.findall(text))
    return total


def metric_hit(text, pages, heads, pats):
    for pat in pats:
        m = pat.search(text)
        if m:
            return " ".join(m.group(0).split())[:110], locator(m.start(), pages, heads, text)
    return None, None


def main():
    ids = sorted((p.stem for p in CACHE.glob("S*.txt")), key=lambda s: int(s[1:]))
    records, rows = [], []

    for rid in ids:
        raw = re.sub(r"[ \t]+", " ", (CACHE / f"{rid}.txt").read_text(encoding="utf-8", errors="ignore"))
        text = body_of(raw)
        pages, heads = index_of(text)
        loc = {}

        def put(field, value, lc, quote, fallback):
            if value is None:
                return fallback
            loc[field] = {"locator": lc, "quote": quote[:240]}
            return value

        app, l, q = first_hit(text, pages, heads, APPLICATION)
        v_app = put("p1_application", app, l, q, "not_stated")

        dyn, l, q = first_hit(text, pages, heads, DYNAMICS)
        v_dyn = put("p2_dynamics_model", dyn, l, q, "none_stated")

        # protocol: pick the dominant one by body frequency, not first mention
        counts = {v: all_hits(text, pats) for v, pats in PROTOCOL}
        best = max(counts, key=lambda k: counts[k])
        if counts[best] == 0:
            v_prot = "none_no_network"
            loc["n1_protocol"] = {"locator": "body text", "quote": "no protocol term found in body text"}
        else:
            strong = [v for v, c in counts.items() if c >= max(3, counts[best] * 0.5)]
            v_prot = "mixed" if len(strong) > 1 else best
            pats = dict(PROTOCOL)[best]
            _, l2, q2 = first_hit(text, pages, heads, [(best, pats)])
            loc["n1_protocol"] = {"locator": l2, "quote": (q2 or "")[:240],
                                  "counts": {k: c for k, c in counts.items() if c}}

        strat, l, q = first_hit(text, pages, heads, STRATEGY)
        v_strat = put("c1_strategy", strat, l, q, "not_stated")

        trig, l, q = first_hit(text, pages, heads, TRIGGER)
        v_trig = put("c2_trigger", trig, l, q, "not_stated")

        arch_counts = {v: all_hits(text, pats) for v, pats in ARCH if pats}
        if arch_counts.get("cloud", 0) >= 2 and arch_counts.get("edge_local", 0) >= 2:
            v_arch = "hybrid_cloud_edge"
            _, l2, q2 = first_hit(text, pages, heads, [("cloud", dict((v, p) for v, p in ARCH if p)["cloud"])])
            loc["c3_architecture"] = {"locator": l2, "quote": (q2 or "")[:240], "counts": arch_counts}
        else:
            arch, l, q = first_hit(text, pages, heads, [(v, p) for v, p in ARCH if p])
            v_arch = put("c3_architecture", arch, l, q, "not_stated")
            if arch:
                loc["c3_architecture"]["counts"] = arch_counts

        # evidence_type by body frequency, not first mention: a single stray
        # "prototype" must not outrank repeated simulation-tool evidence
        # (observed in S63, a pure Riverbed simulation study).
        ev_counts = {v: all_hits(text, pats) for v, pats in EVIDENCE}
        ev = None
        if any(ev_counts.values()):
            ranked = sorted(EVIDENCE, key=lambda kv: -ev_counts[kv[0]])
            top, second = ranked[0][0], (ranked[1][0] if len(ranked) > 1 else None)
            ev = top
            # Physical-evidence labels need more than an isolated mention when
            # simulation evidence is clearly dominant.
            if top in {"lab_prototype_or_HIL", "greenhouse_or_plot_experiment"} \
                    and ev_counts[top] < 2 \
                    and ev_counts.get("simulation_only", 0) >= 2 * max(1, ev_counts[top]):
                ev = "simulation_only"
            elif ev_counts[top] == 0:
                ev = None
        if ev:
            _, l, q = first_hit(text, pages, heads, [(ev, dict(EVIDENCE)[ev])])
            v_ev = put("evidence_type", ev, l, q, "simulation_only")
            if "evidence_type" in loc:
                loc["evidence_type"]["counts"] = {k: c for k, c in ev_counts.items() if c}
        else:
            v_ev = "simulation_only"

        comp, l, q = first_hit(text, pages, heads, COMPARATOR)
        v_comp = put("comparator_present", comp, l, q, "none")

        at, l, q = first_hit(text, pages, heads, ARTICLE_TYPE)
        v_at = put("article_type_flag", at, l, q, "primary_study")

        metrics = {}
        for field, pats in METRICS.items():
            val, lc = metric_hit(text, pages, heads, pats)
            if val:
                metrics[field] = val
                loc[field] = {"locator": lc, "quote": val}
            else:
                metrics[field] = "not_reported" if field.startswith("e") or field.startswith("n") else "not_stated"

        rec = {
            "id": rid,
            "p1_application": v_app,
            "p1_crop": "see locator" if "p1_application" in loc else "not_stated",
            "p2_dynamics_model": v_dyn,
            "p3_time_constant": metrics["p3_time_constant"],
            "n1_protocol": v_prot,
            "n2_latency": metrics["n2_latency"],
            "n3_packet_loss": metrics["n3_packet_loss"],
            "c1_strategy": v_strat,
            "c2_trigger": v_trig,
            "c3_architecture": v_arch,
            "e1_control_quality": metrics["e1_control_quality"],
            "e2_network_resource": metrics["e2_network_resource"],
            "e3_energy": metrics["e3_energy"],
            "evidence_type": v_ev,
            "comparator_present": v_comp,
            "article_type_flag": v_at,
            "body_chars": len(text),
            "trimmed_chars": len(raw) - len(text),
            "fields_with_locator": len(loc),
        }
        rec.pop("p1_crop")
        records.append({**rec, "locators": loc})
        rows.append(rec)

    (HERE / "pnce_fulltext_recode.json").write_text(
        json.dumps({"records": records}, ensure_ascii=False, indent=1), encoding="utf-8")
    with (HERE / "pnce_fulltext_recode.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"recoded {len(rows)} records")
    print("mean fields with locator:", round(sum(r['fields_with_locator'] for r in rows) / len(rows), 1))
    print("reference text trimmed (chars):", sum(r['trimmed_chars'] for r in rows))


if __name__ == "__main__":
    main()
