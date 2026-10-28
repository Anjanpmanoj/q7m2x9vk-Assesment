from datetime import date
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

import analysis as an

app = FastAPI(title="Wind Forecast Monitor API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])

DEFAULT_CUTOFF_HOUR = 9


@lru_cache(maxsize=32)
def _view(cutoff_hour: int):
    return an.day_ahead_view(cutoff_hour)


def _check_date(value: str) -> str:
    try:
        d = date.fromisoformat(value)
    except ValueError:
        raise HTTPException(400, "Dates must look like 2026-01-15")
    if not (date(2026, 1, 1) <= d <= date(2026, 1, 31)):
        raise HTTPException(400, "Only January 2026 is available")
    return value


CutoffHour = Query(DEFAULT_CUTOFF_HOUR, ge=0, le=23, description="UTC hour on D-1 when the buy decision is made")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/meta")
def meta():
    return {"start": "2026-01-01", "end": "2026-01-31", "default_cutoff_hour": DEFAULT_CUTOFF_HOUR}


@app.get("/api/series")
def series(start: str, end: str, cutoff_hour: int = CutoffHour):
    return an.series(_view(cutoff_hour), _check_date(start), _check_date(end))


@app.get("/api/metrics")
def metrics(cutoff_hour: int = CutoffHour):
    df = _view(cutoff_hour)
    return {"summary": an.summarize(df), "by_hour": an.by_hour(df)}


@app.get("/api/decision")
def decision(delivery_date: str, cutoff_hour: int = CutoffHour):
    return an.daily_volume_band(_view(cutoff_hour), _check_date(delivery_date))


@lru_cache(maxsize=1)
def _horizon():
    return an.horizon_curve(48, 1)


@app.get("/api/horizon")
def horizon():
    return _horizon()
