from src.genre_filter import classify_bucket

GENRES_CFG = {
    "play_store": {
        "GAME_PUZZLE": "match3",
        "GAME_CASUAL": "hypercasual",
        "GAME_SIMULATION": "casual_sim",
    },
    "app_store": {
        "Puzzle": "match3",
        "Casual": "hypercasual",
        "Simulation": "casual_sim",
    },
    "keyword_overrides": {
        "hybrid_casual": ["merge", "idle", "tycoon"],
        "match3": ["match-3", "match 3"],
    },
}


def test_classify_bucket_uses_store_genre():
    assert classify_bucket(
        platform="play",
        genre_raw="GAME_PUZZLE",
        title="Block Puzzle Duel",
        description="",
        genres_cfg=GENRES_CFG,
    ) == "match3"


def test_classify_bucket_falls_back_to_keyword_override():
    # genre GAME_CASUAL would map to hypercasual, but "merge" keyword upgrades to hybrid_casual
    assert classify_bucket(
        platform="play",
        genre_raw="GAME_CASUAL",
        title="MergeFarm Tycoon",
        description="Merge cute animals and expand your farm.",
        genres_cfg=GENRES_CFG,
    ) == "hybrid_casual"


def test_classify_bucket_returns_none_for_unmapped_genre():
    assert classify_bucket(
        platform="play",
        genre_raw="GAME_RACING",
        title="Speed Kings",
        description="",
        genres_cfg=GENRES_CFG,
    ) is None


def test_classify_bucket_returns_none_when_no_genre_and_no_keywords():
    assert classify_bucket(
        platform="play",
        genre_raw=None,
        title="Mystery Game",
        description="A mystery awaits.",
        genres_cfg=GENRES_CFG,
    ) is None


def test_classify_bucket_app_store_genre():
    assert classify_bucket(
        platform="ios",
        genre_raw="Puzzle",
        title="Candy Match Saga",
        description="",
        genres_cfg=GENRES_CFG,
    ) == "match3"
