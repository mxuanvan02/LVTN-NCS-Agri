# Simulation Code for Networked-Control Benchmark in Smart Agriculture

This directory contains the simulation source code used by the paper:

**Plant--Network--Control--Evaluation Co-Design for Smart Agriculture: A Systematic Evidence Map and Reproducible Networked-Control Benchmark**

The implementation should be interpreted as a **controlled simulation benchmark**, not as field deployment validation. The current plant model is a scalar greenhouse-temperature abstraction. Communication-energy values are modeled communication-energy estimates, not hardware-measured sensor-node energy.

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

## Reproducing all results

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
