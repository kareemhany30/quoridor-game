from __future__ import annotations

import sys

import pygame

from .engine import BOARD_SIZE, QuoridorGame


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
        self.mode = "move"
        self.selected_pawn = False
        self.legal_moves: list[tuple[int, int]] = []
        self.title_font = pygame.font.SysFont("arial", 28, bold=True)
        self.body_font = pygame.font.SysFont("arial", 20, bold=True)
        self.small_font = pygame.font.SysFont("arial", 17)
        self.buttons = self._build_buttons()

    def run(self) -> None:
        while True:
            self._handle_events()
            self._draw()
            pygame.display.flip()
            self.clock.tick(FPS)

    def _build_buttons(self) -> dict[str, pygame.Rect]:
        button_width = 114
        button_height = 38
        start_x = BOARD_LEFT
        start_y = PANEL_TOP + 88
        spacing = 12
        return {
            "move": pygame.Rect(start_x, start_y, button_width, button_height),
            "wall_h": pygame.Rect(start_x + button_width + spacing, start_y, button_width, button_height),
            "wall_v": pygame.Rect(start_x + 2 * (button_width + spacing), start_y, button_width, button_height),
            "reset": pygame.Rect(start_x + 3 * (button_width + spacing), start_y, button_width, button_height),
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
        if key == pygame.K_r:
            self._reset_game()
        elif key == pygame.K_m:
            self._set_mode("move")
        elif key == pygame.K_h:
            self._set_mode("wall_h")
        elif key == pygame.K_v:
            self._set_mode("wall_v")

    def _handle_click(self, mouse_pos: tuple[int, int]) -> None:
        for name, rect in self.buttons.items():
            if rect.collidepoint(mouse_pos):
                if name == "reset":
                    self._reset_game()
                else:
                    self._set_mode(name)
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
        self.mode = "move"
        self.selected_pawn = False
        self.legal_moves = []

    def _set_mode(self, mode: str) -> None:
        self.mode = mode
        self.selected_pawn = False
        self.legal_moves = []

    def _draw(self) -> None:
        self.screen.fill(BACKGROUND)
        self._draw_board_frame()
        self._draw_cells()
        self._draw_move_hints()
        self._draw_walls()
        self._draw_wall_preview()
        self._draw_pawns()
        self._draw_panel()

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
