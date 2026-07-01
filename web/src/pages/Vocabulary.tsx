import { useEffect, useState } from "react";
import { useStore } from "../store";
import {
  api,
  ApiError,
  type MappingIn,
  type VocabResponse,
} from "../api/client";
import CanonicalPicker from "../components/CanonicalPicker";

export default function Vocabulary() {
  const { activeTeam } = useStore();
  const [vocab, setVocab] = useState<VocabResponse | null>(null);
  const [teamFilter, setTeamFilter] = useState("");
  const [choices, setChoices] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    if (!activeTeam) return;
    setError(null);
    try {
      setVocab(await api.getVocab(activeTeam.id, teamFilter || null));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load vocab");
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTeam?.id]);

  if (!activeTeam) {
    return (
      <div>
        <h1>Vocabulary</h1>
        <p className="subtitle">Select a team first (Teams screen).</p>
      </div>
    );
  }

  const key = (kind: string, raw: string) => `${kind}::${raw}`;

  const save = async () => {
    if (!vocab) return;
    const mappings: MappingIn[] = [];
    for (const raw of vocab.unmapped.formations) {
      const c = choices[key("formation", raw)];
      if (c) mappings.push({ kind: "formation", raw_value: raw, canonical_value: c });
    }
    for (const raw of vocab.unmapped.motions) {
      const c = choices[key("motion", raw)];
      if (c) mappings.push({ kind: "motion", raw_value: raw, canonical_value: c });
    }
    if (mappings.length === 0) {
      setError("Choose a canonical value for at least one row.");
      return;
    }
    setError(null);
    setMsg(null);
    setBusy(true);
    try {
      await api.setVocab(activeTeam.id, mappings);
      setChoices({});
      setMsg(`Saved ${mappings.length} mapping(s).`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  };

  const unmappedRows = vocab
    ? [
        ...vocab.unmapped.formations.map((r) => ({ kind: "formation" as const, raw: r })),
        ...vocab.unmapped.motions.map((r) => ({ kind: "motion" as const, raw: r })),
      ]
    : [];

  return (
    <div>
      <h1>Vocabulary</h1>
      <p className="subtitle">
        Map this team's formation/motion names onto the canonical vocabulary so
        naming variants combine. Changes apply on read — no re-import needed.
      </p>

      <div className="card">
        <div className="row">
          <div className="field">
            <label>Offense team filter (optional)</label>
            <input
              value={teamFilter}
              onChange={(e) => setTeamFilter(e.target.value)}
              placeholder="e.g. LINCOLN"
            />
          </div>
          <button className="secondary" onClick={load}>
            Refresh
          </button>
        </div>
      </div>

      <div className="card">
        <h1 style={{ fontSize: 16 }}>Unmapped values</h1>
        {error && <div className="error">{error}</div>}
        {msg && <div className="ok">{msg}</div>}
        {unmappedRows.length === 0 ? (
          <div className="muted">
            Nothing to map — every formation/motion is recognized.
          </div>
        ) : (
          <>
            <table>
              <thead>
                <tr>
                  <th>Kind</th>
                  <th>Raw value</th>
                  <th>Canonical</th>
                </tr>
              </thead>
              <tbody>
                {unmappedRows.map(({ kind, raw }) => (
                  <tr key={key(kind, raw)}>
                    <td>
                      <span className="pill">{kind}</span>
                    </td>
                    <td>{raw}</td>
                    <td>
                      <CanonicalPicker
                        options={
                          kind === "formation"
                            ? vocab!.canonical.formations
                            : vocab!.canonical.motions
                        }
                        value={choices[key(kind, raw)] ?? ""}
                        onChange={(v) =>
                          setChoices((c) => ({ ...c, [key(kind, raw)]: v }))
                        }
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <button style={{ marginTop: 14 }} onClick={save} disabled={busy}>
              {busy ? "Saving…" : "Save mappings"}
            </button>
          </>
        )}
      </div>

      {vocab && vocab.mappings.length > 0 && (
        <div className="card">
          <h1 style={{ fontSize: 16 }}>Existing mappings</h1>
          <table>
            <thead>
              <tr>
                <th>Kind</th>
                <th>Raw value</th>
                <th>Canonical</th>
              </tr>
            </thead>
            <tbody>
              {vocab.mappings.map((m) => (
                <tr key={m.id}>
                  <td>
                    <span className="pill">{m.kind}</span>
                  </td>
                  <td>{m.raw_value}</td>
                  <td>{m.canonical_value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
