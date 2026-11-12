import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  alignment,
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
    <div className="quiz-page">
      <div className="quiz-wrap">
        <header className="quiz-head">
          <span className="quiz-logo">Engage Eight</span>
          <Link to="/">Sign in</Link>
        </header>

        {loadError && (
          <p className="quiz-msg">Couldn't load the quiz plays. Try refreshing.</p>
        )}
        {!deck && !loadError && <p className="quiz-msg">Loading plays…</p>}

        {play && summary && (
          <RoundSummary results={results.slice(-ROUND)} onNext={next} />
        )}

        {play && !summary && (
          <>
            <div className="quiz-tally">
              <Tally label="You" right={total("you")} of={results.length} />
              <span className="quiz-prog">
                Play {(pos % ROUND) + 1} of {ROUND}
              </span>
              <Tally label="Model" right={total("model")} of={results.length} end />
            </div>

            <section className="quiz-situation">
              <div className="quiz-down">{downAndDistance(play)}</div>
              <div className="quiz-at">at {fieldPosition(play)}</div>
              <dl className="quiz-facts">
                <Fact label="Clock" value={quarterClock(play)} />
                <Fact label="Score" value={scoreText(play)} />
                <Fact label="Timeouts" value={String(play.timeouts)} />
                <Fact label="Alignment" value={alignment(play)} />
              </dl>
              <p className="quiz-match">
                {play.offense} offense vs {play.defense}, week {play.week}
              </p>
            </section>

            {!picked ? (
              <div className="quiz-buttons">
                <button className="quiz-btn run" onClick={() => answer("run")}>
                  Run <kbd>R</kbd>
                </button>
                <button className="quiz-btn pass" onClick={() => answer("pass")}>
                  Pass <kbd>P</kbd>
                </button>
              </div>
            ) : (
              <Reveal
                play={play}
                picked={picked}
                onNext={next}
                last={(pos + 1) % ROUND === 0}
              />
            )}
          </>
        )}

        <p className="quiz-foot">
          Real 2023 NFL plays the model never trained on. Scrambles and sacks count
          as passes. Data from <a href="https://github.com/nflverse">nflverse</a>.
        </p>
      </div>
    </div>
  );
}

function Tally({
  label,
  right,
  of,
  end,
}: {
  label: string;
  right: number;
  of: number;
  end?: boolean;
}) {
  return (
    <div className={end ? "quiz-tally-side end" : "quiz-tally-side"}>
      <small>{label}</small>
      <b>
        {right}
        <i>/{of}</i>
      </b>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
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
  const right = picked === play.actual;
  return (
    <section className="quiz-reveal">
      <div className="quiz-result">
        <span className={right ? "quiz-badge right" : "quiz-badge wrong"}>
          {right ? "Right" : "Wrong"}
        </span>
        You said {picked}.
      </div>
      <div className={`quiz-call ${play.actual}`}>{play.actual}.</div>
      <p className="quiz-desc">{play.desc}</p>
      <div className="quiz-bar" role="img" aria-label={`Model: ${pass}% pass`}>
        <i className="run" style={{ width: `${100 - pass}%` }} />
        <i className="pass" style={{ width: `${pass}%` }} />
      </div>
      <div className="quiz-barlabels">
        <span>Run {100 - pass}%</span>
        <span>Pass {pass}%</span>
      </div>
      <p className="quiz-note">
        The model said {mc} and was {mc === play.actual ? "right" : "wrong"}.
      </p>
      <button className="quiz-btn next" onClick={onNext}>
        {last ? "See round results" : "Next play"} <kbd>Enter</kbd>
      </button>
    </section>
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
    you > model
      ? "You beat the model."
      : you === model
        ? "A tie with the model."
        : "The model wins this round.";
  return (
    <section className="quiz-reveal">
      <div className="quiz-result">Round complete</div>
      <div className="quiz-final">
        <div>
          <small>You</small>
          <b>{you}</b>
        </div>
        <div className="end">
          <small>Model</small>
          <b>{model}</b>
        </div>
      </div>
      <p className="quiz-note">
        Out of {results.length} plays. {verdict}
      </p>
      <button className="quiz-btn next" onClick={onNext}>
        Next round <kbd>Enter</kbd>
      </button>
    </section>
  );
}
