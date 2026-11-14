import { useCallback, useEffect, useRef, useState } from "react";
import SiteNav from "../components/SiteNav";
import { Picks, RedCard, Reveal } from "../components/CallCard";
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
import "../site.css";

const ROUND = 10;
type Result = { you: boolean; model: boolean };

export default function Quiz() {
  const [deck, setDeck] = useState<QuizPlay[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [pos, setPos] = useState(0);
  const [picked, setPicked] = useState<Call | null>(null);
  const [results, setResults] = useState<Result[]>([]);
  const [summary, setSummary] = useState(false);
  const top = useRef<HTMLElement>(null);

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
  // Scores and progress are per round of ten.
  const inRound = pos % ROUND;
  const round = results.slice(results.length - (inRound + (picked ? 1 : 0)));

  const answer = useCallback(
    (call: Call) => {
      if (!play || picked || summary) return;
      setPicked(call);
      setResults((r) => [
        ...r,
        { you: call === play.actual, model: modelCall(play) === play.actual },
      ]);
    },
    [play, picked, summary]
  );

  const next = useCallback(() => {
    if (!deck || !picked) return;
    const advance = () => {
      setPos((pos + 1) % deck.length);
      setPicked(null);
      // On phones the card sits below the situation: bring the new play into view.
      const el = top.current;
      if (el && el.getBoundingClientRect().top < 0) {
        const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        el.scrollIntoView({ behavior: still ? "auto" : "smooth" });
      }
    };
    if (summary) {
      setSummary(false);
      advance();
    } else if ((pos + 1) % ROUND === 0) {
      setSummary(true);
    } else {
      advance();
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

  const you = round.filter((r) => r.you).length;
  const model = round.filter((r) => r.model).length;

  return (
    <div className="e8">
      <div className="e8-page">
        <SiteNav page="quiz" />

        <section className="panel qz" ref={top}>
          {loadError && <p className="qz-msg">Couldn't load the quiz plays. Try refreshing.</p>}
          {!deck && !loadError && <p className="qz-msg">Loading plays…</p>}

          {play && (
            <>
              <div className="qz-top">
                <div>
                  <div className="qz-count">
                    Play {inRound + 1} of {ROUND}
                  </div>
                  <div className="qz-ticks" aria-hidden="true">
                    {Array.from({ length: ROUND }, (_, i) => (
                      <span
                        key={i}
                        className={
                          i < round.length ? (round[i].you ? "right" : "wrong") : i === inRound ? "now" : undefined
                        }
                      />
                    ))}
                  </div>
                </div>
                <div className="qz-scores" aria-live="polite">
                  <Score label="You" right={you} of={round.length} />
                  <Score label="Model" right={model} of={round.length} />
                </div>
              </div>

              <div className="qz-grid">
                <div>
                  <div className="chip chip-line">
                    {play.offense} offense vs {play.defense} · Week {play.week}
                  </div>
                  <div className="sit cond">{downAndDistance(play)}</div>
                  <div className="qz-spot cond">At {fieldPosition(play)}</div>
                  <dl className="facts">
                    <Fact label="Clock" value={quarterClock(play)} />
                    <Fact label="Score" value={scoreText(play)} />
                    <Fact label="Timeouts" value={String(play.timeouts)} />
                    <Fact label="Alignment" value={alignment(play)} />
                  </dl>
                </div>

                <RedCard title={summary ? "Round over" : "Make the call"} label="Your call">
                  {summary ? (
                    <RoundSummary you={you} model={model} onNext={next} />
                  ) : !picked ? (
                    <div>
                      <p className="qz-prompt">
                        Run or pass? Make your read before you see what happened.
                      </p>
                      <Picks onPick={answer} large keys />
                    </div>
                  ) : (
                    <Reveal
                      key={play.id}
                      large
                      picked={picked}
                      actual={play.actual}
                      desc={play.desc}
                      passPct={Math.round(play.model_pass_prob * 100)}
                      verdict={`The model said ${modelCall(play)} and was ${
                        modelCall(play) === play.actual ? "right" : "wrong"
                      }.`}
                      nextLabel={(pos + 1) % ROUND === 0 ? "See round results" : "Next play"}
                      onNext={next}
                    />
                  )}
                </RedCard>
              </div>
            </>
          )}
        </section>

        <p className="qz-foot">
          Real 2023 NFL plays the model never trained on. Scrambles and sacks count as
          passes. Data from{" "}
          <a href="https://github.com/nflverse" target="_blank" rel="noreferrer">
            nflverse
          </a>
          .
        </p>
      </div>
    </div>
  );
}

function Score({ label, right, of }: { label: string; right: number; of: number }) {
  return (
    <div>
      <span>{label}</span>
      <b className="cond">
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

function RoundSummary({ you, model, onNext }: { you: number; model: number; onNext: () => void }) {
  const next = useRef<HTMLButtonElement>(null);
  useEffect(() => next.current?.focus({ preventScroll: true }), []);
  const verdict =
    you > model
      ? "You beat the model."
      : you === model
        ? "A tie with the model."
        : "The model wins this round.";
  return (
    <div className="rise">
      <span className="dc-label">Ten plays</span>
      <div className="dc-final">
        <div>
          <span>You</span>
          <b className="cond">
            {you}/{ROUND}
          </b>
        </div>
        <div>
          <span>Model</span>
          <b className="cond">
            {model}/{ROUND}
          </b>
        </div>
      </div>
      <p className="dc-note">{verdict} A new round starts with fresh plays.</p>
      <button ref={next} className="btn btn-next" onClick={onNext} aria-keyshortcuts="Enter">
        Next round
      </button>
    </div>
  );
}
