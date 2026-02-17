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
    user_id TEXT NOT NULL,
    day TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    PRIMARY KEY (user_id, day),
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
        self.conn.executescript(_SCHEMA)

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

    def set_day_availability(
        self, user_id: int, day: str, start: str | None, end: str | None,
    ) -> None:
        self._ensure_user(user_id)
        if not start or not end:
            self.conn.execute(
                "DELETE FROM availability WHERE user_id = ? AND day = ?",
                (str(user_id), day),
            )
        else:
            self.conn.execute(
                "INSERT INTO availability (user_id, day, start_time, end_time) VALUES (?, ?, ?, ?) "
                "ON CONFLICT (user_id, day) DO UPDATE SET start_time = excluded.start_time, end_time = excluded.end_time",
                (str(user_id), day, start, end),
            )
        self.conn.commit()

    def get_availability(self, user_id: int) -> dict[str, list[dict[str, str]]]:
        result = _empty_availability()
        rows = self.conn.execute(
            "SELECT day, start_time, end_time FROM availability WHERE user_id = ?",
            (str(user_id),),
        ).fetchall()
        for day, start, end in rows:
            if day in result:
                result[day] = [{"start": start, "end": end}]
        return result

    def format_availability(self, user_id: int) -> str:
        tz = self.get_timezone(user_id)
        lines: list[str] = []
        lines.append(f"timezone: {tz}" if tz else "timezone: not set")

        availability = self.get_availability(user_id)
        for day in DAY_KEYS:
            slots = availability[day]
            if not slots:
                lines.append(f"{day}: none")
            else:
                slot = slots[0]
                lines.append(f"{day}: {slot['start']}-{slot['end']}")

        return "\n".join(lines)

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
