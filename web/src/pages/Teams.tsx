import { useState } from "react";
import { useStore } from "../store";
import { api, ApiError } from "../api/client";

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
      setError(err instanceof ApiError ? err.message : "Failed to create team");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <h1>Teams</h1>
      <p className="subtitle">
        A team is your scouting workspace. The active team drives the vocabulary
        mapping used across screens.
      </p>

      <div className="card">
        <form className="row" onSubmit={create}>
          <div className="field">
            <label>Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Lincoln HS"
              required
            />
          </div>
          <div className="field">
            <label>Level</label>
            <select value={level} onChange={(e) => setLevel(e.target.value)}>
              <option value="hs">High school</option>
              <option value="college">College</option>
              <option value="nfl">NFL</option>
              <option value="club">Club</option>
            </select>
          </div>
          <div className="field">
            <label>Season</label>
            <input
              type="number"
              value={season}
              onChange={(e) => setSeason(e.target.value)}
              style={{ width: 100 }}
            />
          </div>
          <button disabled={busy}>Add team</button>
        </form>
        {error && <div className="error">{error}</div>}
      </div>

      <div className="card">
        {teams.length === 0 ? (
          <div className="muted">No teams yet. Create one above.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Level</th>
                <th>Season</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {teams.map((t) => (
                <tr key={t.id}>
                  <td>{t.name}</td>
                  <td>{t.level}</td>
                  <td>{t.season ?? "—"}</td>
                  <td>
                    {activeTeam?.id === t.id ? (
                      <span className="pill">active</span>
                    ) : (
                      <button
                        className="secondary"
                        onClick={() => setActiveTeam(t)}
                      >
                        Set active
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
