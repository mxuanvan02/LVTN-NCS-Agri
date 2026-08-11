# Simulation Code for Networked-Control Benchmark in Smart Agriculture

This directory contains the simulation source code used by the paper:

**Plant--Network--Control--Evaluation Co-Design for Smart Agriculture: A Systematic Evidence Map and Reproducible Networked-Control Benchmark**

The implementation should be interpreted as a **controlled simulation benchmark**, not as field deployment validation. The current plant model is a scalar greenhouse-temperature abstraction. Communication-energy values are modeled communication-energy estimates, not hardware-measured sensor-node energy.

## Version-2 greenhouse + irrigation full-network benchmark

The v2 extension is a separate software-only benchmark. It implements:

- a two-state greenhouse climate abstraction (temperature and relative humidity, 5-minute sample period);
- a two-layer soil-water bucket (root/deep volumetric water content, 30-minute sample period);
- TT/ET × one-step constrained receding-horizon control/PI;
- six two-way network profiles with keyed common random tapes, uplink/downlink loss, delay, jitter, burst state, serialization, contention, finite-queue proxy, duty waiting, ACK loss/retry, computation latency and actuator deadlines;
- separate modeled TX/RX/listen/retry/compute/baseline/actuation-proxy energy components;
- in-process, JSONL and UDP-loopback HIL-ready schemas (software-in-the-loop only; no physical HIL claim).

Plant coefficients and network/energy parameters are declared synthetic benchmark assumptions, not field calibration or hardware measurements. The preregistration is `preregistration_v2.yaml`; exact assumptions are in `configs_v2.yaml`.

Run the complete v2 workflow:

```bash
python -m pytest -q
python experiments/run_v2_primary.py --dry-run
python experiments/run_v2_primary.py --seeds 50
python experiments/run_v2_hil_loopback.py
python experiments/summarize_v2.py
python experiments/plot_v2.py
```

Primary outputs use a `v2_` prefix, preserving all legacy artifacts. `v2_run_manifest.csv` accounts for every scheduled run. `v2_primary_raw.csv`, `v2_primary_summary.csv`, `v2_primary_paired.csv`, `v2_decision_gates.csv`, `v2_sensitivity_raw.csv`, event logs and hashes permit raw-to-summary regeneration. Oracle forecast rows occur only in sensitivity output.

## Prerequisites

- Python 3.9+
- `pip` for package management

## Setup

Create and activate a virtual environment, then install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Data preparation

The simulation uses weather data and a weather-conditioned packet-loss trace. Run:

```bash
python data/fetch_real_vn_data.py
python data/fetch_network_trace.py
```

Important terminology note: `data/fetch_network_trace.py` generates a **weather-conditioned synthetic LoRa packet-status trace** from weather-driven heuristics. It should not be described as an empirical field-measured LoRa trace unless measured packet logs are added.

## Reproducing legacy results

From this `simulation/` directory, run:

```bash
./run_all.sh
```

The script performs the following steps:

1. Runs unit tests with `pytest`.
2. Fetches/prepares weather data.
3. Generates the weather-conditioned synthetic LoRa trace.
4. Runs ablation experiments.
5. Runs nominal Q1 evaluation figures.
6. Runs the multi-scenario benchmark table generation (`run_q1_benchmark.py`).
7. Runs extreme and long-horizon evaluation figures.

Expected outputs are written to `results/`.

## Code-to-paper traceability

| Paper artefact | Generating script | Output file(s) |
|---|---|---|
| Ablation / baseline figure | `experiments/run_ablation.py` | `results/ablation_study.pdf` |
| Nominal evaluation figure | `experiments/run_q1_eval.py` | `results/q1_eval.pdf` |
| Multi-scenario benchmark table | `experiments/run_q1_benchmark.py` | `results/q1_benchmark_raw.csv`, `results/q1_benchmark_summary.csv` |
| Extreme-condition figure | `experiments/run_q1_eval_extreme.py` | `results/q1_eval_extreme.pdf` |
| Long-horizon real-weather figure | `experiments/run_q1_eval_real_long.py` | `results/q1_eval_real_long.pdf` |

## Metric definitions

- **RMSE / IAE:** closed-loop tracking error relative to the temperature setpoint.
- **Transmission rate:** attempted transmissions divided by simulation steps.
- **Packet-loss percentage:** in `run_q1_benchmark.py`, losses are counted over attempted transmissions. If other scripts report channel loss, distinguish it from attempted-transmission loss.
- **Energy (mJ):** modeled communication energy computed from declared `E_tx` and `E_sleep` constants. It is not a measured hardware energy value.
- **Violation percentage:** fraction of steps outside the defined control-error tolerance.

## Project structure

```text
├── data/                 # Weather data and generated packet-status traces
├── experiments/          # Experiment scripts for figures and benchmark tables
├── results/              # Generated figures and CSV outputs
├── src/                  # Core plant, controller, trigger, channel and energy models
├── tests/                # Unit tests
├── README.md             # This file
├── requirements.txt      # Python dependencies
└── run_all.sh            # Master reproduction script
```
