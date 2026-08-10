#!/usr/bin/env python3
"""Extract locator-bearing candidate evidence for PNCE recoding.

For each cached full text, pull compact snippets around keywords tied to each
of the 12 PNCE variables, together with the nearest preceding structural
marker (section heading, table caption, figure caption, or printed page
number). The output is a per-record evidence digest that a human/model coder
reads instead of the whole article, so every coded value can cite a locator
that actually exists in the text.

This script only reads the cache and writes a digest; it never codes.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

AUDIT = Path(__file__).resolve().parents[1]
CACHE = AUDIT / "fulltext_cache"
OUT = Path(__file__).resolve().parent

# Structural markers we can quote as locators.
SECTION_RE = re.compile(
    r"(?:^|\s)((?:[0-9]{1,2}(?:\.[0-9]{1,2}){0,2}\.?\s+[A-Z][A-Za-z][^.\n]{2,60})"
    r"|(?:(?:Section|SECTION)\s+[0-9IVX]+(?:\.[0-9]+)*)"
    r"|(?:Table\s+[0-9]{1,2})|(?:TABLE\s+[0-9IVX]{1,3})"
    r"|(?:Fig(?:ure)?\.?\s+[0-9]{1,2})"
    r"|(?:[IVX]{1,4}\.\s+[A-Z][A-Z ]{3,40}))"
)
PAGE_RE = re.compile(r"\b(\d{1,4})\s+of\s+(\d{1,4})\b")

PATTERNS: dict[str, list[str]] = {
    "p1_application": [
        r"greenhouse", r"glasshouse", r"irrigat", r"hydroponic", r"aeroponic",
        r"soilless", r"drip", r"paddy", r"field trial", r"open field",
        r"plot of", r"crop", r"lettuce", r"tomato", r"rice", r"alfalfa",
    ],
    "p2_dynamics_model": [
        r"state[- ]space", r"first[- ]order", r"second[- ]order",
        r"differential equation", r"nonlinear model", r"transfer function",
        r"lumped", r"energy balance", r"mass balance", r"data[- ]driven",
        r"identif(?:y|ied|ication)", r"ARX", r"ARIMA", r"neural network model",
    ],
    "p3_time_constant": [
        r"time constant", r"settling time", r"rise time", r"sampling (?:period|time|interval)",
        r"every\s+\d+\s*(?:s|sec|second|min|minute|hour|h)\b",
        r"\b\d+\s*(?:s|sec|second|min|minute|hour|h)\s+(?:interval|period|sampling)",
    ],
    "n1_protocol": [
        r"LoRaWAN", r"LoRa\b", r"ZigBee", r"802\.15\.4", r"Wi-?Fi", r"802\.11",
        r"NB-?IoT", r"GSM", r"GPRS", r"3G\b", r"4G\b", r"LTE", r"Sigfox",
        r"Bluetooth", r"BLE\b", r"Ethernet", r"MQTT", r"CoAP", r"RS-?485",
        r"nRF24", r"XBee", r"gateway",
    ],
    "n2_latency": [
        r"latenc", r"\bdelay\b", r"round[- ]trip", r"RTT", r"end[- ]to[- ]end",
        r"response time", r"\bjitter\b", r"\bms\b", r"millisecond",
    ],
    "n3_packet_loss": [
        r"packet loss", r"packet delivery", r"\bPDR\b", r"packet error",
        r"lost packets", r"dropout", r"retransmi", r"\bPER\b",
        r"delivery ratio", r"success rate",
    ],
    "c1_strategy": [
        r"on[-/ ]off control", r"threshold", r"\bPID\b", r"fuzzy",
        r"model predictive", r"\bMPC\b", r"reinforcement learning", r"\bRL\b",
        r"machine learning", r"event[- ]triggered", r"self[- ]triggered",
        r"optimal control", r"receding horizon", r"monitoring only",
        r"\bhybrid\b",
    ],
    "c2_trigger": [
        r"periodic", r"time[- ]triggered", r"event[- ]triggered",
        r"self[- ]triggered", r"trigger(?:ing)? condition", r"adaptive sampling",
        r"manual", r"remote control", r"on demand",
    ],
    "c3_architecture": [
        r"\bcloud\b", r"edge comput", r"fog comput", r"\bserver\b",
        r"microcontroller", r"Arduino", r"Raspberry", r"ESP32", r"ESP8266",
        r"embedded", r"standalone", r"simulat", r"MATLAB", r"Simulink",
        r"hardware[- ]in[- ]the[- ]loop",
    ],
    "e1_control_quality": [
        r"RMSE", r"MAE\b", r"IAE\b", r"ISE\b", r"tracking error",
        r"steady[- ]state error", r"overshoot", r"yield", r"water sav",
        r"water use", r"\bWUE\b", r"dry weight", r"biomass",
        r"\u00b1\s*\d", r"accuracy of",
    ],
    "e2_network_resource": [
        r"number of (?:transmissions|samples|packets)", r"transmission rate",
        r"duty cycle", r"reduc(?:e|ed|tion) (?:in )?(?:transmissions|communication|samples)",
        r"communication (?:load|cost|overhead)", r"bandwidth",
        r"messages per", r"payload",
    ],
    "e3_energy": [
        r"energy consumption", r"power consumption", r"\bmAh\b", r"\bmW\b",
        r"\bmA\b", r"battery life", r"battery lifetime", r"solar",
        r"photovoltaic", r"\bkWh\b", r"\bJoule\b", r"energy sav",
    ],
    "_article_type": [
        r"^\s*Review\b", r"\bthis review\b", r"\bwe review\b", r"\bsurvey\b",
        r"\bArticle\b", r"\bResearch Article\b", r"\bCommunication\b",
        r"\bproefschrift\b", r"\bthesis\b",
    ],
    "_comparator": [
        r"compared (?:to|with)", r"comparison", r"baseline", r"benchmark",
        r"conventional", r"traditional", r"control group", r"versus",
        r"\bvs\.?\b", r"reference (?:case|scenario)",
    ],
    "_deployment": [
        r"we (?:deployed|installed|implemented|conducted|built)",
        r"field (?:test|trial|experiment)", r"experimental (?:setup|site|greenhouse)",
        r"prototype", r"real[- ]time deployment", r"testbed",
        r"in situ", r"pilot",
    ],
}

MAX_SNIPPETS = 6
WINDOW = 190


def normalise(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text.replace("\u00ad", ""))


def locator_before(text: str, pos: int) -> str:
    """Nearest structural marker preceding pos, plus printed page if visible."""
    head = text[max(0, pos - 4000) : pos]
    marker = ""
    matches = list(SECTION_RE.finditer(head))
    if matches:
        marker = " ".join(matches[-1].group(1).split())[:70]
    page = ""
    pmatches = list(PAGE_RE.finditer(head))
    if pmatches:
        page = f"p.{pmatches[-1].group(1)} of {pmatches[-1].group(2)}"
    parts = [p for p in (marker, page) if p]
    return " | ".join(parts) if parts else "no nearby structural marker"


def snippets_for(text: str, patterns: list[str]) -> list[dict]:
    seen_spans: list[tuple[int, int]] = []
    out: list[dict] = []
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE | re.MULTILINE):
            s, e = m.start(), m.end()
            if any(abs(s - ps) < WINDOW for ps, _ in seen_spans):
                continue
            seen_spans.append((s, e))
            lo = max(0, s - WINDOW // 2)
            hi = min(len(text), e + WINDOW)
            out.append(
                {
                    "hit": m.group(0)[:40],
                    "locator": locator_before(text, s),
                    "text": " ".join(text[lo:hi].split()),
                }
            )
            if len(out) >= MAX_SNIPPETS:
                return out
    return out


def main(ids: list[str]) -> None:
    digest: dict[str, dict] = {}
    for rid in ids:
        path = CACHE / f"{rid}.txt"
        if not path.exists():
            print(f"  !! missing cache for {rid}")
            continue
        raw = normalise(path.read_text(encoding="utf-8", errors="replace"))
        rec = {
            "chars": len(raw),
            "head": " ".join(raw[:900].split()),
            "fields": {},
        }
        for field, pats in PATTERNS.items():
            rec["fields"][field] = snippets_for(raw, pats)
        digest[rid] = rec
        counts = {k: len(v) for k, v in rec["fields"].items() if v}
        print(f"  {rid}: {len(raw):>7} chars, fields with evidence: {len(counts)}")

    out_path = OUT / "evidence_digest.json"
    out_path.write_text(json.dumps(digest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {out_path.relative_to(AUDIT.parent)} for {len(digest)} records")


if __name__ == "__main__":
    ids = sys.argv[1:]
    if not ids:
        print("usage: extract_evidence.py S02 S03 ...")
        raise SystemExit(2)
    main(ids)
