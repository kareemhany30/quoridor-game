from __future__ import annotations

import sys

import pygame

from .computer import ComputerPlayer
from .engine import DEFAULT_BOARD_SIZE, DEFAULT_PLAYER_COUNT, Position, QuoridorGame
from .history import GameHistory
from .renderer import QuoridorRenderer
from .save_manager import SaveManager
from .settings import (
    BOARD_SIZE_OPTIONS,
    FPS,
    LEGACY_SAVE_FILES,
    SAVE_FILE,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    BoardGeometry,
    build_game_buttons,
    build_setup_buttons,
)


class QuoridorApp:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Quoridor")

        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.renderer = QuoridorRenderer(self.screen)
        self.save_manager = SaveManager(SAVE_FILE, LEGACY_SAVE_FILES)
        self.computer = ComputerPlayer()

        self.selected_board_size = DEFAULT_BOARD_SIZE
        self.selected_player_count = DEFAULT_PLAYER_COUNT
        self.selected_opponent: str | None = None
        self.play_against_computer = False
        self.computer_difficulty: str | None = None
        self.show_setup = True
        self.notice = ""

        self.game = QuoridorGame(self.selected_board_size, self.selected_player_count)
        self.geometry = BoardGeometry(self.game.board_size)
        self.buttons = build_game_buttons(self.geometry.panel_top)
        self.setup_buttons = build_setup_buttons()
        self.history = GameHistory(self.game)

        self.mode = "move"
        self.selected_pawn = False
        self.legal_moves: list[Position] = []

    def run(self) -> None:
        while True:
            self._handle_events()
            self._maybe_take_computer_turn()
            self._draw()
            pygame.display.flip()
            self.clock.tick(FPS)

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

        clicked_button = self._clicked_game_button(mouse_pos)
        if clicked_button is not None:
            self._handle_game_button(clicked_button)
            return

        if self._is_computer_turn():
            return

        if self.mode == "move":
            self._handle_move_click(mouse_pos)
            return

        if self.mode in {"wall_h", "wall_v"}:
            self._handle_wall_click(mouse_pos)

    def _clicked_game_button(self, mouse_pos: tuple[int, int]) -> str | None:
        for name, rect in self.buttons.items():
            if rect.collidepoint(mouse_pos):
                return name
        return None

    def _handle_game_button(self, name: str) -> None:
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
        elif not self._is_computer_turn():
            self._set_mode(name)

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
            self._handle_human_setup_choice(mouse_pos)
        elif self.selected_opponent == "computer":
            self._handle_computer_setup_choice(mouse_pos)

    def _handle_human_setup_choice(self, mouse_pos: tuple[int, int]) -> None:
        for player_count in (2, 4):
            if self.setup_buttons[f"players_{player_count}"].collidepoint(mouse_pos):
                self._start_match(play_against_computer=False, player_count=player_count)
                return

    def _handle_computer_setup_choice(self, mouse_pos: tuple[int, int]) -> None:
        for difficulty in ("easy", "medium", "hard"):
            if self.setup_buttons[difficulty].collidepoint(mouse_pos):
                self._start_match(play_against_computer=True, difficulty=difficulty, player_count=2)
                return

    def _handle_move_click(self, mouse_pos: tuple[int, int]) -> None:
        if self.game.winner is not None:
            return

        cell = self.geometry.cell_at(mouse_pos)
        if cell is None:
            self._clear_selection()
            return

        if not self.selected_pawn:
            self._select_pawn_if_current_player(cell)
            return

        if cell == self.game.current_player.pawn:
            self._clear_selection()
            return

        if self.game.move_pawn(cell):
            self._after_player_action()
        else:
            self._clear_selection()

    def _select_pawn_if_current_player(self, cell: Position) -> None:
        if cell != self.game.current_player.pawn:
            return

        self.selected_pawn = True
        self.legal_moves = self.game.legal_moves_for_current_player()

    def _handle_wall_click(self, mouse_pos: tuple[int, int]) -> None:
        orientation = "h" if self.mode == "wall_h" else "v"
        slot = self.geometry.wall_slot_at(mouse_pos, orientation)
        if slot is not None and self.game.place_wall(orientation, slot):
            self._after_player_action()

    def _after_player_action(self) -> None:
        self.history.record(self.game)
        self._clear_selection()

    def _reset_game(self) -> None:
        self.game.reset()
        self.game.players[1].name = self._player_two_name()
        self._refresh_board_layout()
        self.history.reset(self.game)
        self._reset_play_state()
        self.notice = ""

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
        self._refresh_board_layout()
        self.history.reset(self.game)
        self._reset_play_state()
        self.notice = ""

    def _return_to_menu(self) -> None:
        self.show_setup = True
        self.selected_opponent = None
        self.play_against_computer = False
        self.computer_difficulty = None
        self.game = QuoridorGame(self.selected_board_size, self.selected_player_count)
        self._refresh_board_layout()
        self.history.reset(self.game)
        self._reset_play_state()
        self.notice = ""

    def _refresh_board_layout(self) -> None:
        self.geometry.update(self.game.board_size)
        self.buttons = build_game_buttons(self.geometry.panel_top)

    def _reset_play_state(self) -> None:
        self.mode = "move"
        self._clear_selection()

    def _set_mode(self, mode: str) -> None:
        self.mode = mode
        self._clear_selection()

    def _clear_selection(self) -> None:
        self.selected_pawn = False
        self.legal_moves = []

    def _save_game(self) -> None:
        try:
            self.save_manager.save(
                self.game.snapshot(),
                self.play_against_computer,
                self.computer_difficulty,
            )
        except OSError:
            self.notice = "Could not save game"
            return

        self.notice = f"Game saved to {SAVE_FILE.name}"

    def _load_game(self) -> None:
        if not self.save_manager.exists():
            self.notice = "No saved game found"
            return

        try:
            loaded_game = self.save_manager.load()
        except (OSError, TypeError, ValueError):
            self.notice = "Saved game could not be loaded"
            return

        snapshot = loaded_game.snapshot
        self.game = QuoridorGame(snapshot.board_size, len(snapshot.players))
        self.game.restore(snapshot)
        self.selected_board_size = snapshot.board_size
        self.selected_player_count = len(snapshot.players)
        self.show_setup = False
        self.play_against_computer = loaded_game.play_against_computer
        self.computer_difficulty = loaded_game.computer_difficulty
        self.selected_opponent = "computer" if self.play_against_computer else "human"
        self._refresh_board_layout()
        self.history.reset(self.game)
        self._reset_play_state()
        self.notice = "Loaded saved game"

    def _can_undo(self) -> bool:
        return self.history.can_undo()

    def _can_redo(self) -> bool:
        return self.history.can_redo()

    def _undo(self) -> None:
        skip_computer_reply = self.play_against_computer and self.game.current_turn == 0
        if self.history.undo(self.game, skip_computer_reply):
            self._set_mode("move")

    def _redo(self) -> None:
        skip_computer_reply = self.play_against_computer and self.game.current_turn == 0
        if self.history.redo(self.game, skip_computer_reply):
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
        action = self.computer.choose_action(self.game, self.computer_difficulty)
        played = False
        if action[0] == "move":
            played = self.game.move_pawn(action[1])
        else:
            orientation, position = action[1], action[2]
            played = self.game.place_wall(orientation, position)

        if played:
            self.history.record(self.game)
        self._reset_play_state()

    def _draw(self) -> None:
        if self.show_setup:
            self.renderer.draw_setup(
                self.setup_buttons,
                self.selected_board_size,
                self.selected_opponent,
                self.notice,
            )
            return

        self.renderer.draw_game(
            self.game,
            self.geometry,
            self.buttons,
            self.mode,
            self.selected_pawn,
            self.legal_moves,
            self.notice,
            self._can_undo(),
            self._can_redo(),
        )
