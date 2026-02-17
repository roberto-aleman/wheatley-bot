import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

DB_PATH = Path(__file__).parent / "data" / "state.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    timezone TEXT
);
CREATE TABLE IF NOT EXISTS games (
    user_id TEXT NOT NULL,
    game_name TEXT NOT NULL,
    normalized TEXT NOT NULL,
    PRIMARY KEY (user_id, normalized),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE TABLE IF NOT EXISTS availability (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    day TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
"""


def normalize_game_name(name: str) -> str:
    """Lowercase the name and remove all whitespace."""
    return "".join(name.split()).lower()


def validate_time(t: str) -> bool:
    """Return True if t is a valid HH:MM time string."""
    try:
        datetime.strptime(t, "%H:%M")
        return True
    except ValueError:
        return False


def _empty_availability() -> dict[str, list[dict[str, str]]]:
    return {day: [] for day in DAY_KEYS}


class Database:
    def __init__(self, path: Path = DB_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._migrate()
        self.conn.executescript(_SCHEMA)

    def _migrate(self) -> None:
        """Drop old availability table if it has the single-slot schema."""
        row = self.conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='availability'",
        ).fetchone()
        if row and "PRIMARY KEY (user_id, day)" in row[0]:
            self.conn.execute("DROP TABLE availability")

    def close(self) -> None:
        self.conn.close()

    def _ensure_user(self, user_id: int) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
            (str(user_id),),
        )

    # --- Games ---

    def add_game(self, user_id: int, game_name: str) -> None:
        self._ensure_user(user_id)
        normalized = normalize_game_name(game_name)
        self.conn.execute(
            "INSERT INTO games (user_id, game_name, normalized) VALUES (?, ?, ?) "
            "ON CONFLICT (user_id, normalized) DO UPDATE SET game_name = excluded.game_name",
            (str(user_id), game_name, normalized),
        )
        self.conn.commit()

    def remove_game(self, user_id: int, game_name: str) -> bool:
        normalized = normalize_game_name(game_name)
        cur = self.conn.execute(
            "DELETE FROM games WHERE user_id = ? AND normalized = ?",
            (str(user_id), normalized),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def list_games(self, user_id: int) -> list[str]:
        rows = self.conn.execute(
            "SELECT game_name FROM games WHERE user_id = ? ORDER BY rowid",
            (str(user_id),),
        ).fetchall()
        return [r[0] for r in rows]

    def get_common_games(self, user_id_a: int, user_id_b: int) -> list[str]:
        rows = self.conn.execute(
            "SELECT a.game_name FROM games a "
            "JOIN games b ON a.normalized = b.normalized "
            "WHERE a.user_id = ? AND b.user_id = ? "
            "ORDER BY a.rowid",
            (str(user_id_a), str(user_id_b)),
        ).fetchall()
        return [r[0] for r in rows]

    # --- Timezone ---

    def set_timezone(self, user_id: int, tz: str) -> None:
        self._ensure_user(user_id)
        self.conn.execute(
            "UPDATE users SET timezone = ? WHERE user_id = ?",
            (tz, str(user_id)),
        )
        self.conn.commit()

    def get_timezone(self, user_id: int) -> str | None:
        row = self.conn.execute(
            "SELECT timezone FROM users WHERE user_id = ?",
            (str(user_id),),
        ).fetchone()
        if row and row[0]:
            return row[0]
        return None

    # --- Availability ---

    def add_day_availability(
        self, user_id: int, day: str, start: str, end: str,
    ) -> None:
        self._ensure_user(user_id)
        uid = str(user_id)

        # Fetch existing slots for this day
        rows = self.conn.execute(
            "SELECT id, start_time, end_time FROM availability WHERE user_id = ? AND day = ?",
            (uid, day),
        ).fetchall()

        new_start, new_end = start, end
        ids_to_delete: list[int] = []

        for row_id, s, e in rows:
            # Check if the new slot overlaps or is adjacent to this existing slot
            if new_start <= e and new_end >= s:
                new_start = min(new_start, s)
                new_end = max(new_end, e)
                ids_to_delete.append(row_id)

        if ids_to_delete:
            placeholders = ",".join("?" * len(ids_to_delete))
            self.conn.execute(
                f"DELETE FROM availability WHERE id IN ({placeholders})",
                ids_to_delete,
            )

        self.conn.execute(
            "INSERT INTO availability (user_id, day, start_time, end_time) VALUES (?, ?, ?, ?)",
            (uid, day, new_start, new_end),
        )
        self.conn.commit()

    def clear_day_availability(self, user_id: int, day: str) -> None:
        self.conn.execute(
            "DELETE FROM availability WHERE user_id = ? AND day = ?",
            (str(user_id), day),
        )
        self.conn.commit()

    def get_availability(self, user_id: int) -> dict[str, list[dict[str, str]]]:
        result = _empty_availability()
        rows = self.conn.execute(
            "SELECT day, start_time, end_time FROM availability WHERE user_id = ? ORDER BY start_time",
            (str(user_id),),
        ).fetchall()
        for day, start, end in rows:
            if day in result:
                result[day].append({"start": start, "end": end})
        return result

    # --- Matchmaking ---

    def is_user_available_now(self, user_id: int, now_utc: datetime) -> bool:
        tz_name = self.get_timezone(user_id)
        if not tz_name:
            return False

        try:
            tz = ZoneInfo(tz_name)
        except (KeyError, ValueError):
            return False

        local_now = now_utc.astimezone(tz)
        today = DAY_KEYS[local_now.weekday()]
        yesterday = DAY_KEYS[(local_now.weekday() - 1) % 7]
        now_str = local_now.strftime("%H:%M")
        uid = str(user_id)

        # Normal window: start < end (e.g. 18:00–22:00)
        row = self.conn.execute(
            "SELECT 1 FROM availability WHERE user_id = ? AND day = ? "
            "AND start_time < end_time AND start_time <= ? AND end_time > ?",
            (uid, today, now_str, now_str),
        ).fetchone()
        if row:
            return True

        # Today's window spans midnight (start >= end), currently past start
        row = self.conn.execute(
            "SELECT 1 FROM availability WHERE user_id = ? AND day = ? "
            "AND start_time >= end_time AND start_time <= ?",
            (uid, today, now_str),
        ).fetchone()
        if row:
            return True

        # Yesterday's window spans midnight, we're in the early-morning portion
        row = self.conn.execute(
            "SELECT 1 FROM availability WHERE user_id = ? AND day = ? "
            "AND start_time >= end_time AND end_time > ?",
            (uid, yesterday, now_str),
        ).fetchone()
        return row is not None

    def find_ready_players(
        self, invoker_id: int, now_utc: datetime, game_filter: str | None = None,
    ) -> list[tuple[int, list[str]]]:
        rows = self.conn.execute(
            "SELECT user_id FROM users WHERE user_id != ?",
            (str(invoker_id),),
        ).fetchall()

        results: list[tuple[int, list[str]]] = []
        for (user_key,) in rows:
            other_id = int(user_key)
            if not self.is_user_available_now(other_id, now_utc):
                continue

            common = self.get_common_games(invoker_id, other_id)
            if not common:
                continue

            if game_filter:
                norm_filter = normalize_game_name(game_filter)
                common = [g for g in common if normalize_game_name(g) == norm_filter]
                if not common:
                    continue

            results.append((other_id, common))

        results.sort(key=lambda x: x[0])
        return results

    # --- Migration ---

    def user_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) FROM users").fetchone()
        return row[0] if row else 0

    def all_game_names(self) -> list[str]:
        """Return distinct game names across all users, ordered alphabetically."""
        rows = self.conn.execute(
            "SELECT DISTINCT game_name FROM games ORDER BY game_name",
        ).fetchall()
        return [r[0] for r in rows]
