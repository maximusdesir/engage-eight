"""End-to-end smoke test for the Engage Eight API (uses FastAPI TestClient)."""
import os
import tempfile

# Use a throwaway DB so the test never touches a real one.
os.environ["ENGAGE8_DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='.db')}"

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import init_db

init_db()  # create tables (lifespan startup only fires under a context manager)
c = TestClient(app)
ok = 0


def check(label, cond, extra=""):
    global ok
    mark = "PASS" if cond else "FAIL"
    if cond:
        ok += 1
    print(f"  [{mark}] {label} {extra}")
    assert cond, label


# 1. health
r = c.get("/health")
check("GET /health", r.status_code == 200, r.json())

# 2. auth: signup + login + me
r = c.post("/auth/signup", json={"email": "coach@engage8.app", "password": "pw12345"})
check("POST /auth/signup", r.status_code in (200, 201), r.status_code)

r = c.post("/auth/login", data={"username": "coach@engage8.app", "password": "pw12345"})
check("POST /auth/login", r.status_code == 200, r.status_code)
token = r.json()["access_token"]
auth = {"Authorization": f"Bearer {token}"}

r = c.get("/auth/me", headers=auth)
check("GET /auth/me", r.status_code == 200 and r.json()["email"] == "coach@engage8.app")

# 3. teams + opponents
r = c.post("/teams", json={"name": "My HS", "level": "hs", "season": 2026}, headers=auth)
check("POST /teams", r.status_code in (200, 201), r.status_code)
team_id = r.json()["id"]

r = c.get("/teams", headers=auth)
check("GET /teams", r.status_code == 200 and len(r.json()) == 1)

r = c.post(f"/teams/{team_id}/opponents", json={"name": "Central", "oc_name": "Smith"}, headers=auth)
check("POST /teams/{id}/opponents", r.status_code in (200, 201), r.status_code)

# 4. auth enforcement
r = c.get("/teams")
check("GET /teams without token -> 401", r.status_code == 401, r.status_code)

# 5. prediction (uses the trained ml model). A 503 means no model artifact is
# present yet (train the ml pipeline to enable it); the rest of the suite still
# exercises the API without it.
model_ready = True
r = c.post("/predict", json={"down": 3, "distance": 8, "yardline_100": 45, "quarter": 4})
check("POST /predict", r.status_code in (200, 503), r.text[:200])
if r.status_code == 200:
    body = r.json()
    print(f"        -> pass {body['pass_prob']:.0%} / run {body['run_prob']:.0%}, {body['lean']}")
else:
    model_ready = False
    print("        -> model not trained; skipping predict/recommend assertions")

# 6. recommendation
if model_ready:
    r = c.post("/recommend", json={"down": 3, "distance": 1, "yardline_100": 3})
    check("POST /recommend", r.status_code == 200, r.status_code)
    if r.status_code == 200:
        recs = r.json()["recommendations"]
        print(f"        -> top call: {recs[0]['front']} / {recs[0]['coverage']} / {recs[0]['pressure']}")

# 7. plays + tendencies
for pt, dn, dist in [("run", 1, 10), ("pass", 3, 8), ("run", 2, 2), ("pass", 3, 9)]:
    c.post("/plays", json={"offense_team": "CENTRAL", "down": dn, "ydstogo": dist,
                           "yardline_100": 50, "play_type": pt, "quarter": 1}, headers=auth)
r = c.get("/plays", headers=auth, params={"offense_team": "CENTRAL"})
check("GET /plays", r.status_code == 200 and len(r.json()) >= 4, len(r.json()))

r = c.get("/tendencies", params={"team": "CENTRAL", "split": "down_distance"})
check("GET /tendencies", r.status_code == 200, r.status_code)
if r.status_code == 200:
    print(f"        -> {len(r.json()['rows'])} tendency buckets")

r = c.get("/tendencies", params={"split": "not_a_split"})
check("GET /tendencies bad split -> 400", r.status_code == 400, r.status_code)

# 8. uploads now require auth (fix #3)
csv = ("offense_team,down,ydstogo,yardline_100,play_type,result_yards\n"
       "CENTRAL,1,10,75,run,5\nCENTRAL,3,8,40,pass,12\n")
r = c.post("/uploads", files={"file": ("chart.csv", csv, "text/csv")})
check("POST /uploads without token -> 401", r.status_code == 401, r.status_code)

r = c.post("/uploads", files={"file": ("chart.csv", csv, "text/csv")}, headers=auth)
check("POST /uploads with token", r.status_code == 200, r.text[:200])
if r.status_code == 200:
    print(f"        -> inserted {r.json()['inserted']} plays")

# 8b. Hudl CSV upload, format auto-detected, team labeled
# "Diamond" is a team-specific name the built-in vocab doesn't know, so it
# surfaces as unmapped; "Trips Rt" auto-folds to canonical TRIPS.
hudl_csv = ("PLAY #,ODK,DN,DIST,YARD LN,HASH,OFF FORM,OFF PLAY,PLAY TYPE,MOTION,PERS,GN/LS,QTR\n"
            "1,O,1,10,-25,L,Diamond,Inside Zone,Run,Jet,11,5,1\n"
            "2,O,3,8,+35,R,Empty,Four Verticals,Pass,,10,12,2\n"
            "3,D,1,10,+20,L,,,,,,0,2\n")
r = c.post("/uploads", data={"source": "auto", "team": "LINCOLN"},
           files={"file": ("export.csv", hudl_csv, "text/csv")}, headers=auth)
detected = r.json().get("source") if r.status_code == 200 else None
check("POST /uploads Hudl (auto-detected)",
      r.status_code == 200 and detected == "hudl" and r.json()["inserted"] == 2
      and "LINCOLN" in r.json()["teams"], r.text[:200])
if r.status_code == 200:
    print(f"        -> detected '{detected}', inserted {r.json()['inserted']} (defense row dropped)")

# 8c. motion tendency split works on the ingested Hudl motion data
r = c.get("/tendencies", params={"team": "LINCOLN", "split": "motion"})
check("GET /tendencies split=motion",
      r.status_code == 200 and len(r.json()["rows"]) >= 1, r.text[:200])
if r.status_code == 200:
    buckets = {row["bucket"] for row in r.json()["rows"]}
    print(f"        -> motion buckets: {sorted(buckets)}")

# 8d. Hudl upload surfaced unmapped formation raws ("Trips Rt" not built-in)
r = c.post("/uploads", data={"source": "auto", "team": "LINCOLN"},
           files={"file": ("export2.csv", hudl_csv, "text/csv")}, headers=auth)
unmapped_f = r.json().get("unmapped_formations", []) if r.status_code == 200 else []
check("upload surfaces unmapped formations",
      r.status_code == 200 and "Diamond" in unmapped_f, unmapped_f)

# 8e. vocab: GET options + unmapped, POST a mapping, confirm it clears
r = c.get(f"/teams/{team_id}/vocab", params={"team": "LINCOLN"}, headers=auth)
check("GET /teams/{id}/vocab",
      r.status_code == 200 and "TRIPS" in r.json()["canonical"]["formations"]
      and "Diamond" in r.json()["unmapped"]["formations"], r.text[:200])

r = c.post(f"/teams/{team_id}/vocab", headers=auth,
           json=[{"kind": "formation", "raw_value": "Diamond", "canonical_value": "TRIPS"}])
check("POST /teams/{id}/vocab", r.status_code == 200
      and r.json()[0]["canonical_value"] == "TRIPS", r.text[:200])

r = c.get(f"/teams/{team_id}/vocab", params={"team": "LINCOLN"}, headers=auth)
check("mapping clears the unmapped value",
      r.status_code == 200 and "Diamond" not in r.json()["unmapped"]["formations"],
      r.json()["unmapped"]["formations"])

# 8f. tendencies with team_id applies the mapping (raw folds to canonical TRIPS),
# but team_id is a private, per-team resource (same data /teams/{id}/vocab
# guards), so it requires auth + ownership -- not just a public split query.
r = c.get("/tendencies", params={"team": "LINCOLN", "split": "formation", "team_id": team_id},
          headers=auth)
check("GET /tendencies split=formation with team_id maps to TRIPS",
      r.status_code == 200 and "TRIPS" in {row["bucket"] for row in r.json()["rows"]},
      r.text[:200])

r = c.get("/tendencies", params={"split": "formation", "team_id": team_id})
check("GET /tendencies with team_id, no token -> 401", r.status_code == 401, r.status_code)

r2 = c.post("/auth/signup", json={"email": "other-coach@engage8.app", "password": "pw12345"})
other_token = c.post("/auth/login", data={"username": "other-coach@engage8.app",
                                           "password": "pw12345"}).json()["access_token"]
other_auth = {"Authorization": f"Bearer {other_token}"}
r = c.get("/tendencies", params={"split": "formation", "team_id": team_id}, headers=other_auth)
check("GET /tendencies with team_id owned by a different user -> 404",
      r.status_code == 404, r.status_code)

# 8g. vocab endpoints require auth
r = c.get(f"/teams/{team_id}/vocab")
check("GET /teams/{id}/vocab without token -> 401", r.status_code == 401, r.status_code)

# 9. signup no longer accepts a client-set role (fix #2): role is ignored
r = c.post("/auth/signup", json={"email": "sneaky@x.com", "password": "pw12345",
                                 "role": "admin"})
check("POST /auth/signup ignores role", r.status_code in (200, 201)
      and r.json()["role"] == "coach", r.json().get("role"))

print(f"\n{ok} checks passed.")
