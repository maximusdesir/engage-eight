"""CSV uploads: charting files and real-shaped Hudl exports."""
from conftest import FIXTURES

CHART_CSV = ("offense_team,down,ydstogo,yardline_100,play_type,result_yards\n"
             "CENTRAL,1,10,75,run,5\nCENTRAL,3,8,40,pass,12\n")
HUDL_EXPORT = (FIXTURES / "hudl_standard_export.csv").read_bytes()
HUDL_NO_PLAY_TYPE = (FIXTURES / "hudl_no_play_type.csv").read_bytes()


def test_upload_needs_login(client, team):
    r = client.post(f"/teams/{team}/uploads", files={"file": ("chart.csv", CHART_CSV, "text/csv")})
    assert r.status_code == 401


def test_charting_csv(coach, team, upload):
    r = upload(coach, team, CHART_CSV)
    assert r.status_code == 201 and r.json()["inserted"] == 2


def test_same_file_twice_is_409(coach, team, upload):
    assert upload(coach, team, CHART_CSV).status_code == 201
    assert upload(coach, team, CHART_CSV, filename="again.csv").status_code == 409


def test_another_team_can_upload_the_same_file(coach, other_coach, team, new_team, upload):
    assert upload(coach, team, CHART_CSV).status_code == 201
    assert upload(other_coach, new_team(other_coach), CHART_CSV).status_code == 201


def test_hudl_export_with_blank_quarters(coach, team, opponent, upload):
    # BOM, blank QTR cells, kicks and an extra point.
    r = upload(coach, team, HUDL_EXPORT, filename="export.csv",
               source="auto", team="LINCOLN", opponent_id=opponent)
    body = r.json()
    assert r.status_code == 201, r.text
    assert body["source"] == "hudl" and body["inserted"] == 9 and body["teams"] == ["LINCOLN"]
    assert body["skipped"].get("unknown_run_pass") == 1


def test_hudl_export_without_play_type(coach, team, upload):
    r = upload(coach, team, HUDL_NO_PLAY_TYPE, filename="noplaytype.csv", team="NORTH")
    body = r.json()
    assert r.status_code == 201 and body["inserted"] == 4
    assert body["unresolved_play_names"] == ["Black 23", "RPO Glance"]
    assert body["unmapped_formations"] == ["Pistol Trey"]


def test_quarter_split_shows_unknown_quarters(client, coach, team, upload):
    upload(coach, team, HUDL_EXPORT, filename="export.csv", team="LINCOLN")
    r = client.get(f"/teams/{team}/tendencies", params={"team": "LINCOLN", "split": "quarter"},
                   headers=coach.headers)
    assert r.status_code == 200 and "(unknown)" in {x["bucket"] for x in r.json()["rows"]}


def test_tendencies_by_opponent(client, coach, team, opponent, upload):
    upload(coach, team, HUDL_EXPORT, filename="export.csv", team="LINCOLN", opponent_id=opponent)
    upload(coach, team, CHART_CSV)  # no opponent: must not be counted
    r = client.get(f"/teams/{team}/tendencies", params={"opponent_id": opponent},
                   headers=coach.headers)
    assert r.status_code == 200 and sum(x["plays"] for x in r.json()["rows"]) == 9


def test_list_uploads(client, coach, team, upload):
    upload(coach, team, CHART_CSV)
    upload(coach, team, HUDL_EXPORT, filename="export.csv", team="LINCOLN")
    r = client.get(f"/teams/{team}/uploads", headers=coach.headers)
    assert r.status_code == 200 and len(r.json()) == 2


def test_deleting_an_upload_removes_its_plays(client, coach, team, upload):
    upload(coach, team, HUDL_EXPORT, filename="export.csv", team="LINCOLN")
    chart = upload(coach, team, CHART_CSV).json()["upload_id"]

    def count():
        return len(client.get(f"/teams/{team}/plays", headers=coach.headers,
                              params={"limit": 1000}).json())

    before = count()
    r = client.delete(f"/teams/{team}/uploads/{chart}", headers=coach.headers)
    assert r.status_code == 204 and count() == before - 2
