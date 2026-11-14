"""Predict and recommend with the committed model, and the opponent blend."""
SITUATION = {"down": 3, "distance": 8, "yardline_100": 45}


def test_predict_needs_login(client):
    assert client.post("/predict", json=SITUATION).status_code == 401


def test_predict_without_an_opponent(client, coach):
    r = client.post("/predict", json={**SITUATION, "quarter": 4}, headers=coach.headers)
    body = r.json()
    assert r.status_code == 200, r.text
    assert body["lean"] in ("RUN", "PASS")
    assert body["model_pass_prob"] == body["pass_prob"] and body["blend"] == []


def test_shotgun_moves_the_prediction(client, coach):
    def pass_prob(shotgun):
        return client.post("/predict", headers=coach.headers, json={
            "down": 1, "distance": 10, "yardline_100": 75, "shotgun": shotgun}).json()["pass_prob"]
    assert pass_prob(True) > pass_prob(False) + 0.1


def test_recommend_is_rules_based_with_no_invented_scores(client, coach):
    r = client.post("/recommend", json={"down": 3, "distance": 1, "yardline_100": 3},
                    headers=coach.headers)
    assert r.status_code == 200
    recs = r.json()["recommendations"]
    assert recs and "Rules-based" in r.json()["basis"]
    assert all("confidence" not in x and "expected_epa_prevented" not in x for x in recs)


def test_blend_pulls_toward_the_opponents_tendency(client, coach, team, upload):
    # RUNNERS runs on 3rd & long out of Pro, which the league model calls a pass.
    rows = ["offense_team,quarter,down,ydstogo,yardline_100,play_type,formation,shotgun"]
    rows += ["RUNNERS,2,3,9,50,run,Pro,0"] * 30 + ["RUNNERS,2,3,8,45,pass,Pro,0"] * 2
    rows += ["RUNNERS,1,1,10,70,run,I,0"] * 8 + ["RUNNERS,2,1,10,60,pass,I,0"] * 8
    assert upload(coach, team, "\n".join(rows) + "\n", filename="runners.csv").status_code == 201

    r = client.post("/predict", headers=coach.headers, json={
        **SITUATION, "shotgun": False, "team_id": team, "offense_team": "RUNNERS",
        "formation": "Pro"})
    body = r.json()
    assert r.status_code == 200, r.text
    # All plays, then 3rd & long. Pro adds no new plays, so it isn't counted twice.
    assert [s["plays"] for s in body["blend"]] == [48, 32]
    assert body["pass_prob"] < body["model_pass_prob"] - 0.2
