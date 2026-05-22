"""
Pygame rendering for Quoridor setup and in-game screens.

``QuoridorRenderer`` draws everything the user sees: main menu, checkerboard,
walls, pawns, legal-move hints, wall placement preview, and the bottom control
panel. It does not handle input or rules; ``QuoridorApp`` passes game state and
UI flags into ``draw_setup`` or ``draw_game``.

Drawing order (in-game)
-----------------------
Background → board frame → cells → move hints → placed walls → wall preview
(hover) → pawns → panel (status, wall counts, buttons, notices).

Fonts use system Arial at three sizes. Colors and layout constants come from
``quoridor_game.settings``.
"""

from __future__ import annotations  # Postponed evaluation of annotations

import pygame  # Surfaces, fonts, rects, and drawing primitives

from .engine import Position, QuoridorGame  # Live game state for draw decisions
from .settings import (  # Palette, layout, and geometry type
    BACKGROUND,
    BOARD_FRAME,
    BOARD_LEFT,
    BOARD_SIZE_OPTIONS,
    BOARD_TOP,
    BUTTON_ACTIVE,
    BUTTON_DISABLED,
    BUTTON_IDLE,
    CELL_DARK,
    CELL_LIGHT,
    GRID_GAP,
    GAP_SIZE,
    INVALID_PREVIEW,
    MOVE_HINT,
    PLAYER_FOUR,
    PLAYER_ONE,
    PLAYER_RING,
    PLAYER_THREE,
    PLAYER_TWO,
    TEXT_MUTED,
    TEXT_PRIMARY,
    VALID_PREVIEW,
    WALL_COLOR,
    WINDOW_WIDTH,
    BoardGeometry,
)


class QuoridorRenderer:
    """
    Stateless drawer bound to a Pygame display surface.

    Create once per window; call ``draw_setup`` or ``draw_game`` each frame.
    """

    def __init__(self, screen: pygame.Surface) -> None:
        """
        Store the target surface and create title, body, and small fonts.
        """
        self.screen = screen  # Main window framebuffer to blit into
        self.title_font = pygame.font.SysFont("arial", 28, bold=True)  # Headings
        self.body_font = pygame.font.SysFont("arial", 20, bold=True)  # Buttons and turn line
        self.small_font = pygame.font.SysFont("arial", 17)  # Hints, status, wall counts

    def draw_setup(
        self,
        setup_buttons: dict[str, pygame.Rect],
        selected_board_size: int,
        selected_opponent: str | None,
        notice: str,
    ) -> None:
        """
        Render the main menu: title, board size, opponent, follow-up choices, load.

        ``selected_board_size`` highlights the active size tile. When opponent is
        human, shows 2/4 player buttons; when computer, shows difficulty buttons.
        ``notice`` is centered near the bottom (save/load messages).
        """
        self.screen.fill(BACKGROUND)  # Clear frame to dark background
        title = self.title_font.render("Quoridor", True, TEXT_PRIMARY)  # Antialiased title text
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, 96))  # Centered near top
        self.screen.blit(title, title_rect)

        size_prompt = self.body_font.render("Choose board size", True, TEXT_PRIMARY)
        size_prompt_rect = size_prompt.get_rect(center=(WINDOW_WIDTH // 2, 136))
        self.screen.blit(size_prompt, size_prompt_rect)

        for board_size in BOARD_SIZE_OPTIONS:  # Draw 7, 9, and 11 size buttons
            self._draw_setup_button(
                setup_buttons,
                f"size_{board_size}",
                f"{board_size}x{board_size}",
                selected_board_size == board_size,  # Highlight current selection
            )

        opponent_prompt = self.body_font.render("Choose your opponent", True, TEXT_PRIMARY)
        opponent_rect = opponent_prompt.get_rect(center=(WINDOW_WIDTH // 2, 248))
        self.screen.blit(opponent_prompt, opponent_rect)

        self._draw_setup_button(setup_buttons, "human", "Human", selected_opponent == "human")
        self._draw_setup_button(setup_buttons, "computer", "Computer", selected_opponent == "computer")

        if selected_opponent == "human":  # Second-step: local player count
            player_prompt = self.small_font.render("Choose players", True, TEXT_MUTED)
            player_rect = player_prompt.get_rect(center=(WINDOW_WIDTH // 2, 362))
            self.screen.blit(player_prompt, player_rect)
            self._draw_setup_button(setup_buttons, "players_2", "2 Players", False)
            self._draw_setup_button(setup_buttons, "players_4", "4 Players", False)
        elif selected_opponent == "computer":  # Second-step: AI difficulty
            difficulty_prompt = self.small_font.render("Choose difficulty", True, TEXT_MUTED)
            difficulty_rect = difficulty_prompt.get_rect(center=(WINDOW_WIDTH // 2, 362))
            self.screen.blit(difficulty_prompt, difficulty_rect)
            self._draw_setup_button(setup_buttons, "easy", "Easy", False)
            self._draw_setup_button(setup_buttons, "medium", "Medium", False)
            self._draw_setup_button(setup_buttons, "hard", "Hard", False)

        self._draw_setup_button(setup_buttons, "load", "Load Saved Game", False)
        if notice:  # Optional banner from app (load error, success, etc.)
            notice_surface = self.small_font.render(notice, True, TEXT_MUTED)
            notice_rect = notice_surface.get_rect(center=(WINDOW_WIDTH // 2, 552))
            self.screen.blit(notice_surface, notice_rect)

    def draw_game(
        self,
        game: QuoridorGame,
        geometry: BoardGeometry,
        buttons: dict[str, pygame.Rect],
        mode: str,
        selected_pawn: bool,
        legal_moves: list[Position],
        notice: str,
        can_undo: bool,
        can_redo: bool,
    ) -> None:
        """
        Render a full in-game frame: board, pieces, hints, preview, and panel.

        ``mode`` controls wall preview orientation. ``selected_pawn`` and
        ``legal_moves`` drive green destination dots. Button states reflect undo/redo.
        """
        self.screen.fill(BACKGROUND)
        self._draw_board_frame(geometry)
        self._draw_cells(geometry)
        self._draw_move_hints(geometry, selected_pawn, legal_moves)
        self._draw_walls(game, geometry)
        self._draw_wall_preview(game, geometry, mode)
        self._draw_pawns(game, geometry)
        self._draw_panel(game, geometry, buttons, mode, notice, can_undo, can_redo)

    def _draw_setup_button(
        self,
        setup_buttons: dict[str, pygame.Rect],
        name: str,
        label: str,
        active: bool,
    ) -> None:
        """
        Draw one setup menu button with optional selected (active) styling.
        """
        rect = setup_buttons[name]  # Precomputed hit/draw rectangle
        color = BUTTON_ACTIVE if active else BUTTON_IDLE
        pygame.draw.rect(self.screen, color, rect, border_radius=10)
        text = self.body_font.render(label, True, TEXT_PRIMARY)
        text_rect = text.get_rect(center=rect.center)
        self.screen.blit(text, text_rect)

    def _draw_board_frame(self, geometry: BoardGeometry) -> None:
        """
        Draw a rounded rectangle frame around the entire grid area.
        """
        frame_rect = pygame.Rect(BOARD_LEFT - 8, BOARD_TOP - 8, geometry.board_pixels + 16, geometry.board_pixels + 16)
        pygame.draw.rect(self.screen, BOARD_FRAME, frame_rect, border_radius=14)

    def _draw_cells(self, geometry: BoardGeometry) -> None:
        """
        Draw checkerboard cells and gap gutters between them.
        """
        for row in range(geometry.board_size):
            for col in range(geometry.board_size):
                rect = geometry.cell_rect(row, col)
                pygame.draw.rect(self.screen, GRID_GAP, rect.inflate(GAP_SIZE, GAP_SIZE), border_radius=8)  # Gap under cell
                color = CELL_LIGHT if (row + col) % 2 == 0 else CELL_DARK  # Checker pattern
                pygame.draw.rect(self.screen, color, rect, border_radius=7)

    def _draw_move_hints(
        self,
        geometry: BoardGeometry,
        selected_pawn: bool,
        legal_moves: list[Position],
    ) -> None:
        """
        Draw green circles on legal destination cells when a pawn is selected.
        """
        if not selected_pawn:  # No hints until first click on own pawn
            return

        for row, col in legal_moves:
            center = geometry.cell_rect(row, col).center
            pygame.draw.circle(self.screen, MOVE_HINT, center, 8)

    def _draw_walls(self, game: QuoridorGame, geometry: BoardGeometry) -> None:
        """
        Draw all placed horizontal and vertical wall segments on the board.
        """
        for row, col in game.horizontal_walls:
            pygame.draw.rect(self.screen, WALL_COLOR, geometry.horizontal_wall_rect(row, col), border_radius=5)
        for row, col in game.vertical_walls:
            pygame.draw.rect(self.screen, WALL_COLOR, geometry.vertical_wall_rect(row, col), border_radius=5)

    def _draw_wall_preview(self, game: QuoridorGame, geometry: BoardGeometry, mode: str) -> None:
        """
        Draw a semi-transparent wall preview at the mouse slot in wall mode.

        Green if ``wall_is_valid`` passes, red otherwise. Hidden when game over
        or not in wall_h / wall_v mode.
        """
        if mode not in {"wall_h", "wall_v"} or game.winner is not None:
            return

        mouse_pos = pygame.mouse.get_pos()  # Current cursor for hover feedback
        orientation = "h" if mode == "wall_h" else "v"
        slot = geometry.wall_slot_at(mouse_pos, orientation)
        if slot is None:
            return

        is_valid, _ = game.wall_is_valid(orientation, slot)  # Ask engine without placing
        color = VALID_PREVIEW if is_valid else INVALID_PREVIEW
        rect = geometry.horizontal_wall_rect(*slot) if orientation == "h" else geometry.vertical_wall_rect(*slot)
        preview = pygame.Surface(rect.size, pygame.SRCALPHA)  # Per-pixel alpha surface
        preview.fill((*color, 150))  # 150/255 opacity
        self.screen.blit(preview, rect.topleft)

    def _draw_pawns(self, game: QuoridorGame, geometry: BoardGeometry) -> None:
        """
        Draw each player's pawn as a numbered circle with a turn halo on active player.
        """
        player_colors = (PLAYER_ONE, PLAYER_TWO, PLAYER_THREE, PLAYER_FOUR)
        for index, player in enumerate(game.players):
            row, col = player.pawn
            rect = geometry.cell_rect(row, col)
            center = rect.center
            radius = geometry.cell_size // 2 - 7  # Inset so pawn fits inside cell
            fill = player_colors[index]
            pygame.draw.circle(self.screen, fill, center, radius)
            pygame.draw.circle(self.screen, PLAYER_RING, center, radius, width=4)  # Outer ring
            label = self.body_font.render(str(index + 1), True, PLAYER_RING)  # 1-based player number
            label_rect = label.get_rect(center=center)
            self.screen.blit(label, label_rect)

            if index == game.current_turn and game.winner is None:  # Highlight whose turn it is
                halo_radius = radius + 5
                pygame.draw.circle(self.screen, PLAYER_RING, center, halo_radius, width=2)

    def _draw_panel(
        self,
        game: QuoridorGame,
        geometry: BoardGeometry,
        buttons: dict[str, pygame.Rect],
        mode: str,
        notice: str,
        can_undo: bool,
        can_redo: bool,
    ) -> None:
        """
        Draw the bottom UI: title, status, wall counts, turn, buttons, hints.
        """
        title = self.title_font.render("Quoridor", True, TEXT_PRIMARY)
        self.screen.blit(title, (BOARD_LEFT, geometry.panel_top))

        status = self.small_font.render(game.status, True, TEXT_PRIMARY)  # Engine status message
        self.screen.blit(status, (BOARD_LEFT, geometry.panel_top + 36))

        info_x = BOARD_LEFT + 295  # Right side: per-player wall counts
        info_y = geometry.panel_top + 8
        for index, player in enumerate(game.players):
            row_offset = (index % 2) * 24  # Two rows for up to four players
            col_offset = (index // 2) * 160  # Two columns of labels
            wall_text = self.small_font.render(
                f"P{index + 1} walls: {player.walls_remaining}",
                True,
                PLAYER_RING,
            )
            self.screen.blit(wall_text, (info_x + col_offset, info_y + row_offset))

        turn_text = "Game over" if game.winner is not None else f"Turn: {game.current_player.name}"
        turn_surface = self.body_font.render(turn_text, True, TEXT_PRIMARY)
        self.screen.blit(turn_surface, (BOARD_LEFT, geometry.panel_top + 60))

        self._draw_game_button(game, buttons, "move", "Move", mode == "move", can_undo, can_redo)
        self._draw_game_button(game, buttons, "wall_h", "Wall H", mode == "wall_h", can_undo, can_redo)
        self._draw_game_button(game, buttons, "wall_v", "Wall V", mode == "wall_v", can_undo, can_redo)
        self._draw_game_button(game, buttons, "undo", "Undo", False, can_undo, can_redo)
        self._draw_game_button(game, buttons, "redo", "Redo", False, can_undo, can_redo)
        self._draw_game_button(game, buttons, "reset", "Reset", False, can_undo, can_redo)
        self._draw_game_button(game, buttons, "save", "Save", False, can_undo, can_redo)
        self._draw_game_button(game, buttons, "menu", "Menu", False, can_undo, can_redo)

        if notice:  # Save/load feedback from app
            notice_surface = self.small_font.render(notice, True, TEXT_MUTED)
            self.screen.blit(notice_surface, (BOARD_LEFT, geometry.panel_top + 136))

        hint = self.small_font.render("Keys: M/H/V modes, U undo, Y redo, R reset, Ctrl+S save", True, TEXT_MUTED)
        self.screen.blit(hint, (BOARD_LEFT, geometry.panel_top + 158))

    def _draw_game_button(
        self,
        game: QuoridorGame,
        buttons: dict[str, pygame.Rect],
        name: str,
        label: str,
        active: bool,
        can_undo: bool,
        can_redo: bool,
    ) -> None:
        """
        Draw one in-game panel button with active/disabled coloring rules.

        Wall buttons disable when no walls remain; undo/redo use ``can_*`` flags.
        """
        rect = buttons[name]
        color = BUTTON_ACTIVE if active else BUTTON_IDLE
        if name.startswith("wall") and game.current_player.walls_remaining == 0:
            color = BUTTON_DISABLED
        if name == "undo" and not can_undo:
            color = BUTTON_DISABLED
        if name == "redo" and not can_redo:
            color = BUTTON_DISABLED
        pygame.draw.rect(self.screen, color, rect, border_radius=10)
        text = self.small_font.render(label, True, TEXT_PRIMARY)
        text_rect = text.get_rect(center=rect.center)
        self.screen.blit(text, text_rect)
