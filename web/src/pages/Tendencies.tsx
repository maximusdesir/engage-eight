import { useEffect, useState } from "react";
import { useStore } from "../useStore";
import {
  api,
  ApiError,
  SPLITS,
  type Split,
  type TendencyRow,
} from "../api/client";
import PageHead, { NeedsTeam } from "../components/PageHead";

const SPLIT_LABELS: Record<Split, string> = {
  down_distance: "Down & distance",
  field_zone: "Field zone",
  formation: "Formation",
  motion: "Pre-snap motion",
  quarter: "Quarter",
  hash: "Hash",
};

function RunPassBar({ run, pass }: { run: number; pass: number }) {
  // flex-grow by share, so the gap never pushes the bar past its column, and
  // an empty side draws nothing (no sliver of red on a 100% run row).
  return (
    <>
      <div className="rp" role="img" aria-label={`Run ${run}%, pass ${pass}%`}>
        {run > 0 && (
          <span className="rp-run" style={{ flexGrow: run }}>
            {run >= 15 ? `${Math.round(run)}%` : ""}
          </span>
        )}
        {pass > 0 && (
          <span className="rp-pass" style={{ flexGrow: pass }}>
            {pass >= 15 ? `${Math.round(pass)}%` : ""}
          </span>
        )}
      </div>
      {/* Phones: the bar is too narrow for numbers inside it. */}
      <small className="rp-note" aria-hidden="true">
        {Math.round(pass)}% pass
      </small>
    </>
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
    if (!activeTeam) return;
    setError(null);
    setLoading(true);
    try {
      const res = await api.tendencies(activeTeam.id, split, teamFilter || null);
      setRows(res.rows);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load tendencies.");
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [split, activeTeam?.id]);

  if (!activeTeam) return <NeedsTeam title="Tendencies" />;

  return (
    <div>
      <PageHead title="Tendencies">
        What they like to do in each situation, from the film uploaded to{" "}
        {activeTeam.name}. Formation and motion use this team's vocabulary
        mapping.
      </PageHead>

      <section className="card">
        <form
          className="row"
          onSubmit={(e) => {
            e.preventDefault();
            load();
          }}
        >
          <label className="field">
            <span>Split by</span>
            <select value={split} onChange={(e) => setSplit(e.target.value as Split)}>
              {SPLITS.map((s) => (
                <option key={s} value={s}>
                  {SPLIT_LABELS[s]}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Offense (optional)</span>
            <input
              value={teamFilter}
              onChange={(e) => setTeamFilter(e.target.value)}
              placeholder="e.g. LINCOLN"
            />
          </label>
          <button className="btn btn-md btn-line">Apply</button>
        </form>
      </section>

      <section className="card" aria-busy={loading}>
        {error && <div className="msg error" role="alert">{error}</div>}
        {loading ? (
          <p className="muted">Loading…</p>
        ) : rows.length === 0 ? (
          !error && <p className="muted">No plays yet. Upload a breakdown to see tendencies.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{SPLIT_LABELS[split]}</th>
                  <th className="num">Plays</th>
                  <th>Run / pass</th>
                  <th className="num hide-sm">Explosive</th>
                  <th className="num hide-sm">Avg EPA</th>
                  <th className="hide-sm">Top play</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.bucket}>
                    <td className="strong">{r.bucket}</td>
                    <td className="num">{r.plays}</td>
                    <td>
                      <RunPassBar run={r.run_pct} pass={r.pass_pct} />
                    </td>
                    <td className="num hide-sm">
                      {r.explosive_pct == null ? "—" : `${r.explosive_pct}%`}
                    </td>
                    <td className="num hide-sm">{r.avg_epa ?? "—"}</td>
                    <td className="hide-sm">{r.top_play}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
