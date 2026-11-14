import { useState } from "react";
import { useStore } from "../useStore";
import { api, ApiError } from "../api/client";
import PageHead from "../components/PageHead";

const LEVELS: Record<string, string> = {
  hs: "High school",
  college: "College",
  nfl: "NFL",
  club: "Club",
};

export default function Teams() {
  const { teams, activeTeam, setActiveTeam, refreshTeams } = useStore();
  const [name, setName] = useState("");
  const [level, setLevel] = useState("hs");
  const [season, setSeason] = useState<string>(String(new Date().getFullYear()));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const team = await api.createTeam(name, level, season ? Number(season) : null);
      setName("");
      await refreshTeams();
      setActiveTeam(team);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't create the team.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHead title="Teams">
        A team is your scouting workspace: its uploads, plays, and vocabulary
        are private to you. The active team is the one every screen works on.
      </PageHead>

      <section className="card">
        <h2 className="card-title cond">Add a team</h2>
        <form className="row" onSubmit={create}>
          <label className="field">
            <span>Name</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Lincoln HS"
              required
            />
          </label>
          <label className="field">
            <span>Level</span>
            <select value={level} onChange={(e) => setLevel(e.target.value)}>
              {Object.entries(LEVELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Season</span>
            <input
              className="w-sm"
              type="number"
              value={season}
              onChange={(e) => setSeason(e.target.value)}
            />
          </label>
          <button className="btn btn-md btn-light" disabled={busy}>
            Add team
          </button>
        </form>
        {error && <div className="msg error" role="alert">{error}</div>}
      </section>

      <section className="card">
        <h2 className="card-title cond">Your teams</h2>
        {teams.length === 0 ? (
          <p className="muted">No teams yet. Add one above.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Level</th>
                  <th className="num">Season</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {teams.map((t) => (
                  <tr key={t.id}>
                    <td className="strong">{t.name}</td>
                    <td>{LEVELS[t.level] ?? t.level}</td>
                    <td className="num">{t.season ?? "—"}</td>
                    <td className="num">
                      {activeTeam?.id === t.id ? (
                        <span className="pill pill-on">Active</span>
                      ) : (
                        <button className="btn btn-sm btn-line" onClick={() => setActiveTeam(t)}>
                          Make active
                        </button>
                      )}
                    </td>
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
