from src.signals.compose import compose_sections

# Each signal list is already sorted by strength.

FAST = [
    {"app_id": "com.a", "platform": "play", "signal": "fast", "score": 60},
    {"app_id": "com.b", "platform": "play", "signal": "fast", "score": 40},
]

NEW = [
    {"app_id": "com.a", "platform": "play", "signal": "new", "score": 10},  # dup — fast wins
    {"app_id": "com.c", "platform": "play", "signal": "new", "score": 20},
]

SUSTAINED = [
    {"app_id": "com.b", "platform": "play", "signal": "sustained", "score": 30},  # dup — sustained > fast
]


def test_compose_priority_sustained_over_fast_over_new():
    sections = compose_sections(fast=FAST, new=NEW, sustained=SUSTAINED, max_per_section=10)
    # com.b should be in sustained (bumped out of fast)
    assert {x["app_id"] for x in sections["sustained"]} == {"com.b"}
    # com.a stays in fast
    assert {x["app_id"] for x in sections["fast"]} == {"com.a"}
    # com.c stays in new
    assert {x["app_id"] for x in sections["new"]} == {"com.c"}


def test_compose_respects_max_per_section():
    fast = [{"app_id": f"com.{i}", "platform": "play", "signal": "fast", "score": 100 - i} for i in range(20)]
    sections = compose_sections(fast=fast, new=[], sustained=[], max_per_section=10)
    assert len(sections["fast"]) == 10
    # top 10 by score preserved
    assert sections["fast"][0]["app_id"] == "com.0"
    assert sections["fast"][9]["app_id"] == "com.9"
