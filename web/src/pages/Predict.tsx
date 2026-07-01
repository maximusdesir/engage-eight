import { useEffect, useState } from "react";
import { useStore } from "../store";
import {
  api,
  ApiError,
  type PredictRequest,
  type RecommendResponse,
} from "../api/client";

const clock = (s: number) => {
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, "0")}`;
};

export default function Predict() {
  const { activeTeam } = useStore();
  const [form, setForm] = useState<PredictRequest>({
    down: 3,
    distance: 2,
    yardline_100: 45,
    quarter: 2,
    game_seconds_remaining: 1800,
    score_differential: 0,
    formation: "",
    motion_type: "",
    offense_team: "",
  });
  const [formations, setFormations] = useState<string[]>([]);
  const [motions, setMotions] = useState<string[]>([]);
  const [result, setResult] = useState<RecommendResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Populate formation/motion dropdowns from the active team's canonical vocab.
  useEffect(() => {
    if (!activeTeam) return;
    api
      .getVocab(activeTeam.id, null)
      .then((v) => {
        setFormations(v.canonical.formations);
        setMotions(v.canonical.motions);
      })
      .catch(() => {});
  }, [activeTeam?.id]);

  const set = (patch: Partial<PredictRequest>) =>
    setForm((f) => ({ ...f, ...patch }));

  const num = (v: string) => (v === "" ? 0 : Number(v));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const payload: PredictRequest = {
        ...form,
        formation: form.formation || null,
        motion_type: form.motion_type || null,
        offense_team: form.offense_team || null,
      };
      setResult(await api.recommend(payload));
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.status === 503
            ? "Model not trained yet. Run the ml pipeline to enable predictions."
            : err.message
          : "Prediction failed"
      );
      setResult(null);
    } finally {
      setBusy(false);
    }
  };

  const pred = result?.predicted;

  return (
    <div>
      <h1>Predict &amp; recommend</h1>
      <p className="subtitle">
        Score a pre-snap situation and get ranked defensive calls.
      </p>

      <div className="card">
        <form className="stack" onSubmit={submit}>
          <div className="row">
            <div className="field">
              <label>Down</label>
              <select
                value={form.down}
                onChange={(e) => set({ down: Number(e.target.value) })}
              >
                {[1, 2, 3, 4].map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Distance</label>
              <input
                type="number"
                value={form.distance}
                onChange={(e) => set({ distance: num(e.target.value) })}
                style={{ width: 90 }}
              />
            </div>
            <div className="field">
              <label>Yards to goal</label>
              <input
                type="number"
                value={form.yardline_100}
                onChange={(e) => set({ yardline_100: num(e.target.value) })}
                style={{ width: 90 }}
              />
            </div>
            <div className="field">
              <label>Quarter</label>
              <select
                value={form.quarter}
                onChange={(e) => set({ quarter: Number(e.target.value) })}
              >
                {[1, 2, 3, 4, 5].map((q) => (
                  <option key={q} value={q}>
                    {q === 5 ? "OT" : q}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="row">
            <div className="field">
              <label>Clock ({clock(form.game_seconds_remaining ?? 0)})</label>
              <input
                type="range"
                min={0}
                max={3600}
                step={15}
                value={form.game_seconds_remaining}
                onChange={(e) =>
                  set({ game_seconds_remaining: num(e.target.value) })
                }
              />
            </div>
            <div className="field">
              <label>Score diff (off − def)</label>
              <input
                type="number"
                value={form.score_differential}
                onChange={(e) => set({ score_differential: num(e.target.value) })}
                style={{ width: 90 }}
              />
            </div>
          </div>

          <div className="row">
            <div className="field">
              <label>Formation</label>
              <select
                value={form.formation ?? ""}
                onChange={(e) => set({ formation: e.target.value })}
              >
                <option value="">(any)</option>
                {formations.map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Motion</label>
              <select
                value={form.motion_type ?? ""}
                onChange={(e) => set({ motion_type: e.target.value })}
              >
                <option value="">(any)</option>
                {motions.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Offense team</label>
              <input
                value={form.offense_team ?? ""}
                onChange={(e) => set({ offense_team: e.target.value })}
                placeholder="optional"
              />
            </div>
            <button disabled={busy}>{busy ? "…" : "Predict"}</button>
          </div>
          {!activeTeam && (
            <div className="muted">
              Select a team to populate canonical formation/motion options.
            </div>
          )}
        </form>
        {error && <div className="error">{error}</div>}
      </div>

      {pred && (
        <div className="card">
          <div className="row" style={{ alignItems: "center", gap: 40 }}>
            <div>
              <div className="muted">Lean</div>
              <div
                className={`big-prob ${
                  pred.lean === "run" ? "lean-run" : "lean-pass"
                }`}
              >
                {pred.lean.toUpperCase()}
              </div>
            </div>
            <div>
              <div className="muted">Pass / Run</div>
              <div style={{ fontSize: 22 }}>
                <span className="lean-pass">
                  {Math.round(pred.pass_prob * 100)}%
                </span>{" "}
                /{" "}
                <span className="lean-run">
                  {Math.round(pred.run_prob * 100)}%
                </span>
              </div>
            </div>
            <div>
              <div className="muted">Confidence</div>
              <div style={{ fontSize: 22 }}>
                {Math.round(pred.confidence * 100)}%
              </div>
            </div>
          </div>
          <p className="muted" style={{ marginTop: 12 }}>
            {pred.why}
          </p>
        </div>
      )}

      {result && result.recommendations.length > 0 && (
        <div className="card">
          <h1 style={{ fontSize: 16 }}>Recommended defensive calls</h1>
          <table>
            <thead>
              <tr>
                <th>Front</th>
                <th>Coverage</th>
                <th>Pressure</th>
                <th>Stunt</th>
                <th>Conf</th>
                <th>EPA saved</th>
                <th>Why</th>
              </tr>
            </thead>
            <tbody>
              {result.recommendations.map((c, i) => (
                <tr key={i}>
                  <td>{c.front}</td>
                  <td>{c.coverage}</td>
                  <td>{c.pressure}</td>
                  <td>{c.stunt}</td>
                  <td>{Math.round(c.confidence * 100)}%</td>
                  <td>{c.expected_epa_prevented.toFixed(2)}</td>
                  <td className="muted">{c.rationale}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
