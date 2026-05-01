from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import Any

import pygame

from .engine import DEFAULT_BOARD_SIZE, DEFAULT_PLAYER_COUNT, GameSnapshot, PlayerSnapshot, Position, QuoridorGame, WallPosition


WINDOW_WIDTH = 700
WINDOW_HEIGHT = 700
BOARD_LEFT = 28
BOARD_TOP = 22
GAP_SIZE = 8
BOARD_SIZE_OPTIONS = (7, 9, 11)
CELL_SIZE_BY_BOARD_SIZE = {
    7: 60,
    9: 46,
    11: 36,
}
SAVE_FILE = Path(__file__).resolve().parent.parent / "saved_game.json"
FPS = 60

BACKGROUND = (24, 31, 38)
BOARD_FRAME = (203, 177, 124)
CELL_LIGHT = (245, 232, 198)
CELL_DARK = (225, 208, 168)
GRID_GAP = (169, 142, 92)
PLAYER_ONE = (47, 95, 168)
PLAYER_TWO = (182, 72, 54)
PLAYER_THREE = (73, 145, 93)
PLAYER_FOUR = (177, 126, 49)
PLAYER_RING = (250, 247, 239)
MOVE_HINT = (72, 148, 86)
TEXT_PRIMARY = (245, 246, 248)
TEXT_MUTED = (184, 194, 204)
BUTTON_IDLE = (58, 74, 92)
BUTTON_ACTIVE = (92, 126, 162)
BUTTON_DISABLED = (82, 83, 86)
WALL_COLOR = (78, 52, 28)
VALID_PREVIEW = (87, 168, 103)
INVALID_PREVIEW = (190, 78, 78)

ComputerAction = tuple[str, Position] | tuple[str, str, WallPosition]


class QuoridorApp:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Quoridor")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.selected_board_size = DEFAULT_BOARD_SIZE
        self.selected_player_count = DEFAULT_PLAYER_COUNT
        self.game = QuoridorGame(self.selected_board_size, self.selected_player_count)
        self._configure_board_metrics()
        self.show_setup = True
        self.play_against_computer = False
        self.computer_difficulty: str | None = None
        self.selected_opponent: str | None = None
        self.notice = ""
        self.mode = "move"
        self.selected_pawn = False
        self.legal_moves: list[tuple[int, int]] = []
        self.history: list[GameSnapshot] = [self.game.snapshot()]
        self.history_index = 0
        self.title_font = pygame.font.SysFont("arial", 28, bold=True)
        self.body_font = pygame.font.SysFont("arial", 20, bold=True)
        self.small_font = pygame.font.SysFont("arial", 17)
        self.buttons = self._build_buttons()
        self.setup_buttons = self._build_setup_buttons()

    def _configure_board_metrics(self) -> None:
        self.board_size = self.game.board_size
        self.cell_size = CELL_SIZE_BY_BOARD_SIZE[self.board_size]
        self.board_pixels = self.board_size * self.cell_size + (self.board_size - 1) * GAP_SIZE
        self.panel_top = BOARD_TOP + self.board_pixels + 18

    def run(self) -> None:
        while True:
            self._handle_events()
            self._maybe_take_computer_turn()
            self._draw()
            pygame.display.flip()
            self.clock.tick(FPS)

    def _build_buttons(self) -> dict[str, pygame.Rect]:
        button_width = 74
        button_height = 38
        start_x = BOARD_LEFT
        start_y = self.panel_top + 88
        spacing = 6
        return {
            "move": pygame.Rect(start_x, start_y, button_width, button_height),
            "wall_h": pygame.Rect(start_x + button_width + spacing, start_y, button_width, button_height),
            "wall_v": pygame.Rect(start_x + 2 * (button_width + spacing), start_y, button_width, button_height),
            "undo": pygame.Rect(start_x + 3 * (button_width + spacing), start_y, button_width, button_height),
            "redo": pygame.Rect(start_x + 4 * (button_width + spacing), start_y, button_width, button_height),
            "reset": pygame.Rect(start_x + 5 * (button_width + spacing), start_y, button_width, button_height),
            "save": pygame.Rect(start_x + 6 * (button_width + spacing), start_y, button_width, button_height),
            "menu": pygame.Rect(start_x + 7 * (button_width + spacing), start_y, button_width, button_height),
        }

    def _build_setup_buttons(self) -> dict[str, pygame.Rect]:
        button_width = 180
        button_height = 44
        size_button_width = 136
        center_x = WINDOW_WIDTH // 2
        return {
            "size_7": pygame.Rect(center_x - size_button_width - 78, 164, size_button_width, button_height),
            "size_9": pygame.Rect(center_x - size_button_width // 2, 164, size_button_width, button_height),
            "size_11": pygame.Rect(center_x + 78, 164, size_button_width, button_height),
            "human": pygame.Rect(center_x - button_width - 10, 276, button_width, button_height),
            "computer": pygame.Rect(center_x + 10, 276, button_width, button_height),
            "players_2": pygame.Rect(center_x - button_width - 10, 388, button_width, button_height),
            "players_4": pygame.Rect(center_x + 10, 388, button_width, button_height),
            "easy": pygame.Rect(center_x - 270, 388, 160, button_height),
            "medium": pygame.Rect(center_x - 80, 388, 160, button_height),
            "hard": pygame.Rect(center_x + 110, 388, 160, button_height),
            "load": pygame.Rect(center_x - 125, 488, 250, button_height),
        }

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                self._handle_key(event)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_click(event.pos)

    def _handle_key(self, event: pygame.event.Event) -> None:
        if self.show_setup:
            return

        key = event.key
        ctrl_pressed = bool(pygame.key.get_mods() & pygame.KMOD_CTRL)
        shift_pressed = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)

        if ctrl_pressed and key == pygame.K_z and shift_pressed:
            self._redo()
        elif ctrl_pressed and key == pygame.K_z:
            self._undo()
        elif ctrl_pressed and key == pygame.K_s:
            self._save_game()
        elif ctrl_pressed and key == pygame.K_y:
            self._redo()
        elif key == pygame.K_u:
            self._undo()
        elif key == pygame.K_y:
            self._redo()
        if key == pygame.K_r:
            self._reset_game()
        elif key == pygame.K_m:
            self._set_mode("move")
        elif key == pygame.K_h:
            self._set_mode("wall_h")
        elif key == pygame.K_v:
            self._set_mode("wall_v")

    def _handle_click(self, mouse_pos: tuple[int, int]) -> None:
        if self.show_setup:
            self._handle_setup_click(mouse_pos)
            return

        for name, rect in self.buttons.items():
            if rect.collidepoint(mouse_pos):
                if name == "reset":
                    self._reset_game()
                elif name == "menu":
                    self._return_to_menu()
                elif name == "undo":
                    self._undo()
                elif name == "redo":
                    self._redo()
                elif name == "save":
                    self._save_game()
                elif self._is_computer_turn():
                    return
                else:
                    self._set_mode(name)
                return

        if self._is_computer_turn():
            return

        if self.mode == "move":
            self._handle_move_click(mouse_pos)
            return

        if self.mode in {"wall_h", "wall_v"}:
            slot = self._wall_slot_at(mouse_pos, "h" if self.mode == "wall_h" else "v")
            if slot is not None:
                if self.game.place_wall("h" if self.mode == "wall_h" else "v", slot):
                    self._record_current_state()
                    self.selected_pawn = False
                    self.legal_moves = []

    def _handle_setup_click(self, mouse_pos: tuple[int, int]) -> None:
        if self.setup_buttons["load"].collidepoint(mouse_pos):
            self._load_game()
            return

        for board_size in BOARD_SIZE_OPTIONS:
            if self.setup_buttons[f"size_{board_size}"].collidepoint(mouse_pos):
                self.selected_board_size = board_size
                self.notice = ""
                return

        if self.setup_buttons["human"].collidepoint(mouse_pos):
            self.selected_opponent = "human"
            return

        if self.setup_buttons["computer"].collidepoint(mouse_pos):
            self.selected_opponent = "computer"
            self.selected_player_count = 2
            return

        if self.selected_opponent == "human":
            for player_count in (2, 4):
                if self.setup_buttons[f"players_{player_count}"].collidepoint(mouse_pos):
                    self.selected_player_count = player_count
                    self._start_match(play_against_computer=False, player_count=player_count)
                    return

        if self.selected_opponent == "computer":
            for difficulty in ("easy", "medium", "hard"):
                if self.setup_buttons[difficulty].collidepoint(mouse_pos):
                    self.selected_player_count = 2
                    self._start_match(play_against_computer=True, difficulty=difficulty, player_count=2)
                    return

    def _handle_move_click(self, mouse_pos: tuple[int, int]) -> None:
        if self.game.winner is not None:
            return

        cell = self._cell_at(mouse_pos)
        if cell is None:
            self.selected_pawn = False
            self.legal_moves = []
            return

        if not self.selected_pawn:
            if cell == self.game.current_player.pawn:
                self.selected_pawn = True
                self.legal_moves = self.game.legal_moves_for_current_player()
            return

        if cell == self.game.current_player.pawn:
            self.selected_pawn = False
            self.legal_moves = []
            return

        if self.game.move_pawn(cell):
            self._record_current_state()
            self.selected_pawn = False
            self.legal_moves = []
            return

        if cell == self.game.current_player.pawn:
            self.selected_pawn = True
            self.legal_moves = self.game.legal_moves_for_current_player()
        else:
            self.selected_pawn = False
            self.legal_moves = []

    def _reset_game(self) -> None:
        self.game.reset()
        self.game.players[1].name = self._player_two_name()
        self._configure_board_metrics()
        self.buttons = self._build_buttons()
        self._reset_history()
        self.notice = ""
        self.mode = "move"
        self.selected_pawn = False
        self.legal_moves = []

    def _start_match(
        self,
        play_against_computer: bool,
        difficulty: str | None = None,
        player_count: int = DEFAULT_PLAYER_COUNT,
    ) -> None:
        self.show_setup = False
        self.play_against_computer = play_against_computer
        self.computer_difficulty = difficulty
        self.selected_player_count = 2 if play_against_computer else player_count
        self.game = QuoridorGame(self.selected_board_size, self.selected_player_count)
        self.game.players[1].name = self._player_two_name()
        self._configure_board_metrics()
        self.buttons = self._build_buttons()
        self._reset_history()
        self.notice = ""
        self.mode = "move"
        self.selected_pawn = False
        self.legal_moves = []

    def _return_to_menu(self) -> None:
        self.show_setup = True
        self.selected_opponent = None
        self.play_against_computer = False
        self.computer_difficulty = None
        self.game = QuoridorGame(self.selected_board_size, self.selected_player_count)
        self._configure_board_metrics()
        self.buttons = self._build_buttons()
        self._reset_history()
        self.notice = ""
        self.mode = "move"
        self.selected_pawn = False
        self.legal_moves = []

    def _set_mode(self, mode: str) -> None:
        self.mode = mode
        self.selected_pawn = False
        self.legal_moves = []

    def _reset_history(self) -> None:
        self.history = [self.game.snapshot()]
        self.history_index = 0

    def _record_current_state(self) -> None:
        self.history = self.history[: self.history_index + 1]
        self.history.append(self.game.snapshot())
        self.history_index += 1

    def _save_game(self) -> None:
        payload = {
            "version": 1,
            "play_against_computer": self.play_against_computer,
            "computer_difficulty": self.computer_difficulty,
            "player_count": len(self.game.players),
            "snapshot": self._snapshot_to_data(self.game.snapshot()),
        }
        try:
            SAVE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError:
            self.notice = "Could not save game"
            return

        self.notice = f"Game saved to {SAVE_FILE.name}"

    def _load_game(self) -> None:
        if not SAVE_FILE.exists():
            self.notice = "No saved game found"
            return

        try:
            data = json.loads(SAVE_FILE.read_text(encoding="utf-8"))
            snapshot = self._snapshot_from_data(data.get("snapshot"))
            play_against_computer = bool(data.get("play_against_computer", False))
            computer_difficulty = data.get("computer_difficulty")
            if play_against_computer and computer_difficulty not in {"easy", "medium", "hard"}:
                raise ValueError("Saved computer difficulty is invalid")
            if play_against_computer and len(snapshot.players) != 2:
                raise ValueError("Saved computer game must have 2 players")
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            self.notice = "Saved game could not be loaded"
            return

        self.game = QuoridorGame(snapshot.board_size, len(snapshot.players))
        self.game.restore(snapshot)
        self.selected_board_size = snapshot.board_size
        self.selected_player_count = len(snapshot.players)
        self.show_setup = False
        self.play_against_computer = play_against_computer
        self.computer_difficulty = computer_difficulty if play_against_computer else None
        self.selected_opponent = "computer" if play_against_computer else "human"
        self._configure_board_metrics()
        self.buttons = self._build_buttons()
        self._reset_history()
        self.notice = "Loaded saved game"
        self.mode = "move"
        self.selected_pawn = False
        self.legal_moves = []

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

    def _can_undo(self) -> bool:
        return self.history_index > 0

    def _can_redo(self) -> bool:
        return self.history_index < len(self.history) - 1

    def _undo(self) -> None:
        if not self._can_undo():
            return

        steps = 1
        if self.play_against_computer and self.game.current_turn == 0 and self.history_index >= 2:
            steps = 2

        self.history_index = max(0, self.history_index - steps)
        self.game.restore(self.history[self.history_index])
        self._set_mode("move")

    def _redo(self) -> None:
        if not self._can_redo():
            return

        steps = 1
        if (
            self.play_against_computer
            and self.game.current_turn == 0
            and self.history_index + 2 < len(self.history)
        ):
            steps = 2

        self.history_index = min(len(self.history) - 1, self.history_index + steps)
        self.game.restore(self.history[self.history_index])
        self._set_mode("move")

    def _player_two_name(self) -> str:
        if not self.play_against_computer or self.computer_difficulty is None:
            return "Player 2"
        return f"Computer ({self.computer_difficulty.title()})"

    def _is_computer_turn(self) -> bool:
        return self.play_against_computer and self.game.current_turn == 1 and self.game.winner is None

    def _maybe_take_computer_turn(self) -> None:
        if not self._is_computer_turn():
            return

        pygame.time.delay(220)
        action = self._choose_computer_action()
        played = False
        if action[0] == "move":
            played = self.game.move_pawn(action[1])
        else:
            orientation, position = action[1], action[2]
            played = self.game.place_wall(orientation, position)
        if played:
            self._record_current_state()
        self.selected_pawn = False
        self.legal_moves = []
        self.mode = "move"

    def _choose_computer_action(self) -> ComputerAction:
        difficulty = self.computer_difficulty or "easy"
        if difficulty == "easy":
            return self._choose_easy_action()
        if difficulty == "medium":
            return self._choose_medium_action()
        return self._choose_hard_action()

    def _choose_easy_action(self) -> ComputerAction:
        wall = self._best_blocking_wall()
        if wall is not None and random.random() < 0.22:
            return ("wall", wall[0], wall[1])
        if random.random() < 0.85:
            return ("move", self._best_path_move(1))
        return ("move", random.choice(self.game.legal_moves_for_current_player()))

    def _choose_medium_action(self) -> ComputerAction:
        return self._best_immediate_action(wall_limit=8)

    def _choose_hard_action(self) -> ComputerAction:
        actions = self._candidate_actions_for_current_player(wall_limit=8, exhaustive_walls=True)
        if not actions:
            return ("move", random.choice(self.game.legal_moves_for_current_player()))

        best_action = actions[0]
        best_score = -100000.0
        for action in actions:
            snapshot = self.game.snapshot()
            try:
                if not self._apply_action(action):
                    continue
                score = self._minimax(depth=1, alpha=-100000.0, beta=100000.0)
            finally:
                self.game.restore(snapshot)

            if score > best_score:
                best_score = score
                best_action = action

        return best_action

    def _best_path_move(self, player_index: int) -> Position:
        path = self.game.shortest_path_for_player(player_index)
        legal_moves = self.game.legal_moves_for_current_player()
        if len(path) > 1 and path[1] in legal_moves:
            return path[1]
        return random.choice(legal_moves)

    def _best_immediate_action(self, wall_limit: int) -> ComputerAction:
        actions = self._candidate_actions_for_current_player(wall_limit, exhaustive_walls=True)
        if not actions:
            return ("move", random.choice(self.game.legal_moves_for_current_player()))

        return max(actions, key=self._score_action)

    def _candidate_actions_for_current_player(
        self,
        wall_limit: int,
        exhaustive_walls: bool = False,
    ) -> list[ComputerAction]:
        actions: list[ComputerAction] = [("move", move) for move in self.game.legal_moves_for_current_player()]
        actions.extend(
            ("wall", orientation, position)
            for orientation, position, score in self._ranked_wall_candidates_for_current_player(
                wall_limit,
                exhaustive=exhaustive_walls,
            )
            if score > 0
        )
        return actions

    def _best_blocking_wall(self) -> tuple[str, WallPosition] | None:
        walls = self._ranked_wall_candidates_for_current_player(limit=1, exhaustive=False)
        if walls and walls[0][2] > 0:
            return (walls[0][0], walls[0][1])
        return None

    def _ranked_wall_candidates_for_current_player(
        self,
        limit: int,
        exhaustive: bool,
    ) -> list[tuple[str, WallPosition, float]]:
        if self.game.current_player.walls_remaining <= 0:
            return []

        player_index = self.game.current_turn
        opponent_index = 1 - player_index
        player_path = self.game.shortest_path_for_player(player_index)
        opponent_path = self.game.shortest_path_for_player(opponent_index)
        if len(opponent_path) < 2:
            return []

        original_player_length = len(player_path) if player_path else 99
        original_opponent_length = len(opponent_path)
        priority_walls: set[tuple[str, WallPosition]] = set()

        for start, end in zip(opponent_path, opponent_path[1:]):
            priority_walls.update(self._walls_blocking_edge(start, end))

        candidates = list(priority_walls)
        if exhaustive:
            all_walls = [
                (orientation, (row, col))
                for orientation in ("h", "v")
                for row in range(self.board_size - 1)
                for col in range(self.board_size - 1)
            ]
            candidates.extend(wall for wall in all_walls if wall not in priority_walls)
        scored: list[tuple[str, WallPosition, float]] = []

        for orientation, position in candidates:
            is_valid, _ = self.game.wall_is_valid(orientation, position)
            if not is_valid:
                continue

            wall_set = self.game.horizontal_walls if orientation == "h" else self.game.vertical_walls
            wall_set.add(position)
            try:
                player_length = len(self.game.shortest_path_for_player(player_index)) or 99
                opponent_length = len(self.game.shortest_path_for_player(opponent_index)) or 99
            finally:
                wall_set.remove(position)

            score = (opponent_length - original_opponent_length) * 4 - (
                player_length - original_player_length
            ) * 2
            if (orientation, position) in priority_walls:
                score += 0.35
            scored.append((orientation, position, score))

        scored.sort(key=lambda item: item[2], reverse=True)
        return scored[:limit]

    def _score_action(self, action: ComputerAction) -> float:
        snapshot = self.game.snapshot()
        try:
            if not self._apply_action(action):
                return -100000.0
            return self._evaluate_position()
        finally:
            self.game.restore(snapshot)

    def _apply_action(self, action: ComputerAction) -> bool:
        if action[0] == "move":
            return self.game.move_pawn(action[1])
        return self.game.place_wall(action[1], action[2])

    def _minimax(self, depth: int, alpha: float, beta: float) -> float:
        if depth == 0 or self.game.winner is not None:
            return self._evaluate_position()

        actions = self._candidate_actions_for_current_player(wall_limit=4)
        if not actions:
            return self._evaluate_position()

        if self.game.current_turn == 1:
            value = -100000.0
            for action in actions:
                snapshot = self.game.snapshot()
                try:
                    if not self._apply_action(action):
                        continue
                    value = max(value, self._minimax(depth - 1, alpha, beta))
                finally:
                    self.game.restore(snapshot)
                alpha = max(alpha, value)
                if beta <= alpha:
                    break
            return value

        value = 100000.0
        for action in actions:
            snapshot = self.game.snapshot()
            try:
                if not self._apply_action(action):
                    continue
                value = min(value, self._minimax(depth - 1, alpha, beta))
            finally:
                self.game.restore(snapshot)
            beta = min(beta, value)
            if beta <= alpha:
                break
        return value

    def _evaluate_position(self) -> float:
        if self.game.winner == 1:
            return 10000.0
        if self.game.winner == 0:
            return -10000.0

        computer_path = self.game.shortest_path_for_player(1)
        human_path = self.game.shortest_path_for_player(0)
        computer_distance = len(computer_path) - 1 if computer_path else 99
        human_distance = len(human_path) - 1 if human_path else 99
        wall_balance = self.game.players[1].walls_remaining - self.game.players[0].walls_remaining
        turn_bonus = 0.2 if self.game.current_turn == 1 else -0.2
        return (human_distance - computer_distance) * 10 + wall_balance * 0.7 + turn_bonus

    def _walls_blocking_edge(self, start: Position, end: Position) -> list[tuple[str, WallPosition]]:
        start_row, start_col = start
        end_row, end_col = end
        candidates: list[tuple[str, WallPosition]] = []

        if start_row == end_row:
            row = start_row
            col = min(start_col, end_col)
            candidates.extend([("v", (row, col)), ("v", (row - 1, col))])
        else:
            row = min(start_row, end_row)
            col = start_col
            candidates.extend([("h", (row, col)), ("h", (row, col - 1))])

        return [
            (orientation, position)
            for orientation, position in candidates
            if 0 <= position[0] < self.board_size - 1 and 0 <= position[1] < self.board_size - 1
        ]

    def _draw(self) -> None:
        self.screen.fill(BACKGROUND)
        if self.show_setup:
            self._draw_setup()
            return

        self._draw_board_frame()
        self._draw_cells()
        self._draw_move_hints()
        self._draw_walls()
        self._draw_wall_preview()
        self._draw_pawns()
        self._draw_panel()

    def _draw_setup(self) -> None:
        title = self.title_font.render("Quoridor", True, TEXT_PRIMARY)
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, 96))
        self.screen.blit(title, title_rect)

        size_prompt = self.body_font.render("Choose board size", True, TEXT_PRIMARY)
        size_prompt_rect = size_prompt.get_rect(center=(WINDOW_WIDTH // 2, 136))
        self.screen.blit(size_prompt, size_prompt_rect)

        for board_size in BOARD_SIZE_OPTIONS:
            self._draw_setup_button(
                f"size_{board_size}",
                f"{board_size}x{board_size}",
                self.selected_board_size == board_size,
            )

        opponent_prompt = self.body_font.render("Choose your opponent", True, TEXT_PRIMARY)
        opponent_rect = opponent_prompt.get_rect(center=(WINDOW_WIDTH // 2, 248))
        self.screen.blit(opponent_prompt, opponent_rect)

        self._draw_setup_button("human", "Human", self.selected_opponent == "human")
        self._draw_setup_button("computer", "Computer", self.selected_opponent == "computer")

        if self.selected_opponent == "human":
            player_prompt = self.small_font.render("Choose players", True, TEXT_MUTED)
            player_rect = player_prompt.get_rect(center=(WINDOW_WIDTH // 2, 362))
            self.screen.blit(player_prompt, player_rect)
            self._draw_setup_button("players_2", "2 Players", False)
            self._draw_setup_button("players_4", "4 Players", False)
        elif self.selected_opponent == "computer":
            difficulty_prompt = self.small_font.render("Choose difficulty", True, TEXT_MUTED)
            difficulty_rect = difficulty_prompt.get_rect(center=(WINDOW_WIDTH // 2, 362))
            self.screen.blit(difficulty_prompt, difficulty_rect)
            self._draw_setup_button("easy", "Easy", False)
            self._draw_setup_button("medium", "Medium", False)
            self._draw_setup_button("hard", "Hard", False)

        self._draw_setup_button("load", "Load Saved Game", False)
        if self.notice:
            notice = self.small_font.render(self.notice, True, TEXT_MUTED)
            notice_rect = notice.get_rect(center=(WINDOW_WIDTH // 2, 552))
            self.screen.blit(notice, notice_rect)

    def _draw_setup_button(self, name: str, label: str, active: bool) -> None:
        rect = self.setup_buttons[name]
        color = BUTTON_ACTIVE if active else BUTTON_IDLE
        pygame.draw.rect(self.screen, color, rect, border_radius=10)
        text = self.body_font.render(label, True, TEXT_PRIMARY)
        text_rect = text.get_rect(center=rect.center)
        self.screen.blit(text, text_rect)

    def _draw_board_frame(self) -> None:
        frame_rect = pygame.Rect(BOARD_LEFT - 8, BOARD_TOP - 8, self.board_pixels + 16, self.board_pixels + 16)
        pygame.draw.rect(self.screen, BOARD_FRAME, frame_rect, border_radius=14)

    def _draw_cells(self) -> None:
        for row in range(self.board_size):
            for col in range(self.board_size):
                rect = self._cell_rect(row, col)
                pygame.draw.rect(self.screen, GRID_GAP, rect.inflate(GAP_SIZE, GAP_SIZE), border_radius=8)
                color = CELL_LIGHT if (row + col) % 2 == 0 else CELL_DARK
                pygame.draw.rect(self.screen, color, rect, border_radius=7)

    def _draw_move_hints(self) -> None:
        if not self.selected_pawn:
            return

        for row, col in self.legal_moves:
            center = self._cell_rect(row, col).center
            pygame.draw.circle(self.screen, MOVE_HINT, center, 8)

    def _draw_walls(self) -> None:
        for row, col in self.game.horizontal_walls:
            pygame.draw.rect(self.screen, WALL_COLOR, self._horizontal_wall_rect(row, col), border_radius=5)
        for row, col in self.game.vertical_walls:
            pygame.draw.rect(self.screen, WALL_COLOR, self._vertical_wall_rect(row, col), border_radius=5)

    def _draw_wall_preview(self) -> None:
        if self.mode not in {"wall_h", "wall_v"} or self.game.winner is not None:
            return

        mouse_pos = pygame.mouse.get_pos()
        orientation = "h" if self.mode == "wall_h" else "v"
        slot = self._wall_slot_at(mouse_pos, orientation)
        if slot is None:
            return

        is_valid, _ = self.game.wall_is_valid(orientation, slot)
        color = VALID_PREVIEW if is_valid else INVALID_PREVIEW
        rect = self._horizontal_wall_rect(*slot) if orientation == "h" else self._vertical_wall_rect(*slot)
        preview = pygame.Surface(rect.size, pygame.SRCALPHA)
        preview.fill((*color, 150))
        self.screen.blit(preview, rect.topleft)

    def _draw_pawns(self) -> None:
        player_colors = (PLAYER_ONE, PLAYER_TWO, PLAYER_THREE, PLAYER_FOUR)
        for index, player in enumerate(self.game.players):
            row, col = player.pawn
            rect = self._cell_rect(row, col)
            center = rect.center
            radius = self.cell_size // 2 - 7
            fill = player_colors[index]
            pygame.draw.circle(self.screen, fill, center, radius)
            pygame.draw.circle(self.screen, PLAYER_RING, center, radius, width=4)
            label = self.body_font.render(str(index + 1), True, PLAYER_RING)
            label_rect = label.get_rect(center=center)
            self.screen.blit(label, label_rect)

            if index == self.game.current_turn and self.game.winner is None:
                halo_radius = radius + 5
                pygame.draw.circle(self.screen, PLAYER_RING, center, halo_radius, width=2)

    def _draw_panel(self) -> None:
        title = self.title_font.render("Quoridor", True, TEXT_PRIMARY)
        self.screen.blit(title, (BOARD_LEFT, self.panel_top))

        status = self.small_font.render(self.game.status, True, TEXT_PRIMARY)
        self.screen.blit(status, (BOARD_LEFT, self.panel_top + 36))

        info_x = BOARD_LEFT + 295
        info_y = self.panel_top + 8
        for index, player in enumerate(self.game.players):
            row_offset = (index % 2) * 24
            col_offset = (index // 2) * 160
            wall_text = self.small_font.render(
                f"P{index + 1} walls: {player.walls_remaining}",
                True,
                PLAYER_RING,
            )
            self.screen.blit(wall_text, (info_x + col_offset, info_y + row_offset))

        turn_text = "Game over" if self.game.winner is not None else f"Turn: {self.game.current_player.name}"
        turn_surface = self.body_font.render(turn_text, True, TEXT_PRIMARY)
        self.screen.blit(turn_surface, (BOARD_LEFT, self.panel_top + 60))

        self._draw_button("move", "Move", self.mode == "move")
        self._draw_button("wall_h", "Wall H", self.mode == "wall_h")
        self._draw_button("wall_v", "Wall V", self.mode == "wall_v")
        self._draw_button("undo", "Undo", False)
        self._draw_button("redo", "Redo", False)
        self._draw_button("reset", "Reset", False)
        self._draw_button("save", "Save", False)
        self._draw_button("menu", "Menu", False)

        if self.notice:
            notice = self.small_font.render(self.notice, True, TEXT_MUTED)
            self.screen.blit(notice, (BOARD_LEFT, self.panel_top + 136))

        hint = self.small_font.render("Keys: M/H/V modes, U undo, Y redo, R reset, Ctrl+S save", True, TEXT_MUTED)
        self.screen.blit(hint, (BOARD_LEFT, self.panel_top + 158))

    def _draw_button(self, name: str, label: str, active: bool) -> None:
        rect = self.buttons[name]
        color = BUTTON_ACTIVE if active else BUTTON_IDLE
        if name.startswith("wall") and self.game.current_player.walls_remaining == 0:
            color = BUTTON_DISABLED
        if name == "undo" and not self._can_undo():
            color = BUTTON_DISABLED
        if name == "redo" and not self._can_redo():
            color = BUTTON_DISABLED
        pygame.draw.rect(self.screen, color, rect, border_radius=10)
        text = self.small_font.render(label, True, TEXT_PRIMARY)
        text_rect = text.get_rect(center=rect.center)
        self.screen.blit(text, text_rect)

    def _cell_rect(self, row: int, col: int) -> pygame.Rect:
        x_pos = BOARD_LEFT + col * (self.cell_size + GAP_SIZE)
        y_pos = BOARD_TOP + row * (self.cell_size + GAP_SIZE)
        return pygame.Rect(x_pos, y_pos, self.cell_size, self.cell_size)

    def _horizontal_wall_rect(self, row: int, col: int) -> pygame.Rect:
        left = self._cell_rect(row, col).left
        top = self._cell_rect(row, col).bottom
        width = self.cell_size * 2 + GAP_SIZE
        return pygame.Rect(left, top, width, GAP_SIZE)

    def _vertical_wall_rect(self, row: int, col: int) -> pygame.Rect:
        left = self._cell_rect(row, col).right
        top = self._cell_rect(row, col).top
        height = self.cell_size * 2 + GAP_SIZE
        return pygame.Rect(left, top, GAP_SIZE, height)

    def _cell_at(self, mouse_pos: tuple[int, int]) -> tuple[int, int] | None:
        for row in range(self.board_size):
            for col in range(self.board_size):
                if self._cell_rect(row, col).collidepoint(mouse_pos):
                    return (row, col)
        return None

    def _wall_slot_at(self, mouse_pos: tuple[int, int], orientation: str) -> tuple[int, int] | None:
        for row in range(self.board_size - 1):
            for col in range(self.board_size - 1):
                rect = self._horizontal_wall_rect(row, col) if orientation == "h" else self._vertical_wall_rect(row, col)
                if rect.collidepoint(mouse_pos):
                    return (row, col)
        return None
