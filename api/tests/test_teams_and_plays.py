"""Teams, opponents, hand-entered plays, and tendencies over them."""
import pytest

CENTRAL_PLAYS = [("run", 1, 10), ("pass", 3, 8), ("run", 2, 2), ("pass", 3, 9)]


@pytest.fixture
def plays(client, coach, team):
    """Four hand-entered CENTRAL plays in the coach's team; returns their ids."""
    ids = []
    for play_type, down, dist in CENTRAL_PLAYS:
        r = client.post(f"/teams/{team}/plays", headers=coach.headers, json={
            "offense_team": "CENTRAL", "down": down, "ydstogo": dist, "yardline_100": 50,
            "play_type": play_type, "quarter": 1})
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    return ids


def test_create_and_list_teams(client, coach, team):
    r = client.get("/teams", headers=coach.headers)
    assert r.status_code == 200 and [t["id"] for t in r.json()] == [team]


def test_create_opponent(opponent):
    assert isinstance(opponent, int)


def test_teams_need_login(client):
    assert client.get("/teams").status_code == 401


def test_list_plays(client, coach, team, plays):
    r = client.get(f"/teams/{team}/plays", headers=coach.headers,
                   params={"offense_team": "CENTRAL"})
    assert r.status_code == 200 and len(r.json()) == len(CENTRAL_PLAYS)


def test_delete_play(client, coach, team, plays):
    r = client.delete(f"/teams/{team}/plays/{plays[0]}", headers=coach.headers)
    assert r.status_code == 204
    left = client.get(f"/teams/{team}/plays", headers=coach.headers).json()
    assert plays[0] not in {p["id"] for p in left}


def test_tendencies(client, coach, team, plays):
    r = client.get(f"/teams/{team}/tendencies", params={"team": "CENTRAL"},
                   headers=coach.headers)
    assert r.status_code == 200 and len(r.json()["rows"]) >= 1


def test_tendencies_bad_split_is_400(client, coach, team):
    r = client.get(f"/teams/{team}/tendencies", params={"split": "not_a_split"},
                   headers=coach.headers)
    assert r.status_code == 400


def test_tendencies_need_login(client, team):
    assert client.get(f"/teams/{team}/tendencies").status_code == 401
