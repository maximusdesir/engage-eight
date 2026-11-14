// Public landing page: the layered hero, a two-play taste of the quiz, the
// shotgun vs under-center stat, three ways in, and a closing call to action.
import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import heroPlayer from "../assets/hero-player.webp";
import SiteNav from "../components/SiteNav";
import { Picks, RedCard, Reveal } from "../components/CallCard";
import { useCountUp, useFocusPull } from "../motion";
import type { Call } from "../quiz";
import { useStartDemo } from "../useStartDemo";
import "../site.css";

export default function Landing() {
  const root = useRef<HTMLDivElement>(null);
  const { hash } = useLocation();
  useFocusPull(root);

  // Arriving from another page at /#ways: the router doesn't scroll for us.
  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView();
  }, [hash]);

  return (
    <div className="e8" ref={root}>
      <div className="e8-page">
        <Hero />
        <StatSection />
        <Ways />
        <section className="panel cta fx pad">
          <span className="cta-mark" aria-hidden="true" />
          <h2 className="cond">
            <span>Ten plays.</span>
            <span>Beat the model.</span>
          </h2>
          <p>Real 2023 plays. No account needed.</p>
          <Link className="btn btn-light" to="/quiz">
            Take the quiz
          </Link>
        </section>
        <SiteFooter />
      </div>
    </div>
  );
}

function ChevronsRight() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M6 6l6 6-6 6" />
      <path d="M13 6l6 6-6 6" />
    </svg>
  );
}

function Hero() {
  const demo = useStartDemo();
  return (
    <section className="hero">
      <SiteNav page="home" />
      <div className="hero-body">
        <h1 className="hl cond">
          <span className="l1">Read the play.</span>
          <span className="l2">Make the call.</span>
        </h1>
        <p className="hero-intro">
          A run/pass model trained on five seasons of NFL play-by-play. Test your
          pre-snap read against it.
        </p>
        <div className="hero-ctas">
          <Link className="btn btn-light" to="/quiz">
            Take the quiz <ChevronsRight />
          </Link>
          <button className="btn btn-line" onClick={demo.start} aria-busy={demo.busy}>
            {demo.label}
          </button>
        </div>
        <p className="hero-error" role="status">
          {demo.error}
        </p>
      </div>
      <div className="photo-clip" aria-hidden="true">
        <div className="spot" />
        <div className="ground" />
        <img className="hero-photo" src={heroPlayer} alt="" width={426} height={1015} fetchPriority="high" />
      </div>
      <DemoCard />
    </section>
  );
}

// Two real 2023 plays with the model's outputs as given in the design handoff.
const DEMO_PLAYS: {
  matchup: string;
  down: string;
  spot: string;
  context: string;
  actual: Call;
  desc: string;
  passPct: number;
}[] = [
  {
    matchup: "NYG offense vs WAS",
    down: "3rd & 13",
    spot: "At opp 48",
    context: "Q1 7:05 · Tied · 3 timeouts · Shotgun",
    actual: "pass",
    desc: "(7:05) (Shotgun) 15-T.DeVito pass deep middle to 86-D.Slayton to WAS 24 for 24 yards (35-P.Butler; 31-K.Curl).",
    passPct: 97,
  },
  {
    matchup: "SEA offense vs ARI, week 7",
    down: "1st & 10",
    spot: "At own 45",
    context: "Q4 4:58 · Leading by 7 · 2 timeouts · Under center",
    actual: "run",
    desc: "(4:58) 9-K.Walker left guard to SEA 47 for 2 yards (92-K.Strong; 98-R.Lopez).",
    passPct: 13,
  },
];
const modelRight = (p: (typeof DEMO_PLAYS)[number]) =>
  (p.passPct >= 50 ? "pass" : "run") === p.actual;

function DemoCard() {
  const [idx, setIdx] = useState(0);
  const [picked, setPicked] = useState<Call | null>(null);
  const [history, setHistory] = useState<boolean[]>([]);

  const total = DEMO_PLAYS.length;
  const done = idx >= total;
  const play = DEMO_PLAYS[Math.min(idx, total - 1)];
  const results = picked && !done ? [...history, picked === play.actual] : history;
  const played = results.length;
  const you = results.filter(Boolean).length;
  const model = DEMO_PLAYS.slice(0, played).filter(modelRight).length;

  const next = () => {
    setHistory(results);
    setIdx(idx + 1);
    setPicked(null);
  };
  const restart = () => {
    setHistory([]);
    setIdx(0);
    setPicked(null);
  };

  return (
    <RedCard
      className="demo"
      title="Call this one"
      label="Live demo of the quiz"
      aside={
        <span className="redcard-score" aria-live="polite">
          You {you}/{played}
          <br />
          Model {model}/{played}
        </span>
      }
    >
      {!done ? (
        <div>
          <div className="dc-meta">
            <span>{play.matchup}</span>
            <span>
              Play {idx + 1} of {total}
            </span>
          </div>
          <div className="dc-down cond">{play.down}</div>
          <div className="dc-spot">{play.spot}</div>
          <p className="dc-context">{play.context}</p>
          {!picked ? (
            <Picks onPick={setPicked} />
          ) : (
            <Reveal
              picked={picked}
              actual={play.actual}
              desc={play.desc}
              passPct={play.passPct}
              nextLabel={idx + 1 >= total ? "See score" : "Next play"}
              onNext={next}
            />
          )}
        </div>
      ) : (
        <div className="rise">
          <span className="dc-label">Demo complete</span>
          <div className="dc-final">
            <div>
              <span>You</span>
              <b className="cond">
                {you}/{total}
              </b>
            </div>
            <div>
              <span>Model</span>
              <b className="cond">
                {model}/{total}
              </b>
            </div>
          </div>
          <p className="dc-note">
            The full quiz is ten plays, with a running score against the model.
          </p>
          <div className="dc-actions">
            <Link className="btn btn-md btn-light" to="/quiz">
              Play all ten
            </Link>
            <button className="btn btn-next" onClick={restart}>
              Replay
            </button>
          </div>
        </div>
      )}
    </RedCard>
  );
}

function StatSection() {
  const ref = useRef<HTMLElement>(null);
  const p = useCountUp(ref);
  const shotgun = Math.round(97 * p);
  const under = Math.round(67 * p);
  return (
    <section className="panel stat pad" ref={ref}>
      <div className="stat-in">
        <span className="chip">Same down. Same spot.</span>
        <h2 className="cond">3rd &amp; 8 from the 45. How likely is a pass?</h2>
        <p className="stat-lede">
          The model's answer for the exact same situation. The only thing that
          changes is where the quarterback lines up.
        </p>
        <Meter label="Shotgun" sub="QB five yards back" value={shotgun} final={97} accent />
        <Meter label="Under center" sub="QB right behind the center" value={under} final={67} />
        <div className="gap" aria-hidden="true" style={{ opacity: shotgun >= 97 ? 1 : 0 }}>
          <div className="gap-bracket" />
          <span>30 points</span>
        </div>
      </div>
    </section>
  );
}

function Meter({
  label,
  sub,
  value,
  final,
  accent,
}: {
  label: string;
  sub: string;
  value: number;
  final: number;
  accent?: boolean;
}) {
  return (
    <div className="meter">
      <div className="meter-head">
        <div>
          <div className="meter-label">{label}</div>
          <div className="meter-sub">{sub}</div>
        </div>
        <div className={accent ? "meter-num cond is-acc" : "meter-num cond"}>{value}%</div>
      </div>
      <div className="track" role="img" aria-label={`${label}: ${final}% pass`}>
        <div className={accent ? "is-acc" : undefined} style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

// League 3rd-down pass rate by yards to go, nflverse 2019-2023 regular season.
const HEAT_COLS = ["1-2", "3-4", "5-7", "8-10", "11+"];
const HEAT_ROWS: [string, number[]][] = [
  ["Shotgun", [58, 88, 95, 97, 92]],
  ["Under center", [21, 41, 30, 19, 20]],
];
const P2 = [0x1b, 0x1b, 0x1b];
const ACC = [0xff, 0x2d, 0x20];
const tint = (v: number) => {
  const k = Math.pow(v / 100, 1.6);
  return `rgb(${P2.map((x, i) => Math.round(x + (ACC[i] - x) * k)).join(",")})`;
};

const TABS = [
  ["call", "01", "Call it"],
  ["scout", "02", "Scout a team"],
  ["film", "03", "Use your film"],
] as const;
type Tab = (typeof TABS)[number][0];

function Ways() {
  const [tab, setTab] = useState<Tab>("call");
  const demo = useStartDemo();
  return (
    <section id="ways" className="panel ways fx pad">
      <div className="ways-grid">
        <div>
          <span className="chip chip-ink">Ways in</span>
          <h2 className="cond">Three ways to use it</h2>
          <div className="tabs">
            {TABS.map(([k, n, label]) => (
              <button
                key={k}
                className={tab === k ? "tab on" : "tab"}
                aria-pressed={tab === k}
                onClick={() => setTab(k)}
              >
                <span>{n}</span>
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="tabpanel">
          {tab === "call" && (
            <div className="tabpanel-in rise" key="call">
              <div className="tcards">
                <div className="tcard">
                  <small>NYG offense vs WAS</small>
                  <div className="tcard-big cond">3rd &amp; 13</div>
                  <div className="tcard-foot">At opp 48 · Shotgun · Tied</div>
                </div>
                <div className="tcard tcard-model">
                  <small>Model says</small>
                  <div className="tcard-big cond is-acc">97%</div>
                  <div className="tcard-foot is-ink">Pass</div>
                </div>
              </div>
              <div className="tcta">
                <Link className="btn btn-md btn-light" to="/quiz">
                  Take the quiz
                </Link>
              </div>
            </div>
          )}

          {tab === "scout" && (
            <div className="tabpanel-in rise" key="scout">
              <div className="hm">
                <div className="hm-head">
                  <span>3rd down pass rate by yards to go</span>
                  <span>League, 2019 to 2023</span>
                </div>
                <div className="hm-grid" role="table" aria-label="3rd down pass rate by yards to go">
                  <div role="row" className="hm-rowgroup">
                    <span role="columnheader" />
                    {HEAT_COLS.map((c) => (
                      <span key={c} role="columnheader" className="hm-col">
                        {c}
                      </span>
                    ))}
                  </div>
                  {HEAT_ROWS.map(([label, vals]) => (
                    <div role="row" className="hm-rowgroup" key={label}>
                      <span role="rowheader" className="hm-row">
                        {label}
                      </span>
                      {vals.map((v, i) => (
                        <span
                          key={HEAT_COLS[i]}
                          role="cell"
                          className="hm-cell cond"
                          style={{ background: tint(v) }}
                        >
                          {v}%
                        </span>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
              <div className="tcta">
                <span className="tcta-error" role="status">
                  {demo.error}
                </span>
                <button className="btn btn-md btn-light" onClick={demo.start} aria-busy={demo.busy}>
                  {demo.label}
                </button>
              </div>
            </div>
          )}

          {tab === "film" && (
            <div className="tabpanel-in rise" key="film">
              <div className="drop">
                <svg
                  width="36"
                  height="36"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M12 16V4" />
                  <path d="M7 9l5-5 5 5" />
                  <path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
                </svg>
                <div className="drop-title cond">Your film goes here</div>
                <div className="drop-sub">A Hudl export or a charted CSV</div>
              </div>
              <div className="tcta">
                <Link className="btn btn-md btn-light" to="/login">
                  Sign in
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function SiteFooter() {
  return (
    <footer className="panel foot fx pad">
      <div className="foot-mark">engage eight</div>
      <div className="foot-row">
        <span>
          Plays and training data from{" "}
          <a href="https://github.com/nflverse" target="_blank" rel="noreferrer">
            nflverse
          </a>
          . The demo team is fictional.
        </span>
        <nav aria-label="Footer">
          <Link to="/quiz">Quiz</Link>
          <a href="#ways">Scout a team</a>
          <Link to="/login">Sign in</Link>
        </nav>
      </div>
    </footer>
  );
}
