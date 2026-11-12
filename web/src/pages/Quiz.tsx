import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  downAndDistance,
  fieldPosition,
  modelCall,
  quarterClock,
  scoreText,
  shuffled,
  type Call,
  type QuizFile,
  type QuizPlay,
} from "../quiz";

const ROUND = 10;
type Result = { you: boolean; model: boolean };

export default function Quiz() {
  const [deck, setDeck] = useState<QuizPlay[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [pos, setPos] = useState(0);
  const [picked, setPicked] = useState<Call | null>(null);
  const [results, setResults] = useState<Result[]>([]);
  const [summary, setSummary] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(`${import.meta.env.BASE_URL}quiz/plays-2023.json`)
      .then((r) => (r.ok ? (r.json() as Promise<QuizFile>) : Promise.reject()))
      .then((f) => !cancelled && setDeck(shuffled(f.plays)))
      .catch(() => !cancelled && setLoadError(true));
    return () => {
      cancelled = true;
    };
  }, []);

  const play = deck ? deck[pos] : null;

  const answer = useCallback(
    (call: Call) => {
      if (!play || picked) return;
      setPicked(call);
      setResults((r) => [
        ...r,
        { you: call === play.actual, model: modelCall(play) === play.actual },
      ]);
    },
    [play, picked]
  );

  const next = useCallback(() => {
    if (!deck || !picked) return;
    if (summary) {
      setSummary(false);
      setPos((pos + 1) % deck.length);
      setPicked(null);
    } else if ((pos + 1) % ROUND === 0) {
      setSummary(true);
    } else {
      setPos((pos + 1) % deck.length);
      setPicked(null);
    }
  }, [deck, picked, summary, pos]);

  // Keyboard: R / P to answer, Enter / N for the next play.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const k = e.key.toLowerCase();
      if (k === "r") answer("run");
      else if (k === "p") answer("pass");
      else if (k === "n" || k === "enter") {
        // Stop Enter from also clicking a focused button (double advance).
        e.preventDefault();
        if (!e.repeat) next();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [answer, next]);

  const total = (key: keyof Result) => results.filter((r) => r[key]).length;

  return (
    <div className="quiz-wrap">
      <header className="quiz-head">
        <div className="brand">
          Engage Eight
          <small>Call it: run or pass?</small>
        </div>
        <Link to="/">Sign in</Link>
      </header>

      {loadError && (
        <div className="card error">Couldn't load the quiz plays. Try refreshing.</div>
      )}
      {!deck && !loadError && <div className="card muted">Loading plays…</div>}

      {play && summary && (
        <RoundSummary results={results.slice(-ROUND)} onNext={next} />
      )}

      {play && !summary && (
        <>
          <div className="quiz-score">
            <span>
              You <b>{total("you")}</b>/{results.length}
            </span>
            <span className="muted">
              Play {(pos % ROUND) + 1} of {ROUND}
            </span>
            <span>
              Model <b>{total("model")}</b>/{results.length}
            </span>
          </div>

          <div className="card">
            <div className="quiz-down">{downAndDistance(play)}</div>
            <div className="muted">at {fieldPosition(play)}</div>
            <div className="quiz-facts">
              <span className="pill">{quarterClock(play)}</span>
              <span className="pill">{scoreText(play)}</span>
              <span className="pill">{play.timeouts} timeouts</span>
              <span className="pill">{play.shotgun ? "Shotgun" : "Under center"}</span>
              {play.no_huddle === 1 && <span className="pill">No huddle</span>}
            </div>
            <div className="muted" style={{ marginTop: 10, fontSize: 13 }}>
              {play.offense} offense vs {play.defense}, week {play.week}
            </div>
          </div>

          {!picked ? (
            <div className="quiz-buttons">
              <button className="quiz-run" onClick={() => answer("run")}>
                Run <kbd>R</kbd>
              </button>
              <button className="quiz-pass" onClick={() => answer("pass")}>
                Pass <kbd>P</kbd>
              </button>
            </div>
          ) : (
            <Reveal play={play} picked={picked} onNext={next} last={(pos + 1) % ROUND === 0} />
          )}
        </>
      )}

      <p className="muted quiz-foot">
        Real 2023 NFL plays the model never trained on. Scrambles and sacks count
        as passes. Data from{" "}
        <a href="https://github.com/nflverse">nflverse</a>.
      </p>
    </div>
  );
}

function Reveal({
  play,
  picked,
  onNext,
  last,
}: {
  play: QuizPlay;
  picked: Call;
  onNext: () => void;
  last: boolean;
}) {
  const pass = Math.round(play.model_pass_prob * 100);
  const mc = modelCall(play);
  return (
    <div className="card">
      <div className={`quiz-verdict ${picked === play.actual ? "ok" : "error"}`}>
        {picked === play.actual ? "Right" : "Wrong"}: it was a{" "}
        <b className={play.actual === "pass" ? "lean-pass" : "lean-run"}>
          {play.actual}
        </b>
        . You said {picked}.
      </div>
      <p className="quiz-desc">{play.desc}</p>
      <div className="bar" aria-label={`Model: ${pass}% pass`}>
        <div className="run" style={{ width: `${100 - pass}%` }}>
          <span>{100 - pass > 12 ? `Run ${100 - pass}%` : ""}</span>
        </div>
        <div className="pass" style={{ width: `${pass}%` }}>
          <span>{pass > 12 ? `Pass ${pass}%` : ""}</span>
        </div>
      </div>
      <div className="muted" style={{ marginTop: 6, fontSize: 13 }}>
        The model said {mc} ({Math.max(pass, 100 - pass)}%) and was{" "}
        {mc === play.actual ? "right" : "wrong"}.
      </div>
      <button style={{ marginTop: 14 }} onClick={onNext}>
        {last ? "See round results" : "Next play"} <kbd>Enter</kbd>
      </button>
    </div>
  );
}

function RoundSummary({
  results,
  onNext,
}: {
  results: Result[];
  onNext: () => void;
}) {
  const you = results.filter((r) => r.you).length;
  const model = results.filter((r) => r.model).length;
  const verdict =
    you > model ? "You beat the model." : you === model ? "A tie with the model." : "The model wins this round.";
  return (
    <div className="card" style={{ textAlign: "center" }}>
      <h1>Round complete</h1>
      <div className="big-prob">
        {you} vs {model}
      </div>
      <p className="muted">
        You got {you} of {results.length}, the model got {model}. {verdict}
      </p>
      <button onClick={onNext}>Next round <kbd>Enter</kbd></button>
    </div>
  );
}
