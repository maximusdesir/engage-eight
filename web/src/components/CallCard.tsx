// The red "make the call" card used by the landing demo and the quiz: a title
// bar, Run/Pass buttons, and the reveal once you've answered.
import { useEffect, useRef, type ReactNode } from "react";
import type { Call } from "../quiz";

export function RedCard({
  title,
  aside,
  label,
  className = "",
  children,
}: {
  title: string;
  aside?: ReactNode;
  label: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <aside className={`redcard ${className}`} aria-label={label}>
      <div className="redcard-head">
        <span className="redcard-title cond">{title}</span>
        {aside}
      </div>
      <div className="redcard-body">{children}</div>
    </aside>
  );
}

export function Picks({
  onPick,
  large,
  keys,
}: {
  onPick: (c: Call) => void;
  large?: boolean;
  keys?: boolean;
}) {
  return (
    <div className={large ? "picks picks-lg" : "picks"}>
      <button
        className="pick pick-run cond"
        onClick={() => onPick("run")}
        aria-keyshortcuts={keys ? "R" : undefined}
      >
        Run
      </button>
      <button
        className="pick pick-pass cond"
        onClick={() => onPick("pass")}
        aria-keyshortcuts={keys ? "P" : undefined}
      >
        Pass
      </button>
    </div>
  );
}

export function Reveal({
  picked,
  actual,
  desc,
  passPct,
  verdict,
  nextLabel,
  onNext,
  large,
}: {
  picked: Call;
  actual: Call;
  desc: string;
  passPct: number;
  verdict?: string;
  nextLabel: string;
  onNext: () => void;
  large?: boolean;
}) {
  const runPct = 100 - passPct;
  const next = useRef<HTMLButtonElement>(null);
  // Keep keyboard focus in the card: the button that was pressed is gone now.
  useEffect(() => next.current?.focus({ preventScroll: true }), []);
  return (
    <div className={large ? "reveal reveal-lg rise" : "reveal rise"}>
      <div className="reveal-you">
        <b>{picked === actual ? "Right." : "Wrong."}</b>
        <span>You said {picked}.</span>
      </div>
      <div className="reveal-call cond">
        It was a <span className={actual === "pass" ? "is-pass" : undefined}>{actual}</span>.
      </div>
      <p className="reveal-desc">{desc}</p>
      <div
        className="split"
        role="img"
        aria-label={`Model: ${runPct}% run, ${passPct}% pass`}
      >
        <span className="split-run" style={{ width: `${runPct}%` }} />
        <span className="split-pass" style={{ width: `${passPct}%` }} />
      </div>
      <div className="split-labels">
        <span>Model: run {runPct}%</span>
        <span>pass {passPct}%</span>
      </div>
      {verdict && <p className="reveal-verdict">{verdict}</p>}
      <button
        ref={next}
        className="btn btn-next"
        onClick={onNext}
        aria-keyshortcuts="Enter"
      >
        {nextLabel}
      </button>
    </div>
  );
}
