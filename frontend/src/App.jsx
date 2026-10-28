import { useEffect, useState } from "react";
import {
  Area, Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { get } from "./api.js";

const C = { actual: "#16262e", forecast: "#0b7f8c", band: "#0b7f8c", error: "#4b4fb3", grid: "#d6dfdd" };
const fmt = (n, d = 0) => (n == null ? "–" : Number(n).toLocaleString("en-GB", { maximumFractionDigits: d }));
const tz = "Europe/London";
const timeLabel = (iso) => new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: tz });
const dayLabel = (iso) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: tz });
const stampLabel = (iso) =>
  iso ? new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: tz }) : "–";

function useApi(path, params) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const key = path + JSON.stringify(params);
  useEffect(() => {
    let live = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    get(path, params)
      .then((data) => live && setState({ data, error: null, loading: false }))
      .catch((error) => live && setState({ data: null, error: error.message, loading: false }));
    return () => { live = false; };
  }, [key]);
  return state;
}

function Stat({ label, value, unit, note }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}<span className="stat-unit">{unit}</span></div>
      {note && <div className="stat-note">{note}</div>}
    </div>
  );
}

function Panel({ title, sub, children, state }) {
  return (
    <section className="panel">
      <header><h2>{title}</h2>{sub && <p>{sub}</p>}</header>
      {state?.error ? <p className="error">{state.error}</p> : state?.loading && !state.data ? <p className="muted">Loading…</p> : children}
    </section>
  );
}

const MwTick = (v) => `${fmt(v / 1000, 1)}k`;

export default function App() {
  const [cutoff, setCutoff] = useState(9);
  const [date, setDate] = useState("2026-01-15");

  const decision = useApi("decision", { delivery_date: date, cutoff_hour: cutoff });
  const day = useApi("series", { start: date, end: date, cutoff_hour: cutoff });
  const month = useApi("series", { start: "2026-01-01", end: "2026-01-31", cutoff_hour: cutoff });
  const metrics = useApi("metrics", { cutoff_hour: cutoff });
  const horizon = useApi("horizon", {});

  const s = metrics.data?.summary;
  const d = decision.data;
  const dayRows = (day.data || []).map((r) => ({ ...r, span: r.lower != null ? r.upper - r.lower : null }));

  return (
    <main>
      <header className="top">
        <div>
          <h1>Wind forecast monitor</h1>
          <p>What the wind forecast said when you had to buy day-ahead power, and how far off it has been. National GB wind, Elexon data, January 2026.</p>
        </div>
        <div className="controls">
          <label>Delivery day
            <input type="date" min="2026-01-01" max="2026-01-31" value={date} onChange={(e) => e.target.value && setDate(e.target.value)} />
          </label>
          <label>Decision made at
            <select value={cutoff} onChange={(e) => setCutoff(Number(e.target.value))}>
              {[6, 7, 8, 9, 10, 11, 12].map((h) => (
                <option key={h} value={h}>{String(h).padStart(2, "0")}:00 the day before</option>
              ))}
            </select>
          </label>
        </div>
      </header>

      <Panel title={`Forecast for ${dayLabel(date + "T12:00:00Z")}`} sub="Latest forecast available at your decision time. The shaded range is where actual wind has landed 80% of the time historically." state={decision.error ? decision : day}>
        <div className="stats">
          <Stat label="Expected wind output" value={fmt(d?.forecast_mwh)} unit=" MWh" note={`Forecast published ${stampLabel(d?.latest_publish_time)}`} />
          <Stat label="Likely range (80%)" value={`${fmt(d?.low_mwh)}–${fmt(d?.high_mwh)}`} unit=" MWh" note={`Based on ${d?.days_used_for_band ?? "–"} days of daily errors`} />
          <Stat label="What actually happened" value={fmt(d?.actual_mwh)} unit=" MWh" note="For comparison, after delivery" />
        </div>
        <div className="chart tall">
          <ResponsiveContainer>
            <ComposedChart data={dayRows} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
              <CartesianGrid stroke={C.grid} vertical={false} />
              <XAxis dataKey="time" tickFormatter={timeLabel} minTickGap={40} />
              <YAxis tickFormatter={MwTick} label={{ value: "MW", angle: -90, position: "insideLeft" }} />
              <Tooltip labelFormatter={timeLabel} formatter={(v, n) => (n === "span" ? null : [`${fmt(v)} MW`, n])} />
              <Legend />
              <Area dataKey="lower" stackId="b" stroke="none" fill="none" legendType="none" name="lower" />
              <Area dataKey="span" stackId="b" stroke="none" fill={C.band} fillOpacity={0.16} name="80% range" />
              <Line dataKey="forecast" name="Forecast" stroke={C.forecast} strokeWidth={2.5} dot={false} />
              <Line dataKey="actual" name="Actual" stroke={C.actual} strokeWidth={2} strokeDasharray="5 4" dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      <Panel title="How accurate has the forecast been?" sub="All of January, using the forecast available at your decision time. Error = actual minus forecast, so a positive bias means wind came in higher than forecast." state={metrics}>
        <div className="stats five">
          <Stat label="Typical miss (MAE)" value={fmt(s?.mae)} unit=" MW" />
          <Stat label="Large misses (RMSE)" value={fmt(s?.rmse)} unit=" MW" />
          <Stat label="Bias" value={fmt(s?.bias)} unit=" MW" note={s?.bias > 0 ? "Wind beat forecast" : "Wind fell short"} />
          <Stat label="Error vs output" value={fmt(s?.wmape_pct, 1)} unit="%" note="Weighted by generation" />
          <Stat label="9 in 10 slots within" value={fmt(s?.p90_abs)} unit=" MW" note={`Worst 1%: over ${fmt(s?.p99_abs)} MW`} />
        </div>
        <div className="chart">
          <ResponsiveContainer>
            <LineChart data={month.data || []} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
              <CartesianGrid stroke={C.grid} vertical={false} />
              <XAxis dataKey="time" tickFormatter={dayLabel} minTickGap={50} />
              <YAxis tickFormatter={MwTick} />
              <Tooltip labelFormatter={(v) => `${dayLabel(v)} ${timeLabel(v)}`} formatter={(v) => `${fmt(v)} MW`} />
              <Legend />
              <Line dataKey="forecast" name="Forecast" stroke={C.forecast} dot={false} strokeWidth={1.5} />
              <Line dataKey="actual" name="Actual" stroke={C.actual} dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      <div className="two">
        <Panel title="Error by forecast lead time" sub="Average miss (MW) for the forecast published this many hours before the target time. Shorter lead time should mean a smaller miss." state={horizon}>
          <div className="chart">
            <ResponsiveContainer>
              <LineChart data={horizon.data || []} margin={{ top: 8, right: 16, bottom: 16, left: 0 }}>
                <CartesianGrid stroke={C.grid} vertical={false} />
                <XAxis dataKey="horizon" label={{ value: "Hours before target", position: "insideBottom", offset: -8 }} />
                <YAxis tickFormatter={MwTick} />
                <Tooltip labelFormatter={(h) => `${h}h ahead`} formatter={(v) => `${fmt(v)} MW`} />
                <Line dataKey="mae" name="MAE" stroke={C.error} strokeWidth={2.5} dot={false} />
                <Line dataKey="rmse" name="RMSE" stroke={C.forecast} strokeWidth={1.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>
        <Panel title="Error by time of day" sub="Average miss (MW) for each hour of the delivery day." state={metrics}>
          <div className="chart">
            <ResponsiveContainer>
              <BarChart data={metrics.data?.by_hour || []} margin={{ top: 8, right: 16, bottom: 16, left: 0 }}>
                <CartesianGrid stroke={C.grid} vertical={false} />
                <XAxis dataKey="hour" label={{ value: "Hour of day (UK)", position: "insideBottom", offset: -8 }} />
                <YAxis tickFormatter={MwTick} />
                <Tooltip formatter={(v) => `${fmt(v)} MW`} />
                <Bar dataKey="mae" name="MAE" fill={C.error} radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>

      <footer>
        Decision time is an assumption you can change above (UTC equals UK time in January). The range comes from the same January data it is scored on, so treat it as a guide, not a guarantee.
      </footer>
    </main>
  );
}
