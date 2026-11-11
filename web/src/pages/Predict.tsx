import { useEffect, useState } from "react";
import { useStore } from "../store";
import {
  api,
  ApiError,
  type PredictRequest,
  type RecommendResponse,
} from "../api/client";

type Tri = "" | "yes" | "no";
const triToBool = (v: Tri) => (v === "" ? null : v === "yes");

// Seconds left in the game from quarter + time left in that quarter.
const gameSeconds = (quarter: number, quarterSeconds: number) =>
  quarter >= 5 ? quarterSeconds : (4 - quarter) * 900 + quarterSeconds;

const pct = (p: number) => `${Math.round(p * 100)}%`;

export default function Predict() {
  const { activeTeam } = useStore();
  const [down, setDown] = useState(3);
  const [distance, setDistance] = useState(2);
  const [yardline, setYardline] = useState(45);
  const [quarter, setQuarter] = useState(2);
  const [minutes, setMinutes] = useState(10);
  const [seconds, setSeconds] = useState(0);
  const [scoreDiff, setScoreDiff] = useState(0);
  const [shotgun, setShotgun] = useState<Tri>("");
  const [noHuddle, setNoHuddle] = useState<Tri>("");
  const [opponent, setOpponent] = useState("");
  const [formation, setFormation] = useState("");
  const [motion, setMotion] = useState("");

  const [formations, setFormations] = useState<string[]>([]);
  const [motions, setMotions] = useState<string[]>([]);
  const [result, setResult] = useState<RecommendResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Formation/motion options come from the active team's canonical vocab.
  useEffect(() => {
    if (!activeTeam) return;
    api
      .getVocab(activeTeam.id, null)
      .then((v) => {
        setFormations(v.canonical.formations);
        setMotions(v.canonical.motions);
      })
      .catch(() => {});
  }, [activeTeam]);

  const num = (v: string) => (v === "" ? 0 : Number(v));
  const quarterSeconds = Math.min(900, Math.max(0, minutes * 60 + seconds));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const blend = activeTeam && opponent.trim();
      const payload: PredictRequest = {
        down,
        distance,
        yardline_100: yardline,
        quarter,
        game_seconds_remaining: gameSeconds(quarter, quarterSeconds),
        score_differential: scoreDiff,
        shotgun: triToBool(shotgun),
        no_huddle: triToBool(noHuddle),
        team_id: blend ? activeTeam.id : null,
        offense_team: blend ? opponent.trim() : null,
        formation: blend && formation ? formation : null,
        motion_type: blend && motion ? motion : null,
      };
      setResult(await api.recommend(payload));
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.status === 503
            ? "Model not found. Run the ml pipeline (python -m engage8.train)."
            : err.message
          : "Prediction failed"
      );
      setResult(null);
    } finally {
      setBusy(false);
    }
  };

  const pred = result?.predicted;
  const blended = pred && pred.blend.length > 0;

  return (
    <div>
      <h1>Predict &amp; recommend</h1>
      <p className="subtitle">
        Score a pre-snap situation and get suggested defensive calls.
      </p>

      <div className="card">
        <form className="stack" onSubmit={submit}>
          <div className="row">
            <div className="field">
              <label>Down</label>
              <select value={down} onChange={(e) => setDown(Number(e.target.value))}>
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
                min={1}
                max={99}
                value={distance}
                onChange={(e) => setDistance(num(e.target.value))}
                style={{ width: 90 }}
              />
            </div>
            <div className="field">
              <label>Yards to goal</label>
              <input
                type="number"
                min={1}
                max={99}
                value={yardline}
                onChange={(e) => setYardline(num(e.target.value))}
                style={{ width: 90 }}
              />
            </div>
            <div className="field">
              <label>Quarter</label>
              <select
                value={quarter}
                onChange={(e) => setQuarter(Number(e.target.value))}
              >
                {[1, 2, 3, 4, 5].map((q) => (
                  <option key={q} value={q}>
                    {q === 5 ? "OT" : q}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Time left in quarter</label>
              <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
                <input
                  type="number"
                  min={0}
                  max={15}
                  value={minutes}
                  onChange={(e) => setMinutes(num(e.target.value))}
                  style={{ width: 60 }}
                  aria-label="Minutes"
                />
                :
                <input
                  type="number"
                  min={0}
                  max={59}
                  value={seconds}
                  onChange={(e) => setSeconds(num(e.target.value))}
                  style={{ width: 60 }}
                  aria-label="Seconds"
                />
              </div>
            </div>
            <div className="field">
              <label>Score diff (off − def)</label>
              <input
                type="number"
                value={scoreDiff}
                onChange={(e) => setScoreDiff(num(e.target.value))}
                style={{ width: 90 }}
              />
            </div>
          </div>

          <div className="row">
            <div className="field">
              <label>QB alignment</label>
              <select
                value={shotgun}
                onChange={(e) => setShotgun(e.target.value as Tri)}
              >
                <option value="">Unknown</option>
                <option value="yes">Shotgun / pistol</option>
                <option value="no">Under center</option>
              </select>
            </div>
            <div className="field">
              <label>Tempo</label>
              <select
                value={noHuddle}
                onChange={(e) => setNoHuddle(e.target.value as Tri)}
              >
                <option value="">Unknown</option>
                <option value="yes">No huddle</option>
                <option value="no">Huddled</option>
              </select>
            </div>
          </div>

          <fieldset className="stack" disabled={!activeTeam}>
            <legend className="muted">
              Opponent tendencies (optional): blend in plays uploaded for this
              opponent
            </legend>
            <div className="row">
              <div className="field">
                <label>Opponent label</label>
                <input
                  value={opponent}
                  onChange={(e) => setOpponent(e.target.value)}
                  placeholder="as used on upload, e.g. LINCOLN"
                />
              </div>
              <div className="field">
                <label>Formation</label>
                <select
                  value={formation}
                  onChange={(e) => setFormation(e.target.value)}
                  disabled={!opponent.trim()}
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
                  value={motion}
                  onChange={(e) => setMotion(e.target.value)}
                  disabled={!opponent.trim()}
                >
                  <option value="">(any)</option>
                  {motions.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            {!activeTeam && (
              <div className="muted">Select a team to use opponent tendencies.</div>
            )}
          </fieldset>

          <div>
            <button disabled={busy}>{busy ? "…" : "Predict"}</button>
          </div>
        </form>
        {error && <div className="error">{error}</div>}
      </div>

      {pred && (
        <div className="card">
          <div className="row" style={{ alignItems: "center", gap: 40 }}>
            <div>
              <div className="muted">Lean</div>
              <div
                className={`big-prob ${pred.lean === "RUN" ? "lean-run" : "lean-pass"}`}
              >
                {pred.lean}
              </div>
            </div>
            <div>
              <div className="muted">Pass / Run</div>
              <div style={{ fontSize: 22 }}>
                <span className="lean-pass">{pct(pred.pass_prob)}</span> /{" "}
                <span className="lean-run">{pct(pred.run_prob)}</span>
              </div>
            </div>
            {blended && (
              <div>
                <div className="muted">League model alone</div>
                <div style={{ fontSize: 22 }}>{pct(pred.model_pass_prob)} pass</div>
              </div>
            )}
          </div>
          <p className="muted" style={{ marginTop: 12 }}>
            {pred.why}
          </p>
          {blended && (
            <table>
              <thead>
                <tr>
                  <th>Opponent plays used</th>
                  <th>Plays</th>
                  <th>Their pass rate</th>
                  <th>Pass prob. after</th>
                </tr>
              </thead>
              <tbody>
                {pred.blend.map((s) => (
                  <tr key={s.label}>
                    <td>{s.label}</td>
                    <td>{s.plays}</td>
                    <td>{pct(s.pass_rate)}</td>
                    <td>{pct(s.pass_prob_after)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {opponent.trim() && !blended && (
            <p className="muted">
              No uploaded plays found for “{opponent.trim()}” in this team, so
              this is the league model only.
            </p>
          )}
        </div>
      )}

      {result && result.recommendations.length > 0 && (
        <div className="card">
          <h1 style={{ fontSize: 16 }}>Suggested defensive calls</h1>
          <p className="muted">{result.basis}</p>
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Front</th>
                <th>Coverage</th>
                <th>Pressure</th>
                <th>Stunt</th>
                <th>Why</th>
              </tr>
            </thead>
            <tbody>
              {result.recommendations.map((c, i) => (
                <tr key={i}>
                  <td>{i + 1}</td>
                  <td>{c.front}</td>
                  <td>{c.coverage}</td>
                  <td>{c.pressure}</td>
                  <td>{c.stunt}</td>
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
