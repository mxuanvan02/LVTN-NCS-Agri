#!/bin/bash
# Master script for the canonical causal legacy benchmark and the v2 extension.
# Deprecated look-ahead scripts are intentionally excluded.

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

# 3. Generate weather-conditioned synthetic packet-status trace
 echo "[3/8] Generating weather-conditioned synthetic packet-status trace..."
python3 data/fetch_network_trace.py

# Legacy scripts run_ablation.py, run_q1_eval*.py are excluded because they
# contain future-weather look-ahead and inconsistent APIs.  The causal legacy
# benchmark is retained only for provenance.
echo "[4/8] Running causal scalar provenance benchmark..."
python3 experiments/run_q1_benchmark.py

# Version-2 confirmatory extension.
echo "[5/8] Validating v2 manifest..."
python3 experiments/run_v2_primary.py --dry-run
echo "[6/8] Running v2 greenhouse/irrigation benchmark..."
python3 experiments/run_v2_primary.py --seeds 50
echo "[7/8] Running SIL/HIL-ready loopback..."
python3 experiments/run_v2_hil_loopback.py
echo "[8/8] Regenerating v2 inference and figure..."
python3 experiments/summarize_v2.py
python3 experiments/plot_v2.py


echo "=================================================="
echo "All experiments completed successfully!"
echo "Check the 'results/' directory for all generated figures."
echo "=================================================="

