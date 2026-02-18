from collections.abc import Generator
from pathlib import Path

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
