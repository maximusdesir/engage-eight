import { useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, type UploadSummary } from "../api/client";

export default function Upload() {
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState("auto");
  const [team, setTeam] = useState("");
  const [summary, setSummary] = useState<UploadSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setError(null);
    setSummary(null);
    setBusy(true);
    try {
      setSummary(await api.upload(file, source, team || null));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  const hasUnmapped =
    summary &&
    (summary.unmapped_formations.length > 0 ||
      summary.unmapped_motions.length > 0);

  return (
    <div>
      <h1>Upload film breakdown</h1>
      <p className="subtitle">
        Import a Hudl breakdown export or a manual charting CSV. Formats are
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
              <label>Label team (optional)</label>
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
    </div>
  );
}
