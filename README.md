# Wind Forecast Monitor

Web app for a UK energy utility's day-ahead buying desk. It shows (1) the latest national wind forecast available when the buy decision is made and (2) how accurate those forecasts have been, using Elexon data for January 2026 only (FUELHH actuals with fuelType WIND, WINDFOR forecasts).

**Live app:** <ADD VERCEL LINK>

> **AI disclosure:** This project was built with help from an AI assistant (Claude by Anthropic) for code generation. I reviewed, ran and understood the code.

## Key idea
For each half-hour target time, the app picks the **latest forecast published at or before the decision time** (default 09:00 on the day before delivery, configurable in the UI) and compares it with actual generation. `error = actual - forecast`. In January UK time equals UTC, so no timezone conversion is needed in the analysis.

Metrics: MAE, RMSE, bias, weighted MAPE, P50/P90/P99 absolute error, error by hour of day, error by forecast lead time (0 to 48 h). The 80% range on the chart uses the P10/P90 of historical error for that hour (and of daily total error for the MWh range).

## Files
```
backend/analysis.py        forecast selection (merge_asof) + all metrics
backend/main.py            FastAPI endpoints (/api/series, /metrics, /decision, /horizon, /meta, /health)
backend/data/              actuals.csv, forecasts.csv (downloaded snapshot of Elexon data)
backend/tests/             pytest unit tests for the selection and metric logic
backend/Dockerfile
frontend/src/App.jsx       dashboard (React + Recharts)
frontend/src/api.js        API helper
frontend/Dockerfile        builds the app, serves it with nginx and proxies /api to the backend
scripts/fetch_data.py      downloads data from the Elexon API into backend/data
docker-compose.yml         runs backend + frontend
```

## Run with Docker
```
docker compose up --build
```
Open http://localhost:3000 (API on http://localhost:8000/docs).

## Run without Docker
```
# backend
cd backend && pip install -r requirements-dev.txt
python -m pytest
uvicorn main:app --reload --port 8000

# frontend (new terminal)
cd frontend && npm install && npm run dev      # http://localhost:5173
```

## Refresh the data
```
pip install -r backend/requirements.txt
python scripts/fetch_data.py
```

## Deploy on Vercel (two projects from the same repo)
1. Backend: import the repo, set Root Directory to `backend`. Vercel detects the FastAPI app in `main.py`.
2. Frontend: import the repo again, Root Directory `frontend`, add env var `VITE_API_URL` = the backend URL (no trailing slash).
3. Put the frontend URL in the "Live app" line above.

## Assumptions and limitations
- Decision time defaults to 09:00 the day before delivery. This is an assumption, so it is adjustable in the UI.
- The error range is computed from the same January data it is evaluated on, so it is descriptive, not a proper out-of-sample prediction interval.
- National-level wind only, no other data sources.

## Live links
- **Frontend (app):** https://q7m2x9vk-assesment-o28l.vercel.app/
- **Backend health check:** https://q7m2x9vk-assesment.vercel.app/api/health
- **API docs (Swagger):** https://q7m2x9vk-assesment.vercel.app/docs 
