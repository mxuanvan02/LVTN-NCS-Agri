# Simulation Code for Networked-Control Benchmark in Smart Agriculture

This directory contains the simulation source code used by the paper:

**Plant--Network--Control--Evaluation Co-Design for Smart Agriculture: A Systematic Evidence Map and Reproducible Networked-Control Benchmark**

The legacy workflow below originated from a scalar greenhouse-temperature abstraction. The authoritative v2 benchmark is different: it contains a synthetic two-state greenhouse model and a synthetic two-layer irrigation bucket model. Neither v2 plant is field calibrated, so results are mechanism-level software evidence rather than deployment validation.

## Version-2 greenhouse + irrigation full-network benchmark

The v2 extension is a separate software-only benchmark. It implements:

- a two-state greenhouse climate abstraction (temperature and relative humidity, 5-minute sample period);
- a two-layer soil-water bucket (root/deep volumetric water content, 30-minute sample period);
- TT/ET × finite-horizon constrained receding-horizon control/PI;
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

Integrity is recorded at two levels:

- `results/v2_output_hashes.json` verifies the frozen 11-file v2 output set (11/11 checked by tests).
- `SHA256SUMS.final.txt` verifies the whole publishable simulation bundle. Regenerate it with `python experiments/regenerate_bundle_manifest.py`; by design it excludes itself, the historical `SHA256SUMS.initial.txt`, `.venv`, caches, bytecode and Git metadata. Verify from the parent `Manuscript/` directory with `sha256sum -c simulation/SHA256SUMS.final.txt`.

Derived reporting is reproducible without rerunning raw primary simulations:

```bash
python experiments/summarize_v2.py
python experiments/report_v2_sensitivity.py
```

The paired table preserves raw p-values and unadjusted 95% paired t intervals. Holm adjustment follows the preregistered four plant–controller-family contrasts: for each network × metric endpoint, the four p-values from 2 plants × 2 controller families are adjusted together. Holm applies to the p-values only; the paired intervals and the three-criterion decision gates are not simultaneous family-wise intervals. The gate table contains both MPC and PI families (24 rows: 2 plants × 2 controller families × 6 networks). Sensitivity summaries are descriptive/exploratory and oracle remains sensitivity-only.

Two preregistered endpoints require cautious interpretation in the frozen primary run. `deadline_miss_pct` is identically zero because the configured deadline is much larger than all simulated end-to-end latencies, so it cannot discriminate policies here. `command_applied_pct` is normalized by each policy's attempted transmissions; because ET and TT intentionally have different denominators, this percentage is not a substitute for the absolute number of commands applied and is not used in the trade-off gate.

The stored `random_tape_sha256` verifies the common process/sensor-noise arrays and the `(seed, plant, network)` key. Channel outcomes are reproducible from deterministic keyed draws, but the digest does not enumerate every channel token and must not be described as a byte-for-byte channel-trace hash.

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
