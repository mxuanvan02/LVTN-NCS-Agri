#!/bin/bash
# Master script to reproduce all simulation results from the paper.
# It ensures code quality via tests before running time-consuming experiments.

# Exit immediately if a command exits with a non-zero status.
set -e

echo "=================================================="
echo " Starting Full Simulation & Verification Pipeline "
echo "=================================================="

# 1. Verify Code Quality with Automated Tests
echo "[1/6] Verifying code quality with Pytest..."
python3 -m pytest -v

# 2. Fetch Vietnam Dataset (Real ERA5 Data)
echo "[2/6] Fetching Real Mekong Delta Dataset (ERA5 Reanalysis)..."
python3 data/fetch_real_vn_data.py

# 3. Generate Empirical Network Trace
echo "[3/6] Fetching/Synthesizing Empirical LoRaWAN Network Trace..."
python3 data/fetch_network_trace.py

# 4. Run Ablation Study
echo "[4/6] Running Ablation Study..."
python3 experiments/run_ablation.py

# 5. Run Main Q1 Evaluation (Nominal Conditions)
echo "[5/6] Running Main Q1 Evaluation (Nominal Conditions)..."
python3 experiments/run_q1_eval.py

# 6. Run multi-scenario benchmark used for the manuscript summary table
echo "[6/7] Running Multi-Scenario Benchmark Table Generation..."
python3 experiments/run_q1_benchmark.py

# 7. Run Q1 Evaluation (Extreme Conditions & Long Horizon)
echo "[7/7] Running Q1 Evaluation (Extreme & Long Horizon)..."
python3 experiments/run_q1_eval_extreme.py
python3 experiments/run_q1_eval_real_long.py


echo "=================================================="
echo "All experiments completed successfully!"
echo "Check the 'results/' directory for all generated figures."
echo "=================================================="

