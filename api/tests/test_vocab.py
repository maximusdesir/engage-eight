"""Formation/motion vocabulary: unmapped values, mapping them, and using the map."""
import pytest

from conftest import FIXTURES


@pytest.fixture
def north(coach, team, upload):
    """NORTH's Hudl export, which has an unmapped "Pistol Trey" formation."""
    r = upload(coach, team, (FIXTURES / "hudl_no_play_type.csv").read_bytes(),
               filename="noplaytype.csv", team="NORTH")
    assert r.status_code == 201, r.text
    return team


def _vocab(client, coach, team):
    return client.get(f"/teams/{team}/vocab", params={"team": "NORTH"}, headers=coach.headers)


def test_vocab_lists_options_and_unmapped(client, coach, north):
    r = _vocab(client, coach, north)
    assert r.status_code == 200
    assert "TRIPS" in r.json()["canonical"]["formations"]
    assert "Pistol Trey" in r.json()["unmapped"]["formations"]


def test_mapping_clears_unmapped_and_applies_to_tendencies(client, coach, north):
    r = client.post(f"/teams/{north}/vocab", headers=coach.headers, json=[
        {"kind": "formation", "raw_value": "Pistol Trey", "canonical_value": "TREY"}])
    assert r.status_code == 200 and r.json()[0]["canonical_value"] == "TREY"

    assert "Pistol Trey" not in _vocab(client, coach, north).json()["unmapped"]["formations"]
    r = client.get(f"/teams/{north}/tendencies", params={"team": "NORTH", "split": "formation"},
                   headers=coach.headers)
    assert "TREY" in {x["bucket"] for x in r.json()["rows"]}


def test_vocab_needs_login(client, team):
    assert client.get(f"/teams/{team}/vocab").status_code == 401
