from __future__ import annotations

import random
import sys

import pygame

from .engine import BOARD_SIZE, Position, QuoridorGame, WallPosition


WINDOW_WIDTH = 700
WINDOW_HEIGHT = 700
BOARD_LEFT = 28
BOARD_TOP = 22
CELL_SIZE = 46
GAP_SIZE = 8
BOARD_PIXELS = BOARD_SIZE * CELL_SIZE + (BOARD_SIZE - 1) * GAP_SIZE
PANEL_TOP = BOARD_TOP + BOARD_PIXELS + 18
FPS = 60

BACKGROUND = (24, 31, 38)
BOARD_FRAME = (203, 177, 124)
CELL_LIGHT = (245, 232, 198)
CELL_DARK = (225, 208, 168)
GRID_GAP = (169, 142, 92)
PLAYER_ONE = (47, 95, 168)
PLAYER_TWO = (182, 72, 54)
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


class QuoridorApp:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Quoridor")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.game = QuoridorGame()
        self.show_setup = True
        self.play_against_computer = False
        self.computer_difficulty: str | None = None
        self.selected_opponent: str | None = None
        self.mode = "move"
        self.selected_pawn = False
        self.legal_moves: list[tuple[int, int]] = []
        self.title_font = pygame.font.SysFont("arial", 28, bold=True)
        self.body_font = pygame.font.SysFont("arial", 20, bold=True)
        self.small_font = pygame.font.SysFont("arial", 17)
        self.buttons = self._build_buttons()
        self.setup_buttons = self._build_setup_buttons()

    def run(self) -> None:
        while True:
            self._handle_events()
            self._maybe_take_computer_turn()
            self._draw()
            pygame.display.flip()
            self.clock.tick(FPS)

    def _build_buttons(self) -> dict[str, pygame.Rect]:
        button_width = 94
        button_height = 38
        start_x = BOARD_LEFT
        start_y = PANEL_TOP + 88
        spacing = 12
        return {
            "move": pygame.Rect(start_x, start_y, button_width, button_height),
            "wall_h": pygame.Rect(start_x + button_width + spacing, start_y, button_width, button_height),
            "wall_v": pygame.Rect(start_x + 2 * (button_width + spacing), start_y, button_width, button_height),
            "reset": pygame.Rect(start_x + 3 * (button_width + spacing), start_y, button_width, button_height),
            "menu": pygame.Rect(start_x + 4 * (button_width + spacing), start_y, button_width, button_height),
        }

    def _build_setup_buttons(self) -> dict[str, pygame.Rect]:
        button_width = 180
        button_height = 44
        center_x = WINDOW_WIDTH // 2
        return {
            "human": pygame.Rect(center_x - button_width - 10, 232, button_width, button_height),
            "computer": pygame.Rect(center_x + 10, 232, button_width, button_height),
            "easy": pygame.Rect(center_x - 270, 330, 160, button_height),
            "medium": pygame.Rect(center_x - 80, 330, 160, button_height),
            "hard": pygame.Rect(center_x + 110, 330, 160, button_height),
        }

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                self._handle_key(event.key)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_click(event.pos)

    def _handle_key(self, key: int) -> None:
        if self.show_setup:
            return

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
                    self.selected_pawn = False
                    self.legal_moves = []

    def _handle_setup_click(self, mouse_pos: tuple[int, int]) -> None:
        if self.setup_buttons["human"].collidepoint(mouse_pos):
            self._start_match(play_against_computer=False)
            return

        if self.setup_buttons["computer"].collidepoint(mouse_pos):
            self.selected_opponent = "computer"
            return

        if self.selected_opponent == "computer":
            for difficulty in ("easy", "medium", "hard"):
                if self.setup_buttons[difficulty].collidepoint(mouse_pos):
                    self._start_match(play_against_computer=True, difficulty=difficulty)
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
        self.mode = "move"
        self.selected_pawn = False
        self.legal_moves = []

    def _start_match(self, play_against_computer: bool, difficulty: str | None = None) -> None:
        self.show_setup = False
        self.play_against_computer = play_against_computer
        self.computer_difficulty = difficulty
        self.game.reset()
        self.game.players[1].name = self._player_two_name()
        self.mode = "move"
        self.selected_pawn = False
        self.legal_moves = []

    def _return_to_menu(self) -> None:
        self.show_setup = True
        self.selected_opponent = None
        self.play_against_computer = False
        self.computer_difficulty = None
        self.game.reset()
        self.mode = "move"
        self.selected_pawn = False
        self.legal_moves = []

    def _set_mode(self, mode: str) -> None:
        self.mode = mode
        self.selected_pawn = False
        self.legal_moves = []

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
        if action[0] == "move":
            self.game.move_pawn(action[1])
        else:
            orientation, position = action[1], action[2]
            self.game.place_wall(orientation, position)
        self.selected_pawn = False
        self.legal_moves = []
        self.mode = "move"

    def _choose_computer_action(self) -> tuple[str, Position] | tuple[str, str, WallPosition]:
        difficulty = self.computer_difficulty or "easy"
        if difficulty == "easy":
            return self._choose_easy_action()
        if difficulty == "medium":
            return ("move", self._best_path_move(1))
        return self._choose_hard_action()

    def _choose_easy_action(self) -> tuple[str, Position] | tuple[str, str, WallPosition]:
        legal_wall = self._random_valid_wall()
        if legal_wall is not None and random.random() < 0.25:
            return ("wall", legal_wall[0], legal_wall[1])
        return ("move", random.choice(self.game.legal_moves_for_current_player()))

    def _choose_hard_action(self) -> tuple[str, Position] | tuple[str, str, WallPosition]:
        wall = self._best_blocking_wall()
        computer_path = self.game.shortest_path_for_player(1)
        human_path = self.game.shortest_path_for_player(0)
        should_wall = (
            wall is not None
            and self.game.current_player.walls_remaining > 0
            and human_path
            and computer_path
            and len(human_path) <= len(computer_path) + 1
        )
        if should_wall:
            return ("wall", wall[0], wall[1])
        return ("move", self._best_path_move(1))

    def _best_path_move(self, player_index: int) -> Position:
        path = self.game.shortest_path_for_player(player_index)
        legal_moves = self.game.legal_moves_for_current_player()
        if len(path) > 1 and path[1] in legal_moves:
            return path[1]
        return random.choice(legal_moves)

    def _random_valid_wall(self) -> tuple[str, WallPosition] | None:
        if self.game.current_player.walls_remaining <= 0:
            return None

        candidates = [
            (orientation, (row, col))
            for orientation in ("h", "v")
            for row in range(BOARD_SIZE - 1)
            for col in range(BOARD_SIZE - 1)
        ]
        random.shuffle(candidates)
        for orientation, position in candidates:
            is_valid, _ = self.game.wall_is_valid(orientation, position)
            if is_valid:
                return (orientation, position)
        return None

    def _best_blocking_wall(self) -> tuple[str, WallPosition] | None:
        if self.game.current_player.walls_remaining <= 0:
            return None

        human_path = self.game.shortest_path_for_player(0)
        if len(human_path) < 2:
            return None

        original_human_length = len(human_path)
        original_computer_length = len(self.game.shortest_path_for_player(1))
        best_wall: tuple[str, WallPosition] | None = None
        best_score = -1000

        for start, end in zip(human_path, human_path[1:]):
            for orientation, position in self._walls_blocking_edge(start, end):
                is_valid, _ = self.game.wall_is_valid(orientation, position)
                if not is_valid:
                    continue

                wall_set = self.game.horizontal_walls if orientation == "h" else self.game.vertical_walls
                wall_set.add(position)
                try:
                    human_length = len(self.game.shortest_path_for_player(0))
                    computer_length = len(self.game.shortest_path_for_player(1))
                finally:
                    wall_set.remove(position)

                score = (human_length - original_human_length) * 3 - (computer_length - original_computer_length)
                if score > best_score:
                    best_score = score
                    best_wall = (orientation, position)

        return best_wall if best_score > 0 else None

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
            if 0 <= position[0] < BOARD_SIZE - 1 and 0 <= position[1] < BOARD_SIZE - 1
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
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, 150))
        self.screen.blit(title, title_rect)

        prompt = self.body_font.render("Choose your opponent", True, TEXT_PRIMARY)
        prompt_rect = prompt.get_rect(center=(WINDOW_WIDTH // 2, 196))
        self.screen.blit(prompt, prompt_rect)

        self._draw_setup_button("human", "Human", self.selected_opponent == "human")
        self._draw_setup_button("computer", "Computer", self.selected_opponent == "computer")

        if self.selected_opponent == "computer":
            difficulty_prompt = self.small_font.render("Choose difficulty", True, TEXT_MUTED)
            difficulty_rect = difficulty_prompt.get_rect(center=(WINDOW_WIDTH // 2, 304))
            self.screen.blit(difficulty_prompt, difficulty_rect)
            self._draw_setup_button("easy", "Easy", False)
            self._draw_setup_button("medium", "Medium", False)
            self._draw_setup_button("hard", "Hard", False)

    def _draw_setup_button(self, name: str, label: str, active: bool) -> None:
        rect = self.setup_buttons[name]
        color = BUTTON_ACTIVE if active else BUTTON_IDLE
        pygame.draw.rect(self.screen, color, rect, border_radius=10)
        text = self.body_font.render(label, True, TEXT_PRIMARY)
        text_rect = text.get_rect(center=rect.center)
        self.screen.blit(text, text_rect)

    def _draw_board_frame(self) -> None:
        frame_rect = pygame.Rect(BOARD_LEFT - 8, BOARD_TOP - 8, BOARD_PIXELS + 16, BOARD_PIXELS + 16)
        pygame.draw.rect(self.screen, BOARD_FRAME, frame_rect, border_radius=14)

    def _draw_cells(self) -> None:
        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
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
        for index, player in enumerate(self.game.players):
            row, col = player.pawn
            rect = self._cell_rect(row, col)
            center = rect.center
            radius = CELL_SIZE // 2 - 7
            fill = PLAYER_ONE if index == 0 else PLAYER_TWO
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
        self.screen.blit(title, (BOARD_LEFT, PANEL_TOP))

        status = self.small_font.render(self.game.status, True, TEXT_PRIMARY)
        self.screen.blit(status, (BOARD_LEFT, PANEL_TOP + 36))

        info_x = BOARD_LEFT + 295
        p1 = self.small_font.render(
            f"Player 1 walls: {self.game.players[0].walls_remaining}",
            True,
            PLAYER_RING,
        )
        p2 = self.small_font.render(
            f"Player 2 walls: {self.game.players[1].walls_remaining}",
            True,
            PLAYER_RING,
        )
        self.screen.blit(p1, (info_x, PANEL_TOP + 8))
        self.screen.blit(p2, (info_x, PANEL_TOP + 32))

        turn_text = "Game over" if self.game.winner is not None else f"Turn: {self.game.current_player.name}"
        turn_surface = self.body_font.render(turn_text, True, TEXT_PRIMARY)
        self.screen.blit(turn_surface, (BOARD_LEFT, PANEL_TOP + 60))

        self._draw_button("move", "Move", self.mode == "move")
        self._draw_button("wall_h", "Wall H", self.mode == "wall_h")
        self._draw_button("wall_v", "Wall V", self.mode == "wall_v")
        self._draw_button("reset", "Reset", False)
        self._draw_button("menu", "Main Menue", False)

        hint = self.small_font.render("Keys: M move, H wall, V wall, R reset", True, TEXT_MUTED)
        self.screen.blit(hint, (BOARD_LEFT, PANEL_TOP + 140))

    def _draw_button(self, name: str, label: str, active: bool) -> None:
        rect = self.buttons[name]
        color = BUTTON_ACTIVE if active else BUTTON_IDLE
        if name.startswith("wall") and self.game.current_player.walls_remaining == 0:
            color = BUTTON_DISABLED
        pygame.draw.rect(self.screen, color, rect, border_radius=10)
        text = self.small_font.render(label, True, TEXT_PRIMARY)
        text_rect = text.get_rect(center=rect.center)
        self.screen.blit(text, text_rect)

    def _cell_rect(self, row: int, col: int) -> pygame.Rect:
        x_pos = BOARD_LEFT + col * (CELL_SIZE + GAP_SIZE)
        y_pos = BOARD_TOP + row * (CELL_SIZE + GAP_SIZE)
        return pygame.Rect(x_pos, y_pos, CELL_SIZE, CELL_SIZE)

    def _horizontal_wall_rect(self, row: int, col: int) -> pygame.Rect:
        left = self._cell_rect(row, col).left
        top = self._cell_rect(row, col).bottom
        width = CELL_SIZE * 2 + GAP_SIZE
        return pygame.Rect(left, top, width, GAP_SIZE)

    def _vertical_wall_rect(self, row: int, col: int) -> pygame.Rect:
        left = self._cell_rect(row, col).right
        top = self._cell_rect(row, col).top
        height = CELL_SIZE * 2 + GAP_SIZE
        return pygame.Rect(left, top, GAP_SIZE, height)

    def _cell_at(self, mouse_pos: tuple[int, int]) -> tuple[int, int] | None:
        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                if self._cell_rect(row, col).collidepoint(mouse_pos):
                    return (row, col)
        return None

    def _wall_slot_at(self, mouse_pos: tuple[int, int], orientation: str) -> tuple[int, int] | None:
        for row in range(BOARD_SIZE - 1):
            for col in range(BOARD_SIZE - 1):
                rect = self._horizontal_wall_rect(row, col) if orientation == "h" else self._vertical_wall_rect(row, col)
                if rect.collidepoint(mouse_pos):
                    return (row, col)
        return None
