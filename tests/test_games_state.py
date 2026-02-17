import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from state import DAY_KEYS, Database


def _make_db(tmp_path: Path) -> Database:
    return Database(tmp_path / "test.db")


def test_normalize_game_name_whitespace_and_case() -> None:
    from state import normalize_game_name

    raw = " HelL DiverS  2  "
    normalized = normalize_game_name(raw)
    assert normalized == "helldivers2"


def test_add_game_merges_duplicates(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    db.add_game(123, "Helldivers 2")
    db.add_game(123, "  helL DiverS  2   ")

    games = db.list_games(123)
    assert len(games) == 1
    assert games[0] == "  helL DiverS  2   "


def test_remove_game_removes_matching_game(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    db.add_game(123, "Helldivers 2")
    db.add_game(123, "Balatro")

    removed = db.remove_game(123, "  helL DiverS  2   ")
    assert removed is True

    games = db.list_games(123)
    assert games == ["Balatro"]


def test_remove_game_returns_false_for_missing(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    assert db.remove_game(123, "Nope") is False


def test_list_games_returns_user_games(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    db.add_game(123, "Helldivers 2")
    db.add_game(123, "Balatro")

    assert db.list_games(123) == ["Helldivers 2", "Balatro"]
    assert db.list_games(999) == []


def test_get_common_games(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    db.add_game(123, "Helldivers 2")
    db.add_game(123, "Balatro")
    db.add_game(999, "  helL DiverS  2   ")

    games = db.get_common_games(123, 999)
    assert games == ["Helldivers 2"]


def test_set_and_get_timezone(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    db.set_timezone(123, "America/Los_Angeles")

    assert db.get_timezone(123) == "America/Los_Angeles"
    assert db.get_timezone(999) is None


def test_set_day_availability_creates_slot(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    db.add_day_availability(123, "mon", "18:00", "22:00")

    availability = db.get_availability(123)
    for day in DAY_KEYS:
        assert day in availability

    assert availability["mon"] == [{"start": "18:00", "end": "22:00"}]
    for day in DAY_KEYS:
        if day != "mon":
            assert availability[day] == []


def test_set_day_availability_multiple_slots(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    db.add_day_availability(123, "fri", "12:00", "14:00")
    db.add_day_availability(123, "fri", "20:00", "23:00")

    availability = db.get_availability(123)
    assert availability["fri"] == [
        {"start": "12:00", "end": "14:00"},
        {"start": "20:00", "end": "23:00"},
    ]


def test_set_day_availability_clears(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    db.add_day_availability(123, "wed", "18:00", "22:00")
    db.clear_day_availability(123, "wed")

    availability = db.get_availability(123)
    assert availability["wed"] == []


def test_get_availability_empty_for_missing_user(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    availability = db.get_availability(123)

    for day in DAY_KEYS:
        assert day in availability
        assert availability[day] == []


def test_format_availability_missing_user(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    msg = db.format_availability(123)
    lines = msg.splitlines()

    assert lines[0] == "timezone: not set"
    assert len(lines) == 1 + len(DAY_KEYS)

    days = [line.split(":")[0] for line in lines[1:]]
    assert days == DAY_KEYS

    for line in lines[1:]:
        assert line.endswith("none")


def test_format_availability_with_timezone_and_day(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    db.set_timezone(123, "America/Los_Angeles")
    db.add_day_availability(123, "fri", "18:00", "22:00")

    msg = db.format_availability(123)
    lines = msg.splitlines()

    assert lines[0] == "timezone: America/Los_Angeles"

    day_to_text = {line.split(":")[0]: line.split(": ")[1] for line in lines[1:]}

    for day in DAY_KEYS:
        if day == "fri":
            assert day_to_text[day] == "18:00-22:00"
        else:
            assert day_to_text[day] == "none"


def test_format_availability_partial(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    db.add_day_availability(123, "mon", "10:00", "12:00")

    msg = db.format_availability(123)
    lines = msg.splitlines()

    assert lines[0] == "timezone: not set"

    day_to_text = {line.split(":")[0]: line.split(": ")[1] for line in lines[1:]}
    assert day_to_text["mon"] == "10:00-12:00"

    for day in DAY_KEYS:
        if day != "mon":
            assert day_to_text[day] == "none"


def test_format_availability_multiple_slots(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    db.add_day_availability(123, "sat", "10:00", "12:00")
    db.add_day_availability(123, "sat", "20:00", "23:00")

    msg = db.format_availability(123)
    lines = msg.splitlines()
    day_to_text = {line.split(":")[0]: line.split(": ")[1] for line in lines[1:]}
    assert day_to_text["sat"] == "10:00-12:00, 20:00-23:00"
