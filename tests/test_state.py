from collections.abc import Generator
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from state import DAY_KEYS, Database, normalize_game_name


@pytest.fixture
def db(tmp_path: Path) -> Generator[Database, None, None]:
    d = Database(tmp_path / "test.db")
    yield d
    d.close()


def test_normalize_game_name_whitespace_and_case() -> None:
    raw = " HelL DiverS  2  "
    normalized = normalize_game_name(raw)
    assert normalized == "helldivers2"


def test_add_game_merges_duplicates(db: Database) -> None:
    db.add_game(123, "Helldivers 2")
    db.add_game(123, "  helL DiverS  2   ")

    games = db.list_games(123)
    assert len(games) == 1
    assert games[0] == "  helL DiverS  2   "


def test_remove_game_removes_matching_game(db: Database) -> None:
    db.add_game(123, "Helldivers 2")
    db.add_game(123, "Balatro")

    removed = db.remove_game(123, "  helL DiverS  2   ")
    assert removed is True

    games = db.list_games(123)
    assert games == ["Balatro"]


def test_remove_game_returns_false_for_missing(db: Database) -> None:
    assert db.remove_game(123, "Nope") is False


def test_list_games_returns_user_games(db: Database) -> None:
    db.add_game(123, "Helldivers 2")
    db.add_game(123, "Balatro")

    assert db.list_games(123) == ["Helldivers 2", "Balatro"]
    assert db.list_games(999) == []


def test_get_common_games(db: Database) -> None:
    db.add_game(123, "Helldivers 2")
    db.add_game(123, "Balatro")
    db.add_game(999, "  helL DiverS  2   ")

    games = db.get_common_games(123, 999)
    assert games == ["Helldivers 2"]


def test_set_and_get_timezone(db: Database) -> None:
    db.set_timezone(123, "America/Los_Angeles")

    assert db.get_timezone(123) == "America/Los_Angeles"
    assert db.get_timezone(999) is None


def test_set_day_availability_creates_slot(db: Database) -> None:
    db.add_day_availability(123, "mon", "18:00", "22:00")

    availability = db.get_availability(123)
    for day in DAY_KEYS:
        assert day in availability

    assert availability["mon"] == [{"start": "18:00", "end": "22:00"}]
    for day in DAY_KEYS:
        if day != "mon":
            assert availability[day] == []


def test_set_day_availability_multiple_slots(db: Database) -> None:
    db.add_day_availability(123, "fri", "12:00", "14:00")
    db.add_day_availability(123, "fri", "20:00", "23:00")

    availability = db.get_availability(123)
    assert availability["fri"] == [
        {"start": "12:00", "end": "14:00"},
        {"start": "20:00", "end": "23:00"},
    ]


def test_set_day_availability_clears(db: Database) -> None:
    db.add_day_availability(123, "wed", "18:00", "22:00")
    db.clear_day_availability(123, "wed")

    availability = db.get_availability(123)
    assert availability["wed"] == []


def test_get_availability_empty_for_missing_user(db: Database) -> None:
    availability = db.get_availability(123)

    for day in DAY_KEYS:
        assert day in availability
        assert availability[day] == []


def test_get_users_for_game(db: Database) -> None:
    db.add_game(123, "Helldivers 2")
    db.add_game(456, "  helL DiverS  2   ")
    db.add_game(789, "Balatro")

    users = db.get_users_for_game("Helldivers 2")
    assert set(users) == {123, 456}


def test_get_users_for_game_no_matches(db: Database) -> None:
    assert db.get_users_for_game("Nope") == []


def test_next_available_returns_active_slot_with_is_now(db: Database) -> None:
    db.set_timezone(123, "US/Eastern")
    db.add_day_availability(123, "thu", "18:00", "22:00")

    # Thursday 20:00 Eastern = slot still active
    now_utc = datetime(2026, 2, 20, 1, 0, tzinfo=ZoneInfo("UTC"))  # 01:00 UTC Fri = 20:00 ET Thu
    result = db.next_available(123, now_utc)
    assert result == ("thu", "18:00", "22:00", True)


def test_next_available_returns_future_slot_with_is_now_false(db: Database) -> None:
    db.set_timezone(123, "US/Eastern")
    db.add_day_availability(123, "thu", "18:00", "22:00")

    # Thursday 15:00 Eastern = slot hasn't started yet
    now_utc = datetime(2026, 2, 19, 20, 0, tzinfo=ZoneInfo("UTC"))  # 20:00 UTC Thu = 15:00 ET Thu
    result = db.next_available(123, now_utc)
    assert result == ("thu", "18:00", "22:00", False)


def test_next_available_skips_ended_slot(db: Database) -> None:
    db.set_timezone(123, "US/Eastern")
    db.add_day_availability(123, "thu", "10:00", "12:00")
    db.add_day_availability(123, "fri", "18:00", "22:00")

    # Thursday 15:00 Eastern — thu slot already ended
    now_utc = datetime(2026, 2, 19, 20, 0, tzinfo=ZoneInfo("UTC"))
    result = db.next_available(123, now_utc)
    assert result == ("fri", "18:00", "22:00", False)


def test_next_available_no_timezone(db: Database) -> None:
    db.add_day_availability(123, "mon", "18:00", "22:00")
    assert db.next_available(123, datetime.now(ZoneInfo("UTC"))) is None


def test_next_available_no_slots(db: Database) -> None:
    db.set_timezone(123, "US/Eastern")
    assert db.next_available(123, datetime.now(ZoneInfo("UTC"))) is None


def test_validate_time_valid() -> None:
    from state import validate_time
    assert validate_time("00:00") is True
    assert validate_time("23:59") is True
    assert validate_time("18:00") is True


def test_validate_time_invalid() -> None:
    from state import validate_time
    assert validate_time("25:00") is False
    assert validate_time("abc") is False
    assert validate_time("1800") is False


def test_add_day_availability_merges_overlapping_slots(db: Database) -> None:
    db.add_day_availability(123, "mon", "10:00", "14:00")
    db.add_day_availability(123, "mon", "13:00", "18:00")

    slots = db.get_availability(123)["mon"]
    assert slots == [{"start": "10:00", "end": "18:00"}]


def test_add_day_availability_merges_adjacent_slots(db: Database) -> None:
    db.add_day_availability(123, "mon", "10:00", "14:00")
    db.add_day_availability(123, "mon", "14:00", "18:00")

    slots = db.get_availability(123)["mon"]
    assert slots == [{"start": "10:00", "end": "18:00"}]


def test_add_day_availability_overnight_splits_at_midnight(db: Database) -> None:
    db.add_day_availability(123, "fri", "22:00", "02:00")

    avail = db.get_availability(123)
    assert avail["fri"] == [{"start": "22:00", "end": "24:00"}]
    assert avail["sat"] == [{"start": "00:00", "end": "02:00"}]


def test_find_ready_players_returns_common_games(db: Database) -> None:
    # User 1: invoker
    db.set_timezone(1, "UTC")
    db.add_game(1, "Helldivers 2")
    db.add_game(1, "Balatro")

    # User 2: available, shares one game
    db.set_timezone(2, "UTC")
    db.add_game(2, "Helldivers 2")
    db.add_day_availability(2, "thu", "10:00", "23:00")

    now_utc = datetime(2026, 2, 19, 15, 0, tzinfo=ZoneInfo("UTC"))  # Thursday 15:00 UTC
    results = db.find_ready_players(1, now_utc)
    assert len(results) == 1
    assert results[0] == (2, ["Helldivers 2"])


def test_find_ready_players_excludes_unavailable(db: Database) -> None:
    db.set_timezone(1, "UTC")
    db.add_game(1, "Helldivers 2")

    db.set_timezone(2, "UTC")
    db.add_game(2, "Helldivers 2")
    db.add_day_availability(2, "thu", "10:00", "12:00")

    # Thursday 15:00 — user 2's slot ended at 12:00
    now_utc = datetime(2026, 2, 19, 15, 0, tzinfo=ZoneInfo("UTC"))
    results = db.find_ready_players(1, now_utc)
    assert results == []


def test_find_ready_players_with_game_filter(db: Database) -> None:
    db.set_timezone(1, "UTC")
    db.add_game(1, "Helldivers 2")
    db.add_game(1, "Balatro")

    db.set_timezone(2, "UTC")
    db.add_game(2, "Helldivers 2")
    db.add_game(2, "Balatro")
    db.add_day_availability(2, "thu", "10:00", "23:00")

    now_utc = datetime(2026, 2, 19, 15, 0, tzinfo=ZoneInfo("UTC"))
    results = db.find_ready_players(1, now_utc, game_filter="Balatro")
    assert len(results) == 1
    assert results[0] == (2, ["Balatro"])


def test_find_ready_players_no_common_games(db: Database) -> None:
    db.set_timezone(1, "UTC")
    db.add_game(1, "Helldivers 2")

    db.set_timezone(2, "UTC")
    db.add_game(2, "Balatro")
    db.add_day_availability(2, "thu", "10:00", "23:00")

    now_utc = datetime(2026, 2, 19, 15, 0, tzinfo=ZoneInfo("UTC"))
    results = db.find_ready_players(1, now_utc)
    assert results == []


def test_user_count(db: Database) -> None:
    assert db.user_count() == 0
    db.set_timezone(1, "UTC")
    db.set_timezone(2, "UTC")
    assert db.user_count() == 2


def test_all_game_names(db: Database) -> None:
    db.add_game(1, "Balatro")
    db.add_game(2, "Helldivers 2")
    db.add_game(3, "Balatro")

    names = db.all_game_names()
    assert names == ["Balatro", "Helldivers 2"]


def test_all_game_names_deduplicates_by_normalized(db: Database) -> None:
    db.add_game(1, "Helldivers 2")
    db.add_game(2, "helldivers 2")

    names = db.all_game_names()
    assert len(names) == 1
