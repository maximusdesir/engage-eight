"""Another account sees none of a team's data, whatever it tries."""
import pytest


@pytest.fixture
def play(client, coach, team):
    r = client.post(f"/teams/{team}/plays", headers=coach.headers, json={
        "offense_team": "CENTRAL", "down": 3, "ydstogo": 8, "yardline_100": 50,
        "play_type": "pass", "quarter": 1})
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.mark.parametrize("path", ["", "/plays", "/tendencies", "/uploads", "/vocab"])
def test_other_account_gets_404(client, other_coach, team, play, path):
    assert client.get(f"/teams/{team}{path}", headers=other_coach.headers).status_code == 404


def test_same_label_in_another_team_is_separate(client, other_coach, new_team, team, play):
    other_team = new_team(other_coach, "Other HS")
    r = client.get(f"/teams/{other_team}/plays", headers=other_coach.headers,
                   params={"offense_team": "CENTRAL"})
    assert r.status_code == 200 and r.json() == []


def test_other_account_cant_delete_a_play(client, coach, other_coach, team, play):
    r = client.delete(f"/teams/{team}/plays/{play}", headers=other_coach.headers)
    assert r.status_code == 404
    assert play in {p["id"] for p in client.get(f"/teams/{team}/plays",
                                                headers=coach.headers).json()}


def test_other_account_cant_blend_with_a_teams_plays(client, other_coach, team, play):
    r = client.post("/predict", headers=other_coach.headers, json={
        "down": 3, "distance": 8, "yardline_100": 45, "team_id": team, "offense_team": "CENTRAL"})
    assert r.status_code == 404
