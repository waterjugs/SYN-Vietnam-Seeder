from seeder import crcon

# Trimmed from the live Syndicate endpoint, 2026-10-24.
PAYLOAD = {
    "result": {
        "name": {
            "name": "Syndicate | Competitive Server | Discord.gg/syn-hll | Radical Gaming Network",
            "short_name": "Syn Nam",
        },
        "player_count": 11,
        "max_player_count": 100,
        "player_count_by_team": {"allied": 6, "axis": 5},
        "time_remaining": 2327.0,
        "match_time": 5400,
    },
    "failed": False,
}


def test_parse_live_shape():
    status = crcon.parse(PAYLOAD)
    assert status.player_count == 11
    assert (status.allied, status.axis) == (6, 5)
    assert status.time_remaining == 2327.0
    assert status.name.startswith("Syndicate | Competitive Server")


def test_weaker_side():
    assert crcon.parse(PAYLOAD).weaker_side() == "axis"
    tied = crcon.ServerStatus("x", 10, 5, 5, 0)
    assert tied.weaker_side() == "allies"


def test_fetch_returns_none_when_unreachable():
    assert crcon.fetch("http://127.0.0.1:9/nothing", timeout=1) is None
