from src.signals.cross_platform import match_cross_platform

CANDIDATES = [
    {"app_id": "com.sunflower.mergefarm", "platform": "play", "title": "MergeFarm Tycoon", "developer": "Sunflower Studios"},
    {"app_id": "1111",                    "platform": "ios",  "title": "MergeFarm Tycoon", "developer": "Sunflower Studios"},
    {"app_id": "com.other.game",          "platform": "play", "title": "Other Game",       "developer": "Other Studio"},
]


def test_fuzzy_match_on_title_and_developer():
    pairs = match_cross_platform(CANDIDATES)
    assert len(pairs) == 1
    play_id, ios_id = pairs[0]
    assert play_id == "com.sunflower.mergefarm"
    assert ios_id == "1111"


def test_title_mismatch_does_not_match():
    candidates = [
        {"app_id": "com.a", "platform": "play", "title": "Alpha",    "developer": "X"},
        {"app_id": "999",   "platform": "ios",  "title": "Omega",    "developer": "X"},
    ]
    assert match_cross_platform(candidates) == []


def test_developer_mismatch_does_not_match():
    candidates = [
        {"app_id": "com.a", "platform": "play", "title": "Candy Crush", "developer": "X"},
        {"app_id": "999",   "platform": "ios",  "title": "Candy Crush", "developer": "Y"},
    ]
    assert match_cross_platform(candidates) == []
