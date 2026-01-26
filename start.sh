#!/bin/bash
set -e

echo "Starting Legislatie API monitoring server..."
python -m monitoring --host 0.0.0.0 --port 9090 --health-check-interval 300 &

echo "Starting Streamlit application..."
exec streamlit run streamlit_app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true