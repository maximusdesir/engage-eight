# Engage Eight web dashboard

A Vite + React (TypeScript) dashboard over the Engage Eight API. Coaches sign
in, upload film breakdowns, browse tendencies, map their formation/motion
vocabulary, and run predict/recommend in the browser instead of the API docs.

## Run

The API must be running first (see `../api`):

```
cd ../api
uvicorn app.main:app --reload        # serves http://localhost:8000
```

Then, in this folder:

```
npm install
npm run dev                          # serves http://localhost:5173
```

The dev origin (`http://localhost:5173`) is already in the API's CORS allowlist.

## Config

`VITE_API_BASE_URL` sets the API base URL (default `http://localhost:8000`).
Copy `.env.example` to `.env.local` to override.

## Screens

- **Tendencies** — run/pass split + top play per bucket, split by down &
  distance, field zone, formation, pre-snap motion, quarter, or hash. Formation
  and motion buckets fold naming variants onto the canonical vocabulary using
  the active team's mapping.
- **Predict / Recommend** — score a pre-snap situation and get ranked defensive
  calls. Formation/motion dropdowns come from the canonical vocabulary.
- **Upload** — import a Hudl breakdown or manual charting CSV; unrecognized
  formation/motion names are surfaced for mapping.
- **Vocabulary** — map this team's raw formation/motion names onto the canonical
  vocabulary. Text-based today; `src/components/CanonicalPicker.tsx` is the seam
  for the planned picture/diagram picker (swap the `<select>` for a diagram grid
  and nothing else changes).
- **Teams** — create teams and pick the active one.

## Build

```
npm run build      # tsc -b && vite build -> dist/
```
