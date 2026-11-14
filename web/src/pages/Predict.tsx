import { useEffect, useState } from "react";
import { useStore } from "../useStore";
import {
  api,
  ApiError,
  type PredictRequest,
  type RecommendResponse,
} from "../api/client";
import PageHead from "../components/PageHead";

type Tri = "" | "yes" | "no";
const triToBool = (v: Tri) => (v === "" ? null : v === "yes");

// Seconds left in the game from quarter + time left in that quarter.
const gameSeconds = (quarter: number, quarterSeconds: number) =>
  quarter >= 5 ? quarterSeconds : (4 - quarter) * 900 + quarterSeconds;

const pct = (p: number) => `${Math.round(p * 100)}%`;

export default function Predict() {
  const { activeTeam, user } = useStore();
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

  const [opponents, setOpponents] = useState<string[]>([]);
  const [formations, setFormations] = useState<string[]>([]);
  const [motions, setMotions] = useState<string[]>([]);
  const [result, setResult] = useState<RecommendResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Formation/motion options come from the active team's canonical vocab;
  // opponent names are suggested from the team's opponents.
  useEffect(() => {
    if (!activeTeam) return;
    api
      .getVocab(activeTeam.id, null)
      .then((v) => {
        setFormations(v.canonical.formations);
        setMotions(v.canonical.motions);
      })
      .catch(() => {});
    api
      .listOpponents(activeTeam.id)
      .then((list) => {
        const names = list.map((o) => o.name);
        setOpponents(names);
        // A demo has one sample opponent: fill it in so the blend works on
        // the first try.
        if (user?.is_demo && names.length > 0) setOpponent((cur) => cur || names[0]);
      })
      .catch(() => {});
  }, [activeTeam, user?.is_demo]);

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
          : "Prediction failed."
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
      <PageHead title="Predict">
        Set up a pre-snap situation to get the run/pass read and a few
        defensive calls. Add an opponent to lean on their own film.
      </PageHead>

      <form onSubmit={submit}>
        <section className="card">
          <h2 className="card-title cond">Situation</h2>
          <div className="stack">
            <div className="row">
              <label className="field">
                <span>Down</span>
                <select value={down} onChange={(e) => setDown(Number(e.target.value))}>
                  {[1, 2, 3, 4].map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Distance</span>
                <input
                  className="w-sm"
                  type="number"
                  min={1}
                  max={99}
                  value={distance}
                  onChange={(e) => setDistance(num(e.target.value))}
                />
              </label>
              <label className="field">
                <span>Yards to goal</span>
                <input
                  className="w-sm"
                  type="number"
                  min={1}
                  max={99}
                  value={yardline}
                  onChange={(e) => setYardline(num(e.target.value))}
                />
              </label>
              <label className="field">
                <span>Quarter</span>
                <select value={quarter} onChange={(e) => setQuarter(Number(e.target.value))}>
                  {[1, 2, 3, 4, 5].map((q) => (
                    <option key={q} value={q}>
                      {q === 5 ? "OT" : q}
                    </option>
                  ))}
                </select>
              </label>
              <div className="field">
                <span id="clock-label">Time left in quarter</span>
                <div className="field-time" role="group" aria-labelledby="clock-label">
                  <input
                    className="w-xs"
                    type="number"
                    min={0}
                    max={15}
                    value={minutes}
                    onChange={(e) => setMinutes(num(e.target.value))}
                    aria-label="Minutes"
                  />
                  :
                  <input
                    className="w-xs"
                    type="number"
                    min={0}
                    max={59}
                    value={seconds}
                    onChange={(e) => setSeconds(num(e.target.value))}
                    aria-label="Seconds"
                  />
                </div>
              </div>
              <label className="field">
                <span>Score (offense − defense)</span>
                <input
                  className="w-sm"
                  type="number"
                  value={scoreDiff}
                  onChange={(e) => setScoreDiff(num(e.target.value))}
                />
              </label>
            </div>
            <div className="row">
              <label className="field">
                <span>QB alignment</span>
                <select value={shotgun} onChange={(e) => setShotgun(e.target.value as Tri)}>
                  <option value="">Unknown</option>
                  <option value="yes">Shotgun / pistol</option>
                  <option value="no">Under center</option>
                </select>
              </label>
              <label className="field">
                <span>Tempo</span>
                <select value={noHuddle} onChange={(e) => setNoHuddle(e.target.value as Tri)}>
                  <option value="">Unknown</option>
                  <option value="yes">No huddle</option>
                  <option value="no">Huddled</option>
                </select>
              </label>
            </div>
          </div>
        </section>

        <section className="card">
          <h2 className="card-title cond">Opponent</h2>
          <fieldset disabled={!activeTeam}>
            <legend>
              Optional. Blends in the plays you've uploaded for this opponent.
            </legend>
            <div className="row">
              <label className="field">
                <span>Opponent label</span>
                <input
                  list="opponent-names"
                  value={opponent}
                  onChange={(e) => setOpponent(e.target.value)}
                  placeholder="as used on upload, e.g. LINCOLN"
                />
                <datalist id="opponent-names">
                  {opponents.map((o) => (
                    <option key={o} value={o} />
                  ))}
                </datalist>
              </label>
              <label className="field">
                <span>Formation</span>
                <select
                  value={formation}
                  onChange={(e) => setFormation(e.target.value)}
                  disabled={!opponent.trim()}
                >
                  <option value="">Any</option>
                  {formations.map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Motion</span>
                <select
                  value={motion}
                  onChange={(e) => setMotion(e.target.value)}
                  disabled={!opponent.trim()}
                >
                  <option value="">Any</option>
                  {motions.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {!activeTeam && (
              <p className="muted" style={{ marginTop: 12 }}>
                Pick a team to use opponent tendencies.
              </p>
            )}
          </fieldset>
          <button className="btn btn-light" style={{ marginTop: 22 }} disabled={busy} aria-busy={busy}>
            {busy ? "Reading the play…" : "Make the call"}
          </button>
          {error && <div className="msg error" role="alert">{error}</div>}
        </section>
      </form>

      {pred && (
        <section className="card" aria-live="polite">
          <div className="result">
            <div>
              <small>The read</small>
              <div className={`lean-word cond ${pred.lean === "RUN" ? "lean-run" : "lean-pass"}`}>
                {pred.lean}
              </div>
            </div>
            <div>
              <div
                className="split"
                role="img"
                aria-label={`${pct(pred.run_prob)} run, ${pct(pred.pass_prob)} pass`}
              >
                <span className="split-run" style={{ width: `${pred.run_prob * 100}%` }} />
                <span className="split-pass" style={{ width: `${pred.pass_prob * 100}%` }} />
              </div>
              <div className="split-labels">
                <span>Run {pct(pred.run_prob)}</span>
                <span>Pass {pct(pred.pass_prob)}</span>
              </div>
              {blended && (
                <p className="result-model">
                  League model alone: {pct(pred.model_pass_prob)} pass
                </p>
              )}
            </div>
          </div>
          <p className="why">{pred.why}</p>
          {blended && (
            <div className="table-wrap blend">
              <table>
                <thead>
                  <tr>
                    <th>Opponent plays used</th>
                    <th className="num">Plays</th>
                    <th className="num">Their pass rate</th>
                    <th className="num">Pass after</th>
                  </tr>
                </thead>
                <tbody>
                  {pred.blend.map((s) => (
                    <tr key={s.label}>
                      <td>{s.label}</td>
                      <td className="num">{s.plays}</td>
                      <td className="num">{pct(s.pass_rate)}</td>
                      <td className="num">{pct(s.pass_prob_after)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {opponent.trim() && !blended && (
            <p className="muted" style={{ marginTop: 14 }}>
              No uploaded plays for “{opponent.trim()}” in this team, so this is
              the league model alone.
            </p>
          )}
        </section>
      )}

      {result && result.recommendations.length > 0 && (
        <section className="card">
          <h2 className="card-title cond">Defensive calls</h2>
          <p className="card-sub">{result.basis}</p>
          <div className="recs">
            {result.recommendations.map((c, i) => (
              <article className="rec" key={i}>
                <div className="rec-n">Call {i + 1}</div>
                <div className="rec-front cond">{c.front}</div>
                <dl>
                  <dt>Coverage</dt>
                  <dd>{c.coverage}</dd>
                  <dt>Pressure</dt>
                  <dd>{c.pressure}</dd>
                  <dt>Stunt</dt>
                  <dd>{c.stunt}</dd>
                </dl>
                <p>{c.rationale}</p>
              </article>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
