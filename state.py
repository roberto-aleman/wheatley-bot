from itertools import groupby
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)

DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

DB_PATH = Path(__file__).parent / "data" / "state.db"

_MIGRATIONS: list[str] = [
    # v1: initial schema
    """
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
    """,
    # v2: multi-slot availability (replaces old single-slot table)
    """
    DROP TABLE IF EXISTS availability;
    CREATE TABLE availability (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        day TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    """,
    # v3: index for availability lookups by user and day
    """
    CREATE INDEX IF NOT EXISTS idx_availability_user_day ON availability(user_id, day);
    """,
]


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


def _uid(user_id: int) -> str:
    """Central conversion of Discord user ID to DB string key."""
    return str(user_id)


def _slots_overlap(s1_start: str, s1_end: str, s2_start: str, s2_end: str) -> bool:
    """Check if two normal (non-overnight) slots overlap or share a boundary."""
    return s1_start <= s2_end and s1_end >= s2_start


def _merge_slot(existing_start: str, existing_end: str, new_start: str, new_end: str) -> tuple[str, str]:
    """Merge two overlapping normal slots."""
    return min(existing_start, new_start), max(existing_end, new_end)


class Database:
    def __init__(self, path: Path = DB_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    def _migrate(self) -> None:
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)",
        )
        row = self.conn.execute("SELECT version FROM schema_version").fetchone()
        current = row[0] if row else 0

        for i, sql in enumerate(_MIGRATIONS[current:], start=current):
            log.info("Applying migration v%s", i + 1)
            self.conn.executescript(sql)

        new_version = len(_MIGRATIONS)
        if current == 0:
            self.conn.execute("INSERT INTO schema_version (version) VALUES (?)", (new_version,))
        elif new_version > current:
            self.conn.execute("UPDATE schema_version SET version = ?", (new_version,))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def _ensure_user(self, user_id: int) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
            (_uid(user_id),),
        )

    # --- Games ---

    def add_game(self, user_id: int, game_name: str) -> None:
        self._ensure_user(user_id)
        normalized = normalize_game_name(game_name)
        self.conn.execute(
            "INSERT INTO games (user_id, game_name, normalized) VALUES (?, ?, ?) "
            "ON CONFLICT (user_id, normalized) DO UPDATE SET game_name = excluded.game_name",
            (_uid(user_id), game_name, normalized),
        )
        self.conn.commit()

    def remove_game(self, user_id: int, game_name: str) -> bool:
        normalized = normalize_game_name(game_name)
        cur = self.conn.execute(
            "DELETE FROM games WHERE user_id = ? AND normalized = ?",
            (_uid(user_id), normalized),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def list_games(self, user_id: int) -> list[str]:
        rows = self.conn.execute(
            "SELECT game_name FROM games WHERE user_id = ? ORDER BY rowid",
            (_uid(user_id),),
        ).fetchall()
        return [r[0] for r in rows]

    def get_common_games(self, user_id_a: int, user_id_b: int) -> list[str]:
        rows = self.conn.execute(
            "SELECT a.game_name FROM games a "
            "JOIN games b ON a.normalized = b.normalized "
            "WHERE a.user_id = ? AND b.user_id = ? "
            "ORDER BY a.rowid",
            (_uid(user_id_a), _uid(user_id_b)),
        ).fetchall()
        return [r[0] for r in rows]

    # --- Timezone ---

    def set_timezone(self, user_id: int, tz: str) -> None:
        self._ensure_user(user_id)
        self.conn.execute(
            "UPDATE users SET timezone = ? WHERE user_id = ?",
            (tz, _uid(user_id)),
        )
        self.conn.commit()

    def get_timezone(self, user_id: int) -> str | None:
        row = self.conn.execute(
            "SELECT timezone FROM users WHERE user_id = ?",
            (_uid(user_id),),
        ).fetchone()
        if row and row[0]:
            return row[0]
        return None

    # --- Availability ---

    def _add_normal_slot(self, uid: str, day: str, start: str, end: str) -> None:
        """Insert a single normal (non-overnight) slot, merging with existing overlaps."""
        rows = self.conn.execute(
            "SELECT id, start_time, end_time FROM availability WHERE user_id = ? AND day = ?",
            (uid, day),
        ).fetchall()

        new_start, new_end = start, end
        ids_to_delete: list[int] = []

        for row_id, s, e in rows:
            if _slots_overlap(new_start, new_end, s, e):
                new_start, new_end = _merge_slot(s, e, new_start, new_end)
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

    def add_day_availability(
        self, user_id: int, day: str, start: str, end: str,
    ) -> None:
        if day not in DAY_KEYS:
            raise ValueError(f"Invalid day: {day!r}")
        if start == end:
            raise ValueError("Start and end times must differ")
        self._ensure_user(user_id)
        uid = _uid(user_id)

        if start < end:
            self._add_normal_slot(uid, day, start, end)
        else:
            # Overnight: split at midnight into two normal slots
            next_day = DAY_KEYS[(DAY_KEYS.index(day) + 1) % 7]
            self._add_normal_slot(uid, day, start, "24:00")
            self._add_normal_slot(uid, next_day, "00:00", end)

        self.conn.commit()

    def clear_day_availability(self, user_id: int, day: str) -> None:
        if day not in DAY_KEYS:
            raise ValueError(f"Invalid day: {day!r}")
        self.conn.execute(
            "DELETE FROM availability WHERE user_id = ? AND day = ?",
            (_uid(user_id), day),
        )
        self.conn.commit()

    def get_availability(self, user_id: int) -> dict[str, list[dict[str, str]]]:
        result = _empty_availability()
        rows = self.conn.execute(
            "SELECT day, start_time, end_time FROM availability WHERE user_id = ? ORDER BY start_time",
            (_uid(user_id),),
        ).fetchall()
        for day, start, end in rows:
            if day in result:
                result[day].append({"start": start, "end": end})
        return result

    # --- Matchmaking ---

    def _available_user_ids(self, now_utc: datetime) -> set[int]:
        """Return user IDs that are available right now, filtering in bulk."""
        rows = self.conn.execute(
            "SELECT u.user_id, u.timezone FROM users u "
            "WHERE u.timezone IS NOT NULL "
            "AND EXISTS (SELECT 1 FROM availability a WHERE a.user_id = u.user_id)",
        ).fetchall()

        available: set[int] = set()
        for uid_str, tz_name in rows:
            try:
                tz = ZoneInfo(tz_name)
            except (KeyError, ValueError):
                continue

            local_now = now_utc.astimezone(tz)
            today = DAY_KEYS[local_now.weekday()]
            now_str = local_now.strftime("%H:%M")

            row = self.conn.execute(
                "SELECT 1 FROM availability WHERE user_id = ? AND day = ? "
                "AND start_time <= ? AND end_time > ?",
                (uid_str, today, now_str, now_str),
            ).fetchone()
            if row:
                available.add(int(uid_str))

        return available

    def find_ready_players(
        self, invoker_id: int, now_utc: datetime, game_filter: str | None = None,
    ) -> list[tuple[int, list[str]]]:
        available = self._available_user_ids(now_utc)
        available.discard(invoker_id)

        if not available:
            return []

        # Find common games between invoker and all available users in one query
        placeholders = ",".join("?" * len(available))
        params: list[str | int] = [_uid(invoker_id)]
        params.extend(_uid(uid) for uid in available)

        rows = self.conn.execute(
            f"SELECT b.user_id, a.game_name, a.normalized FROM games a "
            f"JOIN games b ON a.normalized = b.normalized "
            f"WHERE a.user_id = ? AND b.user_id IN ({placeholders}) "
            f"ORDER BY b.user_id, a.rowid",
            params,
        ).fetchall()

        norm_filter = normalize_game_name(game_filter) if game_filter else None

        # Group by user
        results: list[tuple[int, list[str]]] = []
        for uid_str, group in groupby(rows, key=lambda r: r[0]):
            games = []
            for _, game_name, normalized in group:
                if norm_filter and normalized != norm_filter:
                    continue
                games.append(game_name)
            if games:
                results.append((int(uid_str), games))

        results.sort(key=lambda x: x[0])
        return results

    # --- Stats ---

    def user_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) FROM users").fetchone()
        return row[0] if row else 0

    def all_game_names(self) -> list[str]:
        """Return distinct game names across all users, ordered alphabetically."""
        rows = self.conn.execute(
            "SELECT DISTINCT game_name FROM games ORDER BY game_name",
        ).fetchall()
        return [r[0] for r in rows]
