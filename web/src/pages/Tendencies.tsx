import { useEffect, useState } from "react";
import { useStore } from "../store";
import {
  api,
  ApiError,
  SPLITS,
  type Split,
  type TendencyRow,
} from "../api/client";

const SPLIT_LABELS: Record<Split, string> = {
  down_distance: "Down & distance",
  field_zone: "Field zone",
  formation: "Formation",
  motion: "Pre-snap motion",
  quarter: "Quarter",
  hash: "Hash",
};

function RunPassBar({ run, pass }: { run: number; pass: number }) {
  return (
    <div className="bar" title={`Run ${run}% / Pass ${pass}%`}>
      <div className="run" style={{ width: `${run}%` }}>
        <span>{run > 12 ? `${run}%` : ""}</span>
      </div>
      <div className="pass" style={{ width: `${pass}%` }}>
        <span>{pass > 12 ? `${pass}%` : ""}</span>
      </div>
    </div>
  );
}

export default function Tendencies() {
  const { activeTeam } = useStore();
  const [split, setSplit] = useState<Split>("down_distance");
  const [teamFilter, setTeamFilter] = useState("");
  const [rows, setRows] = useState<TendencyRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setError(null);
    setLoading(true);
    try {
      const res = await api.tendencies(
        split,
        teamFilter || null,
        activeTeam?.id ?? null
      );
      setRows(res.rows);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load");
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [split, activeTeam?.id]);

  return (
    <div>
      <h1>Tendencies</h1>
      <p className="subtitle">
        What they like to do, by situation. Formation and motion buckets use the
        active team's vocabulary mapping.
      </p>

      <div className="card">
        <div className="row">
          <div className="field">
            <label>Split by</label>
            <select
              value={split}
              onChange={(e) => setSplit(e.target.value as Split)}
            >
              {SPLITS.map((s) => (
                <option key={s} value={s}>
                  {SPLIT_LABELS[s]}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Offense team filter (optional)</label>
            <input
              value={teamFilter}
              onChange={(e) => setTeamFilter(e.target.value)}
              placeholder="e.g. LINCOLN"
            />
          </div>
          <button className="secondary" onClick={load}>
            Apply
          </button>
        </div>
      </div>

      <div className="card">
        {error && <div className="error">{error}</div>}
        {loading ? (
          <div className="muted">Loading…</div>
        ) : rows.length === 0 ? (
          <div className="muted">
            No plays yet. Upload a breakdown to populate tendencies.
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>{SPLIT_LABELS[split]}</th>
                <th>Plays</th>
                <th>Run / Pass</th>
                <th>Explosive</th>
                <th>Avg EPA</th>
                <th>Top play</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.bucket}>
                  <td>{r.bucket}</td>
                  <td>{r.plays}</td>
                  <td>
                    <RunPassBar run={r.run_pct} pass={r.pass_pct} />
                  </td>
                  <td>{r.explosive_pct}%</td>
                  <td>{r.avg_epa ?? "—"}</td>
                  <td>{r.top_play}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
