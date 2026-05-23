from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .engine import GameSnapshot, PlayerSnapshot, Position, WallPosition
from .settings import BOARD_SIZE_OPTIONS


@dataclass(frozen=True)
class LoadedGame:
    snapshot: GameSnapshot
    play_against_computer: bool
    computer_difficulty: str | None


class SaveManager:
    def __init__(self, save_file: Path, legacy_save_files: tuple[Path, ...] = ()) -> None:
        self.save_file = save_file
        self.legacy_save_files = legacy_save_files

    def exists(self) -> bool:
        return self._active_save_file() is not None

    def save(
        self,
        snapshot: GameSnapshot,
        play_against_computer: bool,
        computer_difficulty: str | None,
    ) -> None:
        payload = {
            "version": 1,
            "play_against_computer": play_against_computer,
            "computer_difficulty": computer_difficulty,
            "player_count": len(snapshot.players),
            "snapshot": self._snapshot_to_data(snapshot),
        }
        self.save_file.parent.mkdir(parents=True, exist_ok=True)
        self.save_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load(self) -> LoadedGame:
        save_file = self._active_save_file()
        if save_file is None:
            raise FileNotFoundError(self.save_file)

        data = json.loads(save_file.read_text(encoding="utf-8"))
        snapshot = self._snapshot_from_data(data.get("snapshot"))
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
        save_files = [save_file for save_file in (self.save_file, *self.legacy_save_files) if save_file.exists()]
        if not save_files:
            return None
        return max(save_files, key=lambda save_file: save_file.stat().st_mtime)

    def _snapshot_to_data(self, snapshot: GameSnapshot) -> dict[str, Any]:
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
        }

    def _snapshot_from_data(self, data: Any) -> GameSnapshot:
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
        return GameSnapshot(
            board_size=board_size,
            players=players,
            current_turn=current_turn,
            horizontal_walls=horizontal_walls,
            vertical_walls=vertical_walls,
            winner=winner,
            status=status,
        )

    def _player_snapshot_from_data(self, data: Any, board_size: int) -> PlayerSnapshot:
        if not isinstance(data, dict):
            raise ValueError("Saved player is invalid")

        name = data.get("name")
        if not isinstance(name, str):
            raise ValueError("Saved player name is invalid")

        pawn = self._position_from_data(data.get("pawn"), board_size)
        goal_axis = data.get("goal_axis")
        goal_index_data = data.get("goal_index")
        if goal_axis is None and "goal_row" in data:
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
        row, col = self._grid_pair_from_data(data)
        if not (0 <= row < board_size and 0 <= col < board_size):
            raise ValueError("Saved position is outside the board")
        return (row, col)

    def _wall_from_data(self, data: Any, board_size: int) -> WallPosition:
        row, col = self._grid_pair_from_data(data)
        if not (0 <= row < board_size - 1 and 0 <= col < board_size - 1):
            raise ValueError("Saved wall is outside the board")
        return (row, col)

    def _grid_pair_from_data(self, data: Any) -> tuple[int, int]:
        if not isinstance(data, list | tuple) or len(data) != 2:
            raise ValueError("Saved grid pair is invalid")
        row = self._int_from_data(data[0], "row")
        col = self._int_from_data(data[1], "column")
        return (row, col)

    def _int_from_data(self, data: Any, label: str) -> int:
        if type(data) is not int:
            raise ValueError(f"Saved {label} is invalid")
        return data
