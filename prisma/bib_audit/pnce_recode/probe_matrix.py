#!/usr/bin/env python3
"""Deterministic discriminating-probe matrix over the 34 cached full texts.

This does NOT assign coded values. It answers narrow yes/no questions with hit
counts so a human coder can adjudicate every field quickly and consistently,
and so that the same question is asked of every record in the same way.

Reference sections are excluded before probing, because the pass-1 extractor
produced false positives from bibliography entries (e.g. S06 matched "LoRa" and
"greenhouse" inside cited titles).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE.parent / "fulltext_cache"

REF_HEAD = re.compile(
    r"(?m)^\s*(?:References|REFERENCES|Bibliography|Literature Cited|"
    r"References and Notes)\s*$"
)


def body_only(text: str) -> str:
    """Drop the bibliography tail so citation titles cannot create hits."""
    marks = [m.start() for m in REF_HEAD.finditer(text)]
    if marks:
        cut = marks[-1]
        # only trust a late cut (bibliography is at the end)
        if cut > 0.45 * len(text):
            return text[:cut]
    return text


PROBES: dict[str, re.Pattern] = {
    # application
    "greenhouse_enclosure": re.compile(
        r"\b(?:in|inside|within)\s+(?:the\s+|a\s+|an\s+|our\s+)?greenhouse\b"
        r"|\bgreenhouse\s+(?:climate|microclimate|compartment|experiment|air|cover)\b",
        re.I),
    "open_field_irrigation": re.compile(
        r"\b(?:drip|sprinkler|furrow|paddy|field|farmland|open[- ]field)\s+irrigation\b"
        r"|\balternate wetting and drying\b|\bAWD\b", re.I),
    "hydroponic_cea": re.compile(
        r"\b(?:hydroponic\w*|aeroponic\w*|soilless|nutrient film|NFT\b|"
        r"controlled[- ]environment agriculture)\b", re.I),
    "nonag_plant": re.compile(
        r"\b(?:VTOL|aircraft|inverted pendulum|quadrotor|spacecraft|"
        r"batch reactor|CSTR|academic example)\b", re.I),
    # protocol
    "lorawan": re.compile(r"\bLoRaWAN\b"),
    "lora_phy": re.compile(r"\bLoRa\b(?!WAN)"),
    "zigbee": re.compile(r"\b(?:ZigBee|Zig[- ]Bee|802\.15\.4|XBee)\b", re.I),
    "wifi": re.compile(r"\b(?:Wi[- ]?Fi|802\.11|ESP8266|ESP32|NodeMCU)\b", re.I),
    "cellular": re.compile(r"\b(?:NB[- ]IoT|LTE[- ]M|GSM|GPRS|SIM800|SIM900|\b4G\b|\b5G\b)"),
    "wired": re.compile(r"\b(?:switched Ethernet|Ethernet|Modbus|RS[- ]?485|CAN bus|PROFINET)\b", re.I),
    "mqtt_coap": re.compile(r"\b(?:MQTT|CoAP)\b"),
    # control strategy
    "mpc": re.compile(r"\b(?:model predictive control|\bMPC\b|NMPC|DMPC|EMPC)\b"),
    "pid": re.compile(r"\b(?:PID|PI)\s+(?:controller|control|regulator)\b"),
    "fuzzy": re.compile(r"\bfuzzy\b", re.I),
    "rl_ml": re.compile(r"\b(?:reinforcement learning|Q[- ]learning|\bSAC\b|\bDDPG\b|\bPPO\b|"
                        r"random forest|neural network|machine learning)\b", re.I),
    "threshold": re.compile(r"\b(?:threshold|set[- ]?point|on[-/ ]off|hysteresis|bang[- ]bang)\b", re.I),
    "optimal_control": re.compile(r"\boptimal control\b", re.I),
    "etc": re.compile(r"\bevent[- ]triggered\b", re.I),
    "stc": re.compile(r"\bself[- ]triggered\b", re.I),
    "monitoring_only": re.compile(r"\bmonitoring\s+(?:system|platform|only)\b", re.I),
    # trigger / architecture
    "periodic": re.compile(r"\b(?:time[- ]triggered|periodic\w*\s+sampl\w+|fixed\s+sampling|"
                           r"every\s+\d+\s*(?:s|sec|seconds|min|minutes|hours?))\b", re.I),
    "remote_manual": re.compile(r"\b(?:remotely|remote)\s+(?:control|monitor|actuat|trigger|switch|turn)", re.I),
    "cloud": re.compile(r"\b(?:cloud|ThingSpeak|Firebase|Blynk|AWS|Azure)\b", re.I),
    "edge_fog": re.compile(r"\b(?:edge|fog)\s+(?:computing|node|gateway|layer|server)\b", re.I),
    "embedded": re.compile(r"\b(?:Arduino|Raspberry Pi|STM32|ESP32|microcontroller|\bPLC\b)\b", re.I),
    # evidence type
    "field_trial": re.compile(r"\b(?:field|on[- ]farm|on[- ]site)\s+(?:trial|experiment|test|deployment)\b", re.I),
    "we_deployed": re.compile(r"\b(?:we|authors?)\s+(?:deployed|installed|implemented|built|conducted|performed)\b", re.I),
    "gh_experiment": re.compile(r"\b(?:greenhouse|plot|field)\s+experiment\b", re.I),
    "prototype": re.compile(r"\b(?:prototype|testbed|test bench|lab(?:oratory)?[- ]scale|"
                            r"hardware[- ]in[- ]the[- ]loop|\bHIL\b)\b", re.I),
    "sim_tool": re.compile(r"\b(?:MATLAB|Simulink|Riverbed|OMNeT|NS-?[23]|CasADi|IPOPT|GRAMPC|Xpress|TrueTime)\b"),
    "sim_results": re.compile(r"\bsimulat\w+\s+(?:results?|study|studies|scenario|run)\b", re.I),
    # article type
    "mdpi_review_label": re.compile(r"(?m)^\s*(?:sensors|applied sciences|agronomy|electronics|"
                                    r"actuators|energies|agriculture)\s+Review\s*$", re.I),
    "self_review": re.compile(r"\bthis\s+(?:review|survey)\b", re.I),
    "research_article_label": re.compile(r"\b(?:RESEARCH ARTICLE|Original Article)\b"),
    # comparator / outcomes
    "compared_with": re.compile(r"\bcompared?\s+(?:with|to|against)\b", re.I),
    "baseline_word": re.compile(r"\b(?:baseline|benchmark|control group|conventional|traditional)\b", re.I),
    "err_metric": re.compile(r"\b(?:RMSE|MAE|IAE|ISE|overshoot|settling time|steady[- ]state error|"
                             r"tracking error|MAPE)\b", re.I),
    "water_or_yield": re.compile(r"\b(?:water\s+(?:sav\w+|use|consumption)|yield|dry weight)\b", re.I),
    "tx_reduction": re.compile(r"\b(?:transmissions?|packets?|samples?|messages?|updates?)\b[^.\n]{0,40}"
                               r"\b(?:reduc\w+|sav\w+|fewer|decreas\w+)\b", re.I),
    "loss_delay_metric": re.compile(r"\b(?:packet\s+(?:loss|delivery)|PDR\b|PLR\b|RSSI|SNR|"
                                    r"end[- ]to[- ]end delay|latency)\b", re.I),
    "energy_metric": re.compile(r"\b(?:energy|power)\s+(?:consumption|saving|usage|efficiency)\b"
                                r"|\b(?:mAh|kWh|\bWh\b|battery\s+life)\b", re.I),
}


def main() -> None:
    ids = sorted((p.stem for p in CACHE.glob("S*.txt")), key=lambda s: int(s[1:]))
    matrix: dict[str, dict[str, int]] = {}
    for rid in ids:
        raw = (CACHE / f"{rid}.txt").read_text(encoding="utf-8", errors="ignore")
        text = re.sub(r"[ \t]+", " ", raw.replace("\r", "\n"))
        body = body_only(text)
        matrix[rid] = {name: len(pat.findall(body)) for name, pat in PROBES.items()}
        matrix[rid]["_body_chars"] = len(body)
        matrix[rid]["_full_chars"] = len(text)

    (HERE / "probe_matrix.json").write_text(
        json.dumps(matrix, indent=1, ensure_ascii=False), encoding="utf-8")

    groups = [
        ("APPLICATION", ["greenhouse_enclosure", "open_field_irrigation", "hydroponic_cea", "nonag_plant"]),
        ("PROTOCOL", ["lorawan", "lora_phy", "zigbee", "wifi", "cellular", "wired", "mqtt_coap"]),
        ("STRATEGY", ["mpc", "pid", "fuzzy", "rl_ml", "threshold", "optimal_control", "etc", "stc", "monitoring_only"]),
        ("TRIGGER/ARCH", ["periodic", "remote_manual", "cloud", "edge_fog", "embedded"]),
        ("EVIDENCE", ["field_trial", "we_deployed", "gh_experiment", "prototype", "sim_tool", "sim_results"]),
        ("TYPE", ["mdpi_review_label", "self_review", "research_article_label"]),
        ("OUTCOMES", ["compared_with", "baseline_word", "err_metric", "water_or_yield",
                      "tx_reduction", "loss_delay_metric", "energy_metric"]),
    ]
    for title, cols in groups:
        print("=" * 100)
        print(title)
        print("ID   " + "".join(c[:11].rjust(12) for c in cols))
        for rid in ids:
            print(rid.ljust(5) + "".join(str(matrix[rid][c]).rjust(12) for c in cols))
    print()
    print("wrote probe_matrix.json")


if __name__ == "__main__":
    main()
