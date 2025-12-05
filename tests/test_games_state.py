import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import bot


def test_normalize_game_name_whitespace_and_case() -> None:
    """
    normalize_game_name should:
    - remove all whitespace
    - lowercase the string
    """
    raw = " HelL DiverS  2  "
    normalized = bot.normalize_game_name(raw)
    assert normalized == "helldivers2"


def test_add_game_to_state_merges_duplicates() -> None:
    """
    add_game_to_state should:
    - merge normalized duplicates into a single entry
    - keep the latest provided spelling
    """
    state = {"users": {}}

    bot.add_game_to_state(state, user_id=123, game_name="Helldivers 2")
    bot.add_game_to_state(state, user_id=123, game_name="  helL DiverS  2   ")

    games = state["users"]["123"]["games"]

    assert len(games) == 1
    assert games[0] == "  helL DiverS  2   "


def test_remove_game_from_state_removes_matching_game() -> None:
    """
    remove_game_from_state should:
    - find a game by normalized name
    - remove it
    - leave other games untouched
    """
    state = {"users": {}}

    # Start with two games for the same user
    bot.add_game_to_state(state, user_id=123, game_name="Helldivers 2")
    bot.add_game_to_state(state, user_id=123, game_name="Balatro")

    # Remove Helldivers using different case/spacing
    removed = bot.remove_game_from_state(
        state,
        user_id=123,
        game_name="  helL DiverS  2   ",
    )
    assert removed is True

    games = state["users"]["123"]["games"]

    # Only Balatro should remain
    assert games == ["Balatro"]


def test_list_games_from_state_returns_user_games() -> None:
    """
    list_games_from_state should:
    - retrieve all user games
    - return an empty list for missing users
    """
    state = {"users": {}}

    bot.add_game_to_state(state, user_id=123, game_name="Helldivers 2")
    bot.add_game_to_state(state, user_id=123, game_name="Balatro")

    games = bot.list_games_from_state(state, user_id=123)
    assert games == ["Helldivers 2", "Balatro"]

    games = bot.list_games_from_state(state, user_id=999)
    assert games == []


def test_get_common_games_returns_users_common_games() -> None:
    """
    get_common_games should:
    - retrieve all common games between two users
    - compare using normalized names
    - use user_a's spelling and order
    """
    state = {"users": {}}

    bot.add_game_to_state(state, user_id=123, game_name="Helldivers 2")
    bot.add_game_to_state(state, user_id=123, game_name="Balatro")
    bot.add_game_to_state(state, user_id=999, game_name="  helL DiverS  2   ")

    games = bot.get_common_games(state, user_id_a=123, user_id_b=999)
    assert games == ["Helldivers 2"]


def test_set_timezone_sets_users_timezone() -> None:
    """
    set_timezone_in_state should:
    - create the user entry if missing
    - set the user's timezone
    """
    state = {"users": {}}

    bot.set_timezone_in_state(state, user_id=123, tz="America/Los_Angeles")
    tz = state["users"]["123"]["timezone"]
    assert tz == "America/Los_Angeles"


def test_get_timezone_from_state_returns_users_timezone() -> None:
    """
    get_timezone_from_state should:
    - retrieve the user's timezone if present
    - return None for missing users or missing timezone
    """
    state = {"users": {}}

    bot.set_timezone_in_state(state, user_id=123, tz="America/Los_Angeles")

    tz = bot.get_timezone_from_state(state, user_id=123)
    assert tz == "America/Los_Angeles"

    tz = bot.get_timezone_from_state(state, user_id=999)
    assert tz is None


def test_set_day_availability_creates_user_and_initial_availability() -> None:
    """
    set_day_availability_in_state should:
    - create the user entry if missing
    - create an availability dict with all DAY_KEYS
    - set exactly one interval for the given day
    """
    state = {"users": {}}

    bot.set_day_availability_in_state(
        state,
        user_id=123,
        day="mon",
        start="18:00",
        end="22:00",
    )

    user = state["users"]["123"]
    assert "availability" in user

    availability = user["availability"]
    # All day keys should exist
    for day in bot.DAY_KEYS:
        assert day in availability

    # Only Monday should have a slot; others should be empty
    assert availability["mon"] == [{"start": "18:00", "end": "22:00"}]
    for day in bot.DAY_KEYS:
        if day != "mon":
            assert availability[day] == []


def test_set_day_availability_overwrites_existing_interval() -> None:
    """
    set_day_availability_in_state should:
    - overwrite an existing day's interval, not append a second one
    """
    state = {"users": {}}

    bot.set_day_availability_in_state(
        state,
        user_id=123,
        day="fri",
        start="18:00",
        end="22:00",
    )
    bot.set_day_availability_in_state(
        state,
        user_id=123,
        day="fri",
        start="19:30",
        end="23:00",
    )

    availability = state["users"]["123"]["availability"]
    assert availability["fri"] == [{"start": "19:30", "end": "23:00"}]
    # Still exactly one interval
    assert len(availability["fri"]) == 1


def test_set_day_availability_clears_day_when_start_or_end_missing() -> None:
    """
    set_day_availability_in_state should:
    - clear the day's availability when start or end is falsy
    """
    state = {"users": {}}

    # Start with a defined interval
    bot.set_day_availability_in_state(
        state,
        user_id=123,
        day="wed",
        start="18:00",
        end="22:00",
    )

    # Clear using None values
    bot.set_day_availability_in_state(
        state,
        user_id=123,
        day="wed",
        start=None,
        end=None,
    )

    availability = state["users"]["123"]["availability"]
    assert availability["wed"] == []


def test_get_availability_returns_all_days_empty_for_missing_user() -> None:
    """
    get_availability_from_state should:
    - return an all-days-empty dict for missing users
    - not create the user in state as a side effect
    """
    state = {"users": {}}

    availability = bot.get_availability_from_state(state, user_id=123)

    # All DAY_KEYS present, all empty lists
    for day in bot.DAY_KEYS:
        assert day in availability
        assert availability[day] == []

    # State should still not have this user
    assert "123" not in state["users"]


def test_get_availability_normalizes_partial_availability() -> None:
    """
    get_availability_from_state should:
    - normalize a partially defined availability dict
    - keep existing intervals for defined days
    - add missing DAY_KEYS as empty lists
    """
    state = {
        "users": {
            "123": {
                "games": [],
                "availability": {
                    "mon": [{"start": "18:00", "end": "22:00"}],
                },
            }
        }
    }

    availability = bot.get_availability_from_state(state, user_id=123)

    # Existing day preserved
    assert availability["mon"] == [{"start": "18:00", "end": "22:00"}]

    # All DAY_KEYS present
    for day in bot.DAY_KEYS:
        assert day in availability

    # Days that were not originally present should be empty
    for day in bot.DAY_KEYS:
        if day != "mon":
            assert availability[day] == []


def test_get_availability_returns_copies_not_backed_by_state() -> None:
    """
    get_availability_from_state should:
    - return a structure not backed by the underlying state
    - mutating the returned dict or lists should not mutate state
    """
    state = {
        "users": {
            "123": {
                "games": [],
                "availability": {
                    "mon": [{"start": "18:00", "end": "22:00"}],
                },
            }
        }
    }

    availability = bot.get_availability_from_state(state, user_id=123)

    # Mutate the returned structure
    availability["mon"].append({"start": "10:00", "end": "12:00"})
    availability["tue"] = [{"start": "09:00", "end": "11:00"}]

    # Underlying state should be unchanged
    stored_availability = state["users"]["123"]["availability"]
    assert stored_availability["mon"] == [{"start": "18:00", "end": "22:00"}]
    # "tue" should only exist if normalization added it, but it should still be []
    assert stored_availability.get("tue", []) == []
