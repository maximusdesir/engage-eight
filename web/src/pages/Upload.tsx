import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useStore } from "../useStore";
import {
  api,
  ApiError,
  type UploadRecord,
  type UploadSummary,
} from "../api/client";
import PageHead, { NeedsTeam } from "../components/PageHead";

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

  if (!activeTeam) return <NeedsTeam title="Upload" />;

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
      setError(err instanceof ApiError ? err.message : "Upload failed.");
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
      setError(err instanceof ApiError ? err.message : "Delete failed.");
    }
  };

  const skippedTotal = summary
    ? Object.values(summary.skipped).reduce((a, b) => a + b, 0)
    : 0;

  const hasUnmapped =
    summary &&
    (summary.unmapped_formations.length > 0 || summary.unmapped_motions.length > 0);

  return (
    <div>
      <PageHead title="Upload film">
        Import a Hudl breakdown export or a hand-charted CSV into{" "}
        {activeTeam.name}. Only you can see these plays. The format is detected
        for you, and names the vocabulary doesn't know are flagged for mapping.
      </PageHead>

      <section className="card">
        <form className="row" onSubmit={submit}>
          <label className="field">
            <span>CSV file</span>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>
          <label className="field">
            <span>Format</span>
            <select value={source} onChange={(e) => setSource(e.target.value)}>
              <option value="auto">Detect it</option>
              <option value="hudl">Hudl</option>
              <option value="charting">Hand charting</option>
            </select>
          </label>
          <label className="field">
            <span>Opponent label (optional)</span>
            <input value={team} onChange={(e) => setTeam(e.target.value)} placeholder="LINCOLN" />
          </label>
          <button className="btn btn-md btn-light" disabled={!file || busy} aria-busy={busy}>
            {busy ? "Uploading…" : "Upload"}
          </button>
        </form>
        {error && <div className="msg error" role="alert">{error}</div>}
      </section>

      {summary && (
        <section className="card" aria-live="polite">
          <h2 className="card-title cond">Imported</h2>
          <div className="msg ok" role="status">
            {summary.message}
          </div>
          <p className="muted" style={{ marginTop: 14 }}>
            Format: <span className="pill">{summary.source}</span> · Teams:{" "}
            {summary.teams.join(", ") || "—"}
          </p>

          {skippedTotal > 0 && (
            <div className="msg error">
              <div>
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
            </div>
          )}

          {hasUnmapped ? (
            <div style={{ marginTop: 18 }}>
              <p>Some names aren't in the vocabulary yet:</p>
              {summary.unmapped_formations.length > 0 && (
                <>
                  <p className="muted">Formations</p>
                  <div className="pills">
                    {summary.unmapped_formations.map((f) => (
                      <span key={f} className="pill pill-warn">{f}</span>
                    ))}
                  </div>
                </>
              )}
              {summary.unmapped_motions.length > 0 && (
                <>
                  <p className="muted">Motions</p>
                  <div className="pills">
                    {summary.unmapped_motions.map((m) => (
                      <span key={m} className="pill pill-warn">{m}</span>
                    ))}
                  </div>
                </>
              )}
              <Link className="btn btn-md btn-light" to="/vocabulary">
                Map them on the Vocabulary screen
              </Link>
            </div>
          ) : (
            <p className="muted">Every formation and motion name matched the vocabulary.</p>
          )}
        </section>
      )}

      <section className="card">
        <h2 className="card-title cond">Uploads in {activeTeam.name}</h2>
        {uploads.length === 0 ? (
          <p className="muted">Nothing uploaded yet.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>File</th>
                  <th>Format</th>
                  <th className="num">Plays</th>
                  <th>Uploaded</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {uploads.map((u) => (
                  <tr key={u.id}>
                    <td className="strong">{u.filename}</td>
                    <td>{u.source}</td>
                    <td className="num">{u.n_plays}</td>
                    <td>{new Date(u.created_at + "Z").toLocaleString()}</td>
                    <td className="num">
                      <button
                        className="btn btn-sm btn-line btn-danger"
                        onClick={() => remove(u)}
                        aria-label={`Delete ${u.filename}`}
                      >
                        Delete
                      </button>
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
