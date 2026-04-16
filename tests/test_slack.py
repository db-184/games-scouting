from unittest.mock import patch, MagicMock

from src.report.slack import compose_headline, post_headline


def test_compose_headline_contains_totals_and_link():
    msg = compose_headline(
        report_date="2026-04-20",
        totals={"sustained": 8, "fast": 6, "new": 11, "cross_platform": 2},
        highlight={
            "title": "MergeFarm Tycoon",
            "signal_label": "Sustained Climber",
            "detail": "sustained climb across IN+BR, 4.6★, solo-dev studio with one prior hit",
        },
        full_report_url="https://user.github.io/games-scouting/2026-04-20/",
        archive_url="https://user.github.io/games-scouting/",
    )
    assert "8 Sustained Climbers" in msg
    assert "11 New Entrants" in msg
    assert "MergeFarm Tycoon" in msg
    assert "https://user.github.io/games-scouting/2026-04-20/" in msg


def test_compose_headline_no_highlight_when_empty():
    msg = compose_headline(
        report_date="2026-04-20",
        totals={"sustained": 0, "fast": 0, "new": 0, "cross_platform": 0},
        highlight=None,
        full_report_url="https://example.com/",
        archive_url="https://example.com/archive/",
    )
    assert "Highlight" not in msg
    assert "0 Sustained" in msg


def test_post_headline_sends_to_webhook():
    mock_resp = MagicMock(status_code=200, text="ok")
    with patch("src.report.slack.requests.post", return_value=mock_resp) as mp:
        post_headline("https://hooks.slack.com/services/FAKE", "hello")
    assert mp.call_count == 1
    _, kwargs = mp.call_args
    assert kwargs["json"] == {"text": "hello"}
