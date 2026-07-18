"""Streamlit dashboard for GridCast demand forecasts.

Deliberately thin: no model or feature logic here, just calls the FastAPI
service (src/api/main.py) and renders whatever /forecast returns. Respondent
options come from config/data_ingestion.config (the same regions the
ingestion pipeline is configured for) rather than being hardcoded again.
"""

from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st

from src.ingestion.data_ingestion import load_config

API_URL = os.environ.get("GRIDCAST_API_URL", "http://localhost:8000")

st.set_page_config(page_title="GridCast", layout="centered")
st.title("GridCast -- Demand Forecast")

config = load_config()
respondent = st.selectbox("Respondent", config.regions)

if st.button("Get forecast", type="primary"):
    response = requests.get(f"{API_URL}/forecast", params={"respondent": respondent})

    if response.status_code != 200:
        st.error(response.json().get("detail", response.text))
    else:
        data = response.json()
        forecasts = pd.DataFrame(data["forecasts"])

        st.caption(f"As of {data['origin_hour_utc']} (UTC)")
        st.line_chart(forecasts.set_index("horizon")["predicted_demand_mwh"])
        st.dataframe(forecasts, hide_index=True)
