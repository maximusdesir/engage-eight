// Thin typed client for the Engage Eight API. Reads the base URL from
// VITE_API_BASE_URL (default localhost:8000) and attaches the stored JWT.

const BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

const TOKEN_KEY = "engage8_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type Options = {
  method?: string;
  body?: unknown;
  form?: URLSearchParams;
  formData?: FormData;
  auth?: boolean;
};

async function request<T>(path: string, opts: Options = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (opts.auth !== false) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  let body: BodyInit | undefined;
  if (opts.formData) {
    body = opts.formData; // browser sets multipart boundary
  } else if (opts.form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    body = opts.form;
  } else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    method: opts.method ?? (body ? "POST" : "GET"),
    headers,
    body,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      if (data?.detail) detail = typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail);
    } catch {
      // non-JSON error body; keep statusText
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// --- Types (mirror the API's Pydantic schemas) -----------------------------

export type User = { id: number; email: string; role: string };
export type Team = { id: number; name: string; level: string; season: number | null };

export type TendencyRow = {
  bucket: string;
  plays: number;
  run_pct: number;
  pass_pct: number;
  explosive_pct: number | null;
  avg_epa: number | null;
  top_play: string;
};
export type TendencyResponse = {
  team_id: number;
  team: string | null;
  split: string;
  rows: TendencyRow[];
};

export type UploadSummary = {
  upload_id: number;
  inserted: number;
  teams: string[];
  source: string;
  message: string;
  unmapped_formations: string[];
  unmapped_motions: string[];
  skipped: Record<string, number>;
  unresolved_play_names: string[];
};

export type UploadRecord = {
  id: number;
  team_id: number;
  opponent_id: number | null;
  filename: string;
  source: string;
  n_plays: number;
  created_at: string;
};

export type PredictRequest = {
  down: number;
  distance: number;
  yardline_100: number;
  quarter?: number;
  game_seconds_remaining?: number | null;
  score_differential?: number;
  shotgun?: boolean | null;
  no_huddle?: boolean | null;
  // Opponent blend: uses this team's uploaded plays for offense_team.
  team_id?: number | null;
  offense_team?: string | null;
  formation?: string | null;
  motion_type?: string | null;
};
export type BlendStep = {
  label: string;
  plays: number;
  pass_rate: number;
  pass_prob_after: number;
};
export type PredictResponse = {
  pass_prob: number;
  run_prob: number;
  lean: "RUN" | "PASS";
  confidence: number;
  why: string;
  model_pass_prob: number;
  blend: BlendStep[];
};
export type DefensiveCall = {
  front: string;
  coverage: string;
  pressure: string;
  stunt: string;
  rationale: string;
};
export type RecommendResponse = {
  predicted: PredictResponse;
  recommendations: DefensiveCall[];
  basis: string;
};

export type VocabMapping = {
  id: number;
  kind: "formation" | "motion";
  raw_value: string;
  canonical_value: string;
};
export type VocabResponse = {
  canonical: { formations: string[]; motions: string[] };
  mappings: VocabMapping[];
  unmapped: { formations: string[]; motions: string[] };
};
export type MappingIn = {
  kind: "formation" | "motion";
  raw_value: string;
  canonical_value: string;
};

export const SPLITS = [
  "down_distance",
  "field_zone",
  "formation",
  "motion",
  "quarter",
  "hash",
] as const;
export type Split = (typeof SPLITS)[number];

// --- Endpoint helpers ------------------------------------------------------

export const api = {
  signup: (email: string, password: string) =>
    request<User>("/auth/signup", { body: { email, password }, auth: false }),

  login: async (email: string, password: string) => {
    const form = new URLSearchParams({ username: email, password });
    const { access_token } = await request<{ access_token: string }>(
      "/auth/login",
      { form, auth: false }
    );
    setToken(access_token);
    return access_token;
  },

  me: () => request<User>("/auth/me"),

  listTeams: () => request<Team[]>("/teams"),
  createTeam: (name: string, level: string, season: number | null) =>
    request<Team>("/teams", { body: { name, level, season } }),

  // Everything below is scoped to one of the signed-in user's teams.
  upload: (teamId: number, file: File, source: string, team: string | null) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("source", source);
    if (team) fd.append("team", team);
    return request<UploadSummary>(`/teams/${teamId}/uploads`, { formData: fd });
  },
  listUploads: (teamId: number) =>
    request<UploadRecord[]>(`/teams/${teamId}/uploads`),
  deleteUpload: (teamId: number, uploadId: number) =>
    request<void>(`/teams/${teamId}/uploads/${uploadId}`, { method: "DELETE" }),

  tendencies: (teamId: number, split: Split, team: string | null) => {
    const p = new URLSearchParams({ split });
    if (team) p.set("team", team);
    return request<TendencyResponse>(`/teams/${teamId}/tendencies?${p.toString()}`);
  },

  predict: (req: PredictRequest) =>
    request<PredictResponse>("/predict", { body: req }),
  recommend: (req: PredictRequest) =>
    request<RecommendResponse>("/recommend", { body: req }),

  getVocab: (teamId: number, team: string | null) => {
    const p = new URLSearchParams();
    if (team) p.set("team", team);
    const qs = p.toString();
    return request<VocabResponse>(
      `/teams/${teamId}/vocab${qs ? `?${qs}` : ""}`
    );
  },
  setVocab: (teamId: number, mappings: MappingIn[]) =>
    request<VocabMapping[]>(`/teams/${teamId}/vocab`, { body: mappings }),
};
