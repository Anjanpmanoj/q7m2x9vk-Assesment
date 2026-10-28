"""Core analysis: pick the forecast a trader actually had, then measure its error.

error = actual - forecast   (positive = wind under-forecast, i.e. more wind than expected)
"""
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
UTC_NS = "datetime64[ns, UTC]"


def _utc(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, utc=True).astype(UTC_NS)


@lru_cache(maxsize=1)
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    actuals = pd.read_csv(DATA_DIR / "actuals.csv")
    forecasts = pd.read_csv(DATA_DIR / "forecasts.csv")
    actuals["startTime"] = _utc(actuals["startTime"])
    forecasts["startTime"] = _utc(forecasts["startTime"])
    forecasts["publishTime"] = _utc(forecasts["publishTime"])
    actuals = actuals.drop_duplicates("startTime", keep="last")
    forecasts = forecasts.drop_duplicates(["startTime", "publishTime"], keep="last")
    return actuals, forecasts


def _join_latest(actuals: pd.DataFrame, forecasts: pd.DataFrame, cutoff: pd.Series) -> pd.DataFrame:
    """For every target time, attach the latest forecast published at or before `cutoff`."""
    left = actuals[["startTime", "generation"]].rename(columns={"generation": "actual"}).copy()
    left["cutoff"] = cutoff.astype(UTC_NS)
    left = left.sort_values("cutoff")
    right = forecasts.rename(columns={"generation": "forecast"}).sort_values("publishTime")
    out = pd.merge_asof(
        left, right, left_on="cutoff", right_on="publishTime", by="startTime", direction="backward"
    )
    out["error"] = out["actual"] - out["forecast"]
    return out.sort_values("startTime").reset_index(drop=True)


def day_ahead_view(cutoff_hour: int = 9) -> pd.DataFrame:
    """Forecast available at `cutoff_hour` UTC on the day BEFORE each delivery day (UK = UTC in January)."""
    actuals, forecasts = load_data()
    cutoff = actuals["startTime"].dt.normalize() - pd.Timedelta(days=1) + pd.Timedelta(hours=cutoff_hour)
    return _join_latest(actuals, forecasts, cutoff)


def horizon_view(horizon_h: float) -> pd.DataFrame:
    """Latest forecast published at least `horizon_h` hours before the target time."""
    actuals, forecasts = load_data()
    cutoff = actuals["startTime"] - pd.Timedelta(hours=horizon_h)
    return _join_latest(actuals, forecasts, cutoff)


def summarize(df: pd.DataFrame) -> dict:
    d = df.dropna(subset=["forecast"])
    if d.empty:
        return {"n": 0, "missing": int(len(df))}
    err, abs_err = d["error"], d["error"].abs()
    return {
        "n": int(len(d)),
        "missing": int(len(df) - len(d)),
        "mae": float(abs_err.mean()),
        "rmse": float(np.sqrt((err**2).mean())),
        "bias": float(err.mean()),
        "wmape_pct": float(abs_err.sum() / d["actual"].sum() * 100) if d["actual"].sum() else None,
        "p50_abs": float(abs_err.quantile(0.5)),
        "p90_abs": float(abs_err.quantile(0.9)),
        "p99_abs": float(abs_err.quantile(0.99)),
        "mean_actual": float(d["actual"].mean()),
    }


def by_hour(df: pd.DataFrame) -> list[dict]:
    d = df.dropna(subset=["forecast"]).copy()
    d["hour"] = d["startTime"].dt.hour
    d["abs_error"] = d["error"].abs()
    g = d.groupby("hour")
    out = pd.DataFrame(
        {
            "mae": g["abs_error"].mean(),
            "bias": g["error"].mean(),
            "p10": g["error"].quantile(0.1),
            "p90": g["error"].quantile(0.9),
        }
    ).reset_index()
    return out.round(1).to_dict("records")


def series(df: pd.DataFrame, start: str, end: str) -> list[dict]:
    """Rows for target dates start..end inclusive, with an error band from hour-of-day error quantiles."""
    bands = {r["hour"]: r for r in by_hour(df)}
    s = pd.Timestamp(start, tz="UTC")
    e = pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
    d = df[(df["startTime"] >= s) & (df["startTime"] < e)]
    rows = []
    for r in d.itertuples():
        fc = None if pd.isna(r.forecast) else float(r.forecast)
        b = bands.get(r.startTime.hour)
        rows.append(
            {
                "time": r.startTime.isoformat(),
                "actual": float(r.actual),
                "forecast": fc,
                "publish_time": None if pd.isna(r.publishTime) else r.publishTime.isoformat(),
                "lower": None if fc is None or not b else max(0.0, fc + b["p10"]),
                "upper": None if fc is None or not b else fc + b["p90"],
            }
        )
    return rows


def daily_volume_band(df: pd.DataFrame, delivery_date: str) -> dict:
    """Expected MWh for a delivery day, with a range from historical daily-total errors."""
    d = df.dropna(subset=["forecast"]).copy()
    d["date"] = d["startTime"].dt.date
    daily_err = d.groupby("date")["error"].sum() * 0.5  # MW x 0.5h = MWh
    day = d[d["date"] == pd.Timestamp(delivery_date).date()]
    fc_mwh = float(day["forecast"].sum() * 0.5)
    act_mwh = float(day["actual"].sum() * 0.5)
    p10, p90 = float(daily_err.quantile(0.1)), float(daily_err.quantile(0.9))
    return {
        "date": delivery_date,
        "forecast_mwh": fc_mwh,
        "actual_mwh": act_mwh,
        "low_mwh": max(0.0, fc_mwh + p10),
        "high_mwh": fc_mwh + p90,
        "latest_publish_time": day["publishTime"].max().isoformat() if len(day) else None,
        "slots": int(len(day)),
        "days_used_for_band": int(len(daily_err)),
    }


def horizon_curve(max_h: int = 48, step: int = 1) -> list[dict]:
    rows = []
    for h in range(0, max_h + 1, step):
        s = summarize(horizon_view(h))
        if s["n"]:
            rows.append({"horizon": h, "mae": s["mae"], "rmse": s["rmse"], "bias": s["bias"], "n": s["n"]})
    return rows
