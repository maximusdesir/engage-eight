// Title block at the top of each signed-in screen.
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

export default function PageHead({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <header className="page-head">
      <h1 className="page-title cond">{title}</h1>
      {children && <p className="page-lede">{children}</p>}
    </header>
  );
}

/** Shown on team-scoped screens before any team exists or is selected. */
export function NeedsTeam({ title }: { title: string }) {
  return (
    <PageHead title={title}>
      Create or pick a team first on the{" "}
      <Link className="linkish" to="/teams">
        Teams
      </Link>{" "}
      screen.
    </PageHead>
  );
}
