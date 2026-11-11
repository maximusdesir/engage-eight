import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useStore } from "../store";
import {
  api,
  ApiError,
  type UploadRecord,
  type UploadSummary,
} from "../api/client";

export default function Upload() {
  const { activeTeam } = useStore();
  const [uploads, setUploads] = useState<UploadRecord[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState("auto");
  const [team, setTeam] = useState("");
  const [summary, setSummary] = useState<UploadSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const teamId = activeTeam?.id;
  const refresh = useCallback(async () => {
    if (teamId == null) return;
    try {
      setUploads(await api.listUploads(teamId));
    } catch {
      setUploads([]);
    }
  }, [teamId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  if (!activeTeam) {
    return (
      <div>
        <h1>Upload film breakdown</h1>
        <p className="subtitle">Create or select a team first (Teams screen).</p>
      </div>
    );
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setError(null);
    setSummary(null);
    setBusy(true);
    try {
      setSummary(await api.upload(activeTeam.id, file, source, team || null));
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (u: UploadRecord) => {
    if (!confirm(`Delete "${u.filename}" and its ${u.n_plays} plays?`)) return;
    setError(null);
    try {
      await api.deleteUpload(activeTeam.id, u.id);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Delete failed");
    }
  };

  const skippedTotal = summary
    ? Object.values(summary.skipped).reduce((a, b) => a + b, 0)
    : 0;

  const hasUnmapped =
    summary &&
    (summary.unmapped_formations.length > 0 ||
      summary.unmapped_motions.length > 0);

  return (
    <div>
      <h1>Upload film breakdown</h1>
      <p className="subtitle">
        Import a Hudl breakdown export or a manual charting CSV into{" "}
        {activeTeam.name}. Only you can see these plays. Formats are
        auto-detected; anything the vocabulary doesn't recognize is flagged for
        mapping.
      </p>

      <div className="card">
        <form className="stack" onSubmit={submit}>
          <div className="row">
            <div className="field">
              <label>CSV file</label>
              <input
                type="file"
                accept=".csv"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </div>
            <div className="field">
              <label>Format</label>
              <select value={source} onChange={(e) => setSource(e.target.value)}>
                <option value="auto">Auto-detect</option>
                <option value="hudl">Hudl</option>
                <option value="charting">Manual charting</option>
              </select>
            </div>
            <div className="field">
              <label>Opponent label (optional)</label>
              <input
                value={team}
                onChange={(e) => setTeam(e.target.value)}
                placeholder="LINCOLN"
              />
            </div>
            <button disabled={!file || busy}>
              {busy ? "Uploading…" : "Upload"}
            </button>
          </div>
        </form>
        {error && <div className="error">{error}</div>}
      </div>

      {summary && (
        <div className="card">
          <div className="ok">{summary.message}</div>
          <p className="muted">
            Detected format: <span className="pill">{summary.source}</span>{" "}
            Teams: {summary.teams.join(", ") || "—"}
          </p>

          {skippedTotal > 0 && (
            <div className="error">
              {summary.skipped.unknown_run_pass > 0 && (
                <p>
                  {summary.skipped.unknown_run_pass} plays were skipped because
                  run or pass couldn't be determined
                  {summary.unresolved_play_names.length > 0 && (
                    <>: {summary.unresolved_play_names.join(", ")}</>
                  )}
                  . Add a PLAY TYPE column (Run/Pass) to your export to include
                  them.
                </p>
              )}
              {summary.skipped.no_down > 0 && (
                <p>{summary.skipped.no_down} rows had no down and were skipped.</p>
              )}
            </div>
          )}

          {hasUnmapped ? (
            <>
              <p>
                Some formation/motion names aren't in the canonical vocabulary
                yet:
              </p>
              {summary.unmapped_formations.length > 0 && (
                <p>
                  <strong>Formations:</strong>{" "}
                  {summary.unmapped_formations.map((f) => (
                    <span key={f} className="pill warn" style={{ marginRight: 6 }}>
                      {f}
                    </span>
                  ))}
                </p>
              )}
              {summary.unmapped_motions.length > 0 && (
                <p>
                  <strong>Motions:</strong>{" "}
                  {summary.unmapped_motions.map((m) => (
                    <span key={m} className="pill warn" style={{ marginRight: 6 }}>
                      {m}
                    </span>
                  ))}
                </p>
              )}
              <Link to="/vocabulary">
                <button>Map these on the Vocabulary screen →</button>
              </Link>
            </>
          ) : (
            <p className="muted">
              All formation/motion names matched the vocabulary.
            </p>
          )}
        </div>
      )}

      <div className="card">
        <h1 style={{ fontSize: 16 }}>Uploads in {activeTeam.name}</h1>
        {uploads.length === 0 ? (
          <div className="muted">Nothing uploaded yet.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>File</th>
                <th>Format</th>
                <th>Plays</th>
                <th>Uploaded</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {uploads.map((u) => (
                <tr key={u.id}>
                  <td>{u.filename}</td>
                  <td>{u.source}</td>
                  <td>{u.n_plays}</td>
                  <td>{new Date(u.created_at + "Z").toLocaleString()}</td>
                  <td>
                    <button className="secondary" onClick={() => remove(u)}>
                      Delete
                    </button>
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
