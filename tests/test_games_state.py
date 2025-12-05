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
