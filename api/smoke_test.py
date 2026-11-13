"""End-to-end smoke test for the Engage Eight API (FastAPI TestClient).

    cd api && python smoke_test.py
"""
import os
import tempfile
from pathlib import Path

# Throwaway DB, dev mode (placeholder JWT secret allowed). Set before importing
# the app, which reads settings at import time.
os.environ["ENGAGE8_DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='.db')}"
os.environ["ENGAGE8_DEBUG"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

from app.core import ratelimit  # noqa: E402
from app.db.session import init_db  # noqa: E402
from app.main import app  # noqa: E402

FIXTURES = Path(__file__).resolve().parent.parent / "ml" / "tests" / "fixtures"
PW = "correct-horse-1"

init_db()  # alembic upgrade head (lifespan only fires under a context manager)
ratelimit.reset()
c = TestClient(app)
ok = 0


def check(label, cond, extra=""):
    global ok
    mark = "PASS" if cond else "FAIL"
    if cond:
        ok += 1
    print(f"  [{mark}] {label} {extra}")
    assert cond, label


def login(email):
    r = c.post("/auth/login", data={"username": email, "password": PW})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# 1. health
r = c.get("/health")
check("GET /health", r.status_code == 200, r.json())

# 2. auth: password minimum, signup, login, me
r = c.post("/auth/signup", json={"email": "weak@engage8.app", "password": "x"})
check("signup with a 1-char password -> 422", r.status_code == 422, r.status_code)

r = c.post("/auth/signup", json={"email": "coach@engage8.app", "password": PW})
check("POST /auth/signup", r.status_code == 201, r.status_code)
auth = login("coach@engage8.app")
r = c.get("/auth/me", headers=auth)
check("GET /auth/me", r.status_code == 200 and r.json()["email"] == "coach@engage8.app")

r = c.post("/auth/signup", json={"email": "sneaky@x.com", "password": PW, "role": "admin"})
check("signup ignores a client-set role", r.status_code == 201 and r.json()["role"] == "coach")

# 3. teams + opponents
r = c.post("/teams", json={"name": "My HS", "level": "hs", "season": 2026}, headers=auth)
check("POST /teams", r.status_code == 201, r.status_code)
team_id = r.json()["id"]
r = c.get("/teams", headers=auth)
check("GET /teams", r.status_code == 200 and len(r.json()) == 1)
r = c.post(f"/teams/{team_id}/opponents", json={"name": "Central", "oc_name": "Smith"},
           headers=auth)
check("POST /teams/{id}/opponents", r.status_code == 201, r.status_code)
opponent_id = r.json()["id"]
r = c.get("/teams")
check("GET /teams without token -> 401", r.status_code == 401, r.status_code)

# 4. predict / recommend (committed model)
r = c.post("/predict", json={"down": 3, "distance": 8, "yardline_100": 45})
check("POST /predict without token -> 401", r.status_code == 401, r.status_code)
r = c.post("/predict", json={"down": 3, "distance": 8, "yardline_100": 45, "quarter": 4},
           headers=auth)
check("POST /predict", r.status_code == 200, r.text[:200])
body = r.json()
check("predict lean is RUN|PASS and model prob is reported",
      body["lean"] in ("RUN", "PASS") and body["model_pass_prob"] == body["pass_prob"]
      and body["blend"] == [])
gun = c.post("/predict", headers=auth, json={"down": 1, "distance": 10, "yardline_100": 75,
                                            "shotgun": True}).json()["pass_prob"]
uc = c.post("/predict", headers=auth, json={"down": 1, "distance": 10, "yardline_100": 75,
                                           "shotgun": False}).json()["pass_prob"]
check("shotgun moves the prediction", gun > uc + 0.1, f"gun {gun} vs under center {uc}")

r = c.post("/recommend", json={"down": 3, "distance": 1, "yardline_100": 3}, headers=auth)
check("POST /recommend", r.status_code == 200, r.status_code)
recs = r.json()["recommendations"]
check("recommendations carry no invented scores",
      recs and all("confidence" not in x and "expected_epa_prevented" not in x for x in recs)
      and "Rules-based" in r.json()["basis"])

# 5. plays, scoped to a team
for pt, dn, dist in [("run", 1, 10), ("pass", 3, 8), ("run", 2, 2), ("pass", 3, 9)]:
    r = c.post(f"/teams/{team_id}/plays", headers=auth, json={
        "offense_team": "CENTRAL", "down": dn, "ydstogo": dist, "yardline_100": 50,
        "play_type": pt, "quarter": 1})
check("POST /teams/{id}/plays", r.status_code == 201, r.text[:200])
manual_play_id = r.json()["id"]
r = c.get(f"/teams/{team_id}/plays", headers=auth, params={"offense_team": "CENTRAL"})
check("GET /teams/{id}/plays", r.status_code == 200 and len(r.json()) == 4, len(r.json()))

r = c.get(f"/teams/{team_id}/tendencies", params={"team": "CENTRAL"}, headers=auth)
check("GET /teams/{id}/tendencies", r.status_code == 200 and len(r.json()["rows"]) >= 1)
r = c.get(f"/teams/{team_id}/tendencies", params={"split": "not_a_split"}, headers=auth)
check("tendencies bad split -> 400", r.status_code == 400, r.status_code)
r = c.get(f"/teams/{team_id}/tendencies")
check("tendencies without token -> 401", r.status_code == 401, r.status_code)

# 6. isolation: a second account sees none of the first account's data
c.post("/auth/signup", json={"email": "other-coach@engage8.app", "password": PW})
other = login("other-coach@engage8.app")
other_team = c.post("/teams", json={"name": "Other HS"}, headers=other).json()["id"]
for path in ("plays", "tendencies", "uploads", "vocab"):
    r = c.get(f"/teams/{team_id}/{path}", headers=other)
    check(f"other user GET /teams/{{A}}/{path} -> 404", r.status_code == 404, r.status_code)
r = c.get(f"/teams/{other_team}/plays", headers=other, params={"offense_team": "CENTRAL"})
check("same label in another team returns only that team's plays",
      r.status_code == 200 and r.json() == [], r.text[:100])
r = c.delete(f"/teams/{team_id}/plays/{manual_play_id}", headers=other)
check("other user can't delete A's play", r.status_code == 404, r.status_code)
r = c.post("/predict", headers=other, json={"down": 3, "distance": 8, "yardline_100": 45,
                                           "team_id": team_id, "offense_team": "CENTRAL"})
check("other user can't blend with A's plays", r.status_code == 404, r.status_code)

# 7. uploads
csv = ("offense_team,down,ydstogo,yardline_100,play_type,result_yards\n"
       "CENTRAL,1,10,75,run,5\nCENTRAL,3,8,40,pass,12\n")
r = c.post(f"/teams/{team_id}/uploads", files={"file": ("chart.csv", csv, "text/csv")})
check("upload without token -> 401", r.status_code == 401, r.status_code)
r = c.post(f"/teams/{team_id}/uploads", files={"file": ("chart.csv", csv, "text/csv")},
           headers=auth)
check("upload charting CSV", r.status_code == 201 and r.json()["inserted"] == 2, r.text[:200])
chart_upload = r.json()["upload_id"]
r = c.post(f"/teams/{team_id}/uploads", files={"file": ("again.csv", csv, "text/csv")},
           headers=auth)
check("re-uploading the same file -> 409", r.status_code == 409, r.status_code)
r = c.post(f"/teams/{other_team}/uploads", files={"file": ("chart.csv", csv, "text/csv")},
           headers=other)
check("another team can upload the same file", r.status_code == 201, r.status_code)

# Real-shaped Hudl export: BOM, blank QTR cells, kicks and an extra point.
r = c.post(f"/teams/{team_id}/uploads", headers=auth,
           data={"source": "auto", "team": "LINCOLN", "opponent_id": str(opponent_id)},
           files={"file": ("export.csv", (FIXTURES / "hudl_standard_export.csv").read_bytes(),
                           "text/csv")})
body = r.json()
check("Hudl export with blank QTR imports (auto-detected)",
      r.status_code == 201 and body["source"] == "hudl" and body["inserted"] == 9
      and body["teams"] == ["LINCOLN"], r.text[:300])
check("skipped rows are reported", body.get("skipped", {}).get("unknown_run_pass") == 1,
      body.get("skipped"))

r = c.post(f"/teams/{team_id}/uploads", headers=auth, data={"team": "NORTH"},
           files={"file": ("noplaytype.csv", (FIXTURES / "hudl_no_play_type.csv").read_bytes(),
                           "text/csv")})
body = r.json()
check("Hudl export without PLAY TYPE reports unresolved names",
      r.status_code == 201 and body["inserted"] == 4
      and body["unresolved_play_names"] == ["Black 23", "RPO Glance"], r.text[:300])
check("upload surfaces unmapped formations",
      body["unmapped_formations"] == ["Pistol Trey"], body["unmapped_formations"])

r = c.get(f"/teams/{team_id}/tendencies", params={"team": "LINCOLN", "split": "quarter"},
          headers=auth)
check("quarter split shows unknown quarters",
      r.status_code == 200 and "(unknown)" in {x["bucket"] for x in r.json()["rows"]},
      [x["bucket"] for x in r.json()["rows"]])
r = c.get(f"/teams/{team_id}/tendencies", params={"opponent_id": opponent_id}, headers=auth)
check("tendencies by opponent_id", r.status_code == 200
      and sum(x["plays"] for x in r.json()["rows"]) == 9, r.text[:200])

r = c.get(f"/teams/{team_id}/uploads", headers=auth)
check("GET /teams/{id}/uploads", r.status_code == 200 and len(r.json()) == 3, len(r.json()))
before = len(c.get(f"/teams/{team_id}/plays", headers=auth, params={"limit": 1000}).json())
r = c.delete(f"/teams/{team_id}/uploads/{chart_upload}", headers=auth)
after = len(c.get(f"/teams/{team_id}/plays", headers=auth, params={"limit": 1000}).json())
check("DELETE upload removes its plays", r.status_code == 204 and after == before - 2,
      f"{before} -> {after}")
r = c.delete(f"/teams/{team_id}/plays/{manual_play_id}", headers=auth)
check("DELETE /teams/{id}/plays/{play_id}", r.status_code == 204, r.status_code)

# 8. vocab: options + unmapped, map one, confirm it clears and applies
r = c.get(f"/teams/{team_id}/vocab", params={"team": "NORTH"}, headers=auth)
check("GET /teams/{id}/vocab", r.status_code == 200
      and "TRIPS" in r.json()["canonical"]["formations"]
      and "Pistol Trey" in r.json()["unmapped"]["formations"], r.text[:200])
r = c.post(f"/teams/{team_id}/vocab", headers=auth, json=[
    {"kind": "formation", "raw_value": "Pistol Trey", "canonical_value": "TREY"}])
check("POST /teams/{id}/vocab", r.status_code == 200
      and r.json()[0]["canonical_value"] == "TREY", r.text[:200])
r = c.get(f"/teams/{team_id}/vocab", params={"team": "NORTH"}, headers=auth)
check("mapping clears the unmapped value",
      "Pistol Trey" not in r.json()["unmapped"]["formations"])
r = c.get(f"/teams/{team_id}/tendencies", params={"team": "NORTH", "split": "formation"},
          headers=auth)
check("formation split uses the team mapping",
      "TREY" in {x["bucket"] for x in r.json()["rows"]}, r.text[:200])
r = c.get(f"/teams/{team_id}/vocab")
check("vocab without token -> 401", r.status_code == 401, r.status_code)

# 9. opponent blend: an opponent that runs on 3rd & long pulls the lean to run
rows = ["offense_team,quarter,down,ydstogo,yardline_100,play_type,formation,shotgun"]
rows += ["RUNNERS,2,3,9,50,run,Pro,0"] * 30 + ["RUNNERS,2,3,8,45,pass,Pro,0"] * 2
rows += ["RUNNERS,1,1,10,70,run,I,0"] * 8 + ["RUNNERS,2,1,10,60,pass,I,0"] * 8
r = c.post(f"/teams/{team_id}/uploads", headers=auth,
           files={"file": ("runners.csv", "\n".join(rows) + "\n", "text/csv")})
check("upload opponent plays for the blend", r.status_code == 201, r.text[:200])
r = c.post("/predict", headers=auth, json={
    "down": 3, "distance": 8, "yardline_100": 45, "shotgun": False,
    "team_id": team_id, "offense_team": "RUNNERS", "formation": "Pro"})
body = r.json()
check("blend pulls the prediction toward the opponent's tendency",
      r.status_code == 200 and len(body["blend"]) == 2  # Pro level adds no new plays
      and body["pass_prob"] < body["model_pass_prob"] - 0.2,
      f"model {body.get('model_pass_prob')} -> blended {body.get('pass_prob')}, "
      f"{[s['label'] for s in body.get('blend', [])]}")

# 10. demo accounts: one click, own data, no password, purged after 24 h
from datetime import datetime, timedelta  # noqa: E402

from sqlalchemy import func, select  # noqa: E402

from app.db.models import Play, Team, User  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services.demo import purge_demo_users  # noqa: E402

r1, r2 = c.post("/auth/demo"), c.post("/auth/demo")
check("POST /auth/demo (twice, no credentials)",
      r1.status_code == 201 and r2.status_code == 201, (r1.status_code, r2.status_code))
d1, d2 = r1.json(), r2.json()
h1 = {"Authorization": f"Bearer {d1['access_token']}"}
h2 = {"Authorization": f"Bearer {d2['access_token']}"}
check("each demo gets its own team and opponent",
      d1["team_id"] != d2["team_id"] and d1["opponent_id"] != d2["opponent_id"])
me = c.get("/auth/me", headers=h1).json()
check("demo user is flagged is_demo; normal users are not",
      me["is_demo"] is True and c.get("/auth/me", headers=auth).json()["is_demo"] is False, me)
r = c.post("/auth/login", data={"username": me["email"], "password": PW})
check("demo account has no usable password", r.status_code == 401, r.status_code)
r = c.get(f"/teams/{d1['team_id']}/tendencies", params={"opponent_id": d1["opponent_id"],
                                                         "split": "formation"}, headers=h1)
rows = r.json()["rows"] if r.status_code == 200 else []
buckets = {x["bucket"]: x for x in rows}
check("demo opponent film is loaded: I-Form runs, Empty passes",
      r.status_code == 200 and "I-FORM" in buckets and "EMPTY" in buckets
      and buckets["I-FORM"]["run_pct"] > 50 > buckets["EMPTY"]["run_pct"], list(buckets))
r = c.get(f"/teams/{d1['team_id']}/uploads", headers=h1)
check("demo film is a normal upload", r.status_code == 200 and len(r.json()) == 1
      and r.json()[0]["n_plays"] > 200, r.text[:200])
# Cross-account isolation: another demo and a regular coach see 404.
for who, hdr in (("another demo", h2), ("a regular coach", auth)):
    for path in ("", "/tendencies", "/uploads", "/plays"):
        r = c.get(f"/teams/{d1['team_id']}{path}", headers=hdr)
        check(f"{who} on demo team{path or ' '} -> 404", r.status_code == 404, r.status_code)
r = c.get(f"/teams/{team_id}", headers=h1)
check("demo user on a regular team -> 404", r.status_code == 404, r.status_code)

with SessionLocal() as db:
    check("purge keeps fresh demo users", purge_demo_users(db) == 0)
    d1_user_id = db.scalar(select(User.id).where(User.email == me["email"]))
    purged = purge_demo_users(db, now=datetime.utcnow() + timedelta(hours=25))
    left = db.scalar(select(func.count()).select_from(Play).where(
        Play.team_id.in_([d1["team_id"], d2["team_id"]])))
    check("purge deletes old demo users and their data",
          purged >= 2 and left == 0
          and db.get(User, d1_user_id) is None and db.get(Team, d1["team_id"]) is None,
          f"purged {purged}, plays left {left}")
    check("purge never touches regular users",
          db.scalar(select(User.id).where(User.email == "coach@engage8.app")) is not None)
r = c.get("/auth/me", headers=h1)
check("a purged demo token stops working", r.status_code == 401, r.status_code)
r = c.get("/auth/me", headers=auth)
check("regular coach still signed in after purge", r.status_code == 200, r.status_code)

codes = [c.post("/auth/demo").status_code for _ in range(10)]
check("demo creation is rate limited", 429 in codes, codes)

# 11. rate limiting on login (last: it uses up this client's login budget)
codes = [c.post("/auth/login", data={"username": "coach@engage8.app", "password": "wrong"}
                ).status_code for _ in range(12)]
check("login is rate limited", 429 in codes, codes)

print(f"\n{ok} checks passed.")
