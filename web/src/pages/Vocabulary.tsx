import { useEffect, useState } from "react";
import { useStore } from "../useStore";
import {
  api,
  ApiError,
  type MappingIn,
  type VocabResponse,
} from "../api/client";
import CanonicalPicker from "../components/CanonicalPicker";
import PageHead, { NeedsTeam } from "../components/PageHead";

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
      setError(err instanceof ApiError ? err.message : "Couldn't load the vocabulary.");
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTeam?.id]);

  if (!activeTeam) return <NeedsTeam title="Vocabulary" />;

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
      setError("Pick a standard name for at least one row.");
      return;
    }
    setError(null);
    setMsg(null);
    setBusy(true);
    try {
      await api.setVocab(activeTeam.id, mappings);
      setChoices({});
      setMsg(`Saved ${mappings.length} mapping${mappings.length === 1 ? "" : "s"}.`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed.");
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
      <PageHead title="Vocabulary">
        Map this team's formation and motion names onto standard ones, so
        "Trips Rt" and "TRIPS" count as the same thing. Changes apply right
        away, with no re-upload.
      </PageHead>

      <section className="card">
        <form
          className="row"
          onSubmit={(e) => {
            e.preventDefault();
            load();
          }}
        >
          <label className="field">
            <span>Offense (optional)</span>
            <input
              value={teamFilter}
              onChange={(e) => setTeamFilter(e.target.value)}
              placeholder="e.g. LINCOLN"
            />
          </label>
          <button className="btn btn-md btn-line">Refresh</button>
        </form>
      </section>

      <section className="card">
        <h2 className="card-title cond">Needs mapping</h2>
        {error && <div className="msg error" role="alert">{error}</div>}
        {msg && <div className="msg ok" role="status">{msg}</div>}
        {unmappedRows.length === 0 ? (
          <p className="muted" style={{ marginTop: error || msg ? 14 : 0 }}>
            Nothing to map. Every formation and motion name is recognized.
          </p>
        ) : (
          <>
            <div className="table-wrap" style={{ marginTop: error || msg ? 14 : 0 }}>
              <table>
                <thead>
                  <tr>
                    <th>Kind</th>
                    <th>Name in your film</th>
                    <th>Standard name</th>
                  </tr>
                </thead>
                <tbody>
                  {unmappedRows.map(({ kind, raw }) => (
                    <tr key={key(kind, raw)}>
                      <td>
                        <span className="pill">{kind}</span>
                      </td>
                      <td className="strong">{raw}</td>
                      <td>
                        <CanonicalPicker
                          label={`Standard name for ${raw}`}
                          options={
                            kind === "formation"
                              ? vocab!.canonical.formations
                              : vocab!.canonical.motions
                          }
                          value={choices[key(kind, raw)] ?? ""}
                          onChange={(v) => setChoices((c) => ({ ...c, [key(kind, raw)]: v }))}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <button
              className="btn btn-md btn-light"
              style={{ marginTop: 18 }}
              onClick={save}
              disabled={busy}
              aria-busy={busy}
            >
              {busy ? "Saving…" : "Save mappings"}
            </button>
          </>
        )}
      </section>

      {vocab && vocab.mappings.length > 0 && (
        <section className="card">
          <h2 className="card-title cond">Saved mappings</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Kind</th>
                  <th>Name in your film</th>
                  <th>Standard name</th>
                </tr>
              </thead>
              <tbody>
                {vocab.mappings.map((m) => (
                  <tr key={m.id}>
                    <td>
                      <span className="pill">{m.kind}</span>
                    </td>
                    <td className="strong">{m.raw_value}</td>
                    <td>{m.canonical_value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
