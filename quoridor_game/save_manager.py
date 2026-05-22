"""
Persistent save and load for Quoridor matches.

``SaveManager`` writes a versioned JSON document containing:

- A full ``GameSnapshot`` (board, players, walls, turn, winner, recent moves).
- Flags for human vs computer mode and AI difficulty.

Saves go to ``SAVE_FILE`` from ``settings`` (under the user's AppData/home
Quoridor folder). Older saves may exist at ``LEGACY_SAVE_FILES``; ``exists`` and
``load`` pick the newest file among primary and legacy paths.

Validation
----------
Load paths validate types, board size, player count, indices, and coordinates
so corrupted files raise ``ValueError`` rather than silently breaking the game.
Legacy player JSON may use ``goal_row`` instead of ``goal_axis`` / ``goal_index``.
"""

from __future__ import annotations  # Modern type annotations without forward-ref strings

import json  # Serialize snapshots to UTF-8 JSON on disk
from dataclasses import dataclass  # LoadedGame result container
from pathlib import Path  # Save file locations
from typing import Any  # Untyped JSON dict values during parsing

from .engine import GameSnapshot, PawnMoveSnapshot, PlayerSnapshot, Position, WallPosition
from .settings import BOARD_SIZE_OPTIONS  # Allowed board dimensions for validation


@dataclass(frozen=True)
class LoadedGame:
    """
    Result of a successful ``SaveManager.load()`` call.

    ``snapshot`` is the board state; the boolean and difficulty describe how
    ``QuoridorApp`` should configure the AI after restore.
    """

    snapshot: GameSnapshot  # Immutable full game state
    play_against_computer: bool  # Whether player 1 is the computer
    computer_difficulty: str | None  # "easy" | "medium" | "hard", or None for human games


class SaveManager:
    """
    Read and write Quoridor save files as JSON with schema version 1.

    Construct with primary ``save_file`` and optional ``legacy_save_files`` for
    migration from older install locations.
    """

    def __init__(self, save_file: Path, legacy_save_files: tuple[Path, ...] = ()) -> None:
        """
        Store primary and legacy save paths; does not touch disk until save/load.
        """
        self.save_file = save_file  # Canonical save location
        self.legacy_save_files = legacy_save_files  # Older paths checked if primary missing

    def exists(self) -> bool:
        """
        Return True if any known save file exists on disk.

        Uses the same resolution rules as ``load`` (newest mtime wins).
        """
        return self._active_save_file() is not None

    def save(
        self,
        snapshot: GameSnapshot,
        play_against_computer: bool,
        computer_difficulty: str | None,
    ) -> None:
        """
        Write the current match to ``save_file`` as indented JSON.

        Creates parent directories if needed. Raises ``OSError`` on I/O failure.
        """
        payload = {  # Top-level document written to disk
            "version": 1,  # Schema version for future migrations
            "play_against_computer": play_against_computer,
            "computer_difficulty": computer_difficulty,
            "player_count": len(snapshot.players),  # Redundant but convenient for inspection
            "snapshot": self._snapshot_to_data(snapshot),  # Nested board state
        }
        self.save_file.parent.mkdir(parents=True, exist_ok=True)  # Ensure Quoridor folder exists
        self.save_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")  # Human-readable JSON

    def load(self) -> LoadedGame:
        """
        Load and validate the newest available save file.

        Raises ``FileNotFoundError`` if none exist, ``ValueError`` for invalid
        content, ``OSError`` for read failures.
        """
        save_file = self._active_save_file()  # Pick primary or newest legacy file
        if save_file is None:
            raise FileNotFoundError(self.save_file)

        data = json.loads(save_file.read_text(encoding="utf-8"))  # Parse JSON root object
        snapshot = self._snapshot_from_data(data.get("snapshot"))  # Build frozen GameSnapshot
        play_against_computer = bool(data.get("play_against_computer", False))
        computer_difficulty = data.get("computer_difficulty")

        if play_against_computer and computer_difficulty not in {"easy", "medium", "hard"}:
            raise ValueError("Saved computer difficulty is invalid")
        if play_against_computer and len(snapshot.players) != 2:
            raise ValueError("Saved computer game must have 2 players")

        return LoadedGame(
            snapshot=snapshot,
            play_against_computer=play_against_computer,
            computer_difficulty=computer_difficulty if play_against_computer else None,
        )

    def _active_save_file(self) -> Path | None:
        """
        Return the path to use for load: newest existing among primary and legacy.

        Returns ``None`` when no save file is found.
        """
        save_files = [save_file for save_file in (self.save_file, *self.legacy_save_files) if save_file.exists()]
        if not save_files:
            return None
        return max(save_files, key=lambda save_file: save_file.stat().st_mtime)  # Most recently modified

    def _snapshot_to_data(self, snapshot: GameSnapshot) -> dict[str, Any]:
        """
        Convert a ``GameSnapshot`` to a JSON-serializable dict.

        Positions and walls are stored as ``[row, col]`` lists for readability.
        """
        return {
            "board_size": snapshot.board_size,
            "players": [
                {
                    "name": player.name,
                    "pawn": list(player.pawn),
                    "goal_axis": player.goal_axis,
                    "goal_index": player.goal_index,
                    "walls_remaining": player.walls_remaining,
                }
                for player in snapshot.players
            ],
            "current_turn": snapshot.current_turn,
            "horizontal_walls": [list(wall) for wall in sorted(snapshot.horizontal_walls)],
            "vertical_walls": [list(wall) for wall in sorted(snapshot.vertical_walls)],
            "winner": snapshot.winner,
            "status": snapshot.status,
            "recent_pawn_moves": [
                {
                    "player_index": move.player_index,
                    "start": list(move.start),
                    "end": list(move.end),
                }
                for move in snapshot.recent_pawn_moves
            ],
        }

    def _snapshot_from_data(self, data: Any) -> GameSnapshot:
        """
        Parse a snapshot dict from JSON into a validated ``GameSnapshot``.

        Raises ``ValueError`` with specific messages when fields are missing or invalid.
        """
        if not isinstance(data, dict):
            raise ValueError("Saved snapshot is missing")

        board_size = self._int_from_data(data.get("board_size"), "board size")
        if board_size not in BOARD_SIZE_OPTIONS:
            raise ValueError("Saved board size is invalid")

        players_data = data.get("players")
        if not isinstance(players_data, list) or len(players_data) not in {2, 4}:
            raise ValueError("Saved players are invalid")

        players = tuple(self._player_snapshot_from_data(player, board_size) for player in players_data)
        current_turn = self._int_from_data(data.get("current_turn"), "current turn")
        if not 0 <= current_turn < len(players):
            raise ValueError("Saved turn is invalid")

        winner_data = data.get("winner")
        winner = None if winner_data is None else self._int_from_data(winner_data, "winner")
        if winner is not None and not 0 <= winner < len(players):
            raise ValueError("Saved winner is invalid")

        status = data.get("status")
        if not isinstance(status, str):
            raise ValueError("Saved status is invalid")

        horizontal_walls = frozenset(
            self._wall_from_data(wall, board_size) for wall in data.get("horizontal_walls", [])
        )
        vertical_walls = frozenset(
            self._wall_from_data(wall, board_size) for wall in data.get("vertical_walls", [])
        )
        recent_pawn_moves_data = data.get("recent_pawn_moves", [])
        if not isinstance(recent_pawn_moves_data, list):
            raise ValueError("Saved pawn move history is invalid")
        recent_pawn_moves = tuple(
            self._pawn_move_from_data(move, board_size, len(players))
            for move in recent_pawn_moves_data
        )

        return GameSnapshot(
            board_size=board_size,
            players=players,
            current_turn=current_turn,
            horizontal_walls=horizontal_walls,
            vertical_walls=vertical_walls,
            winner=winner,
            status=status,
            recent_pawn_moves=recent_pawn_moves,
        )

    def _player_snapshot_from_data(self, data: Any, board_size: int) -> PlayerSnapshot:
        """
        Parse one player object from JSON into ``PlayerSnapshot``.

        Supports legacy ``goal_row`` field mapped to row-based goals.
        """
        if not isinstance(data, dict):
            raise ValueError("Saved player is invalid")

        name = data.get("name")
        if not isinstance(name, str):
            raise ValueError("Saved player name is invalid")

        pawn = self._position_from_data(data.get("pawn"), board_size)
        goal_axis = data.get("goal_axis")
        goal_index_data = data.get("goal_index")
        if goal_axis is None and "goal_row" in data:  # Backward compatibility with older saves
            goal_axis = "row"
            goal_index_data = data.get("goal_row")
        if goal_axis not in {"row", "col"}:
            raise ValueError("Saved goal axis is invalid")

        goal_index = self._int_from_data(goal_index_data, "goal index")
        if not 0 <= goal_index < board_size:
            raise ValueError("Saved goal index is invalid")

        walls_remaining = self._int_from_data(data.get("walls_remaining"), "walls remaining")
        if walls_remaining < 0:
            raise ValueError("Saved wall count is invalid")

        return PlayerSnapshot(
            name=name,
            pawn=pawn,
            goal_axis=goal_axis,
            goal_index=goal_index,
            walls_remaining=walls_remaining,
        )

    def _position_from_data(self, data: Any, board_size: int) -> Position:
        """
        Parse a pawn cell ``[row, col]`` and ensure it lies on the board.
        """
        row, col = self._grid_pair_from_data(data)
        if not (0 <= row < board_size and 0 <= col < board_size):
            raise ValueError("Saved position is outside the board")
        return (row, col)

    def _wall_from_data(self, data: Any, board_size: int) -> WallPosition:
        """
        Parse a wall anchor ``[row, col]`` in the (board_size - 1) wall grid.
        """
        row, col = self._grid_pair_from_data(data)
        if not (0 <= row < board_size - 1 and 0 <= col < board_size - 1):
            raise ValueError("Saved wall is outside the board")
        return (row, col)

    def _pawn_move_from_data(self, data: Any, board_size: int, player_count: int) -> PawnMoveSnapshot:
        """
        Parse one recent pawn move record for AI repetition heuristics on load.
        """
        if not isinstance(data, dict):
            raise ValueError("Saved pawn move is invalid")

        player_index = self._int_from_data(data.get("player_index"), "pawn move player")
        if not 0 <= player_index < player_count:
            raise ValueError("Saved pawn move player is invalid")

        return PawnMoveSnapshot(
            player_index=player_index,
            start=self._position_from_data(data.get("start"), board_size),
            end=self._position_from_data(data.get("end"), board_size),
        )

    def _grid_pair_from_data(self, data: Any) -> tuple[int, int]:
        """
        Parse a two-element list/tuple as ``(row, col)`` integers.
        """
        if not isinstance(data, list | tuple) or len(data) != 2:
            raise ValueError("Saved grid pair is invalid")
        row = self._int_from_data(data[0], "row")
        col = self._int_from_data(data[1], "column")
        return (row, col)

    def _int_from_data(self, data: Any, label: str) -> int:
        """
        Require a strict JSON int (not bool) for numeric fields.

        JSON booleans are subclasses of int in Python, so ``type(data) is not int``
        rejects ``true``/``false`` mistaken for numbers.
        """
        if type(data) is not int:
            raise ValueError(f"Saved {label} is invalid")
        return data
