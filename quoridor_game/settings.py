"""
Shared configuration, layout, and visual constants for Quoridor.

This module centralizes values used across rendering, saving, and the app layer
so UI geometry and file paths stay consistent. It does not depend on the game
engine beyond type aliases for positions and wall slots.

Contents
--------
- Window dimensions and frame rate.
- Board layout: cell sizes per board dimension, gap between cells, panel offset.
- Save directory and legacy save file paths (dev vs frozen executable).
- Color palette for board, players, buttons, and wall previews.
- ``BoardGeometry``: maps between pixel coordinates and grid cells / wall slots.
- ``build_game_buttons`` / ``build_setup_buttons``: precomputed ``pygame.Rect``
  hit areas for menus and the in-game control panel.
- ``ComputerAction`` type alias for AI move tuples.
"""

from __future__ import annotations  # Enable modern type hint syntax without quotes

import os  # Read APPDATA for default save directory on Windows
import sys  # Detect frozen (PyInstaller) builds for legacy save paths
from pathlib import Path  # Cross-platform paths for saves and project root

import pygame  # Rect type and display constants used by geometry helpers

from .engine import Position, WallPosition  # Grid coordinate type aliases


WINDOW_WIDTH = 700  # Fixed Pygame window width in pixels
WINDOW_HEIGHT = 700  # Fixed Pygame window height in pixels
BOARD_LEFT = 28  # X offset of the board grid from the left edge
BOARD_TOP = 22  # Y offset of the board grid from the top edge
GAP_SIZE = 8  # Pixel width/height of gaps between cells (also used for walls)
BOARD_SIZE_OPTIONS = (7, 9, 11)  # Supported square board dimensions
CELL_SIZE_BY_BOARD_SIZE = {  # Cell pixel size chosen so board fits in the window
    7: 60,
    9: 46,
    11: 36,
}
PROJECT_ROOT = Path(__file__).resolve().parent.parent  # Repository root (parent of quoridor_game/)
SAVE_DIR = Path(os.environ.get("APPDATA", Path.home())) / "Quoridor"  # User-writable save folder
SAVE_FILE = SAVE_DIR / "saved_game.json"  # Primary save file path
if getattr(sys, "frozen", False):  # Running as a packaged executable
    EXE_DIR = Path(sys.executable).resolve().parent  # Directory containing the .exe
    LEGACY_SAVE_FILES = (EXE_DIR / "saved_game.json", EXE_DIR.parent / "saved_game.json")
else:  # Running from source during development
    LEGACY_SAVE_FILES = (PROJECT_ROOT / "saved_game.json", PROJECT_ROOT / "dist" / "saved_game.json")
FPS = 60  # Target frames per second for the main loop

BACKGROUND = (24, 31, 38)  # Window background RGB
BOARD_FRAME = (203, 177, 124)  # Decorative border around the grid
CELL_LIGHT = (245, 232, 198)  # Checkerboard light square
CELL_DARK = (225, 208, 168)  # Checkerboard dark square
GRID_GAP = (169, 142, 92)  # Color drawn in cell gaps (under wall slots)
PLAYER_ONE = (47, 95, 168)  # Pawn fill color for player index 0
PLAYER_TWO = (182, 72, 54)  # Pawn fill color for player index 1
PLAYER_THREE = (73, 145, 93)  # Pawn fill color for player index 2 (4-player)
PLAYER_FOUR = (177, 126, 49)  # Pawn fill color for player index 3 (4-player)
PLAYER_RING = (250, 247, 239)  # Outline and pawn number label color
MOVE_HINT = (72, 148, 86)  # Green circles on legal destination cells
TEXT_PRIMARY = (245, 246, 248)  # Main UI text color
TEXT_MUTED = (184, 194, 204)  # Secondary hints and notices
BUTTON_IDLE = (58, 74, 92)  # Default button background
BUTTON_ACTIVE = (92, 126, 162)  # Selected or highlighted button
BUTTON_DISABLED = (82, 83, 86)  # Undo/redo/wall buttons when unavailable
WALL_COLOR = (78, 52, 28)  # Placed wall segments
VALID_PREVIEW = (87, 168, 103)  # Semi-transparent valid wall hover (RGB; alpha added later)
INVALID_PREVIEW = (190, 78, 78)  # Semi-transparent invalid wall hover

ComputerAction = tuple[str, Position] | tuple[str, str, WallPosition]  # ("move", cell) or ("wall", "h"|"v", slot)


class BoardGeometry:
    """
    Convert between screen pixels and board grid coordinates for a given size.

    Recomputed when board size changes via ``update``. Used for hit-testing
    cells, wall slots, and drawing rects aligned to the grid.
    """

    def __init__(self, board_size: int) -> None:
        """
        Initialize geometry for ``board_size`` (7, 9, or 11).

        Delegates to ``update`` to set cell size and panel position.
        """
        self.update(board_size)

    def update(self, board_size: int) -> None:
        """
        Recalculate cell size, total board pixel footprint, and panel Y.

        ``panel_top`` sits below the board so control buttons do not overlap cells.
        """
        self.board_size = board_size  # Number of rows/columns on the grid
        self.cell_size = CELL_SIZE_BY_BOARD_SIZE[board_size]  # Pixel width/height of one cell
        self.board_pixels = board_size * self.cell_size + (board_size - 1) * GAP_SIZE  # Full grid extent
        self.panel_top = BOARD_TOP + self.board_pixels + 18  # Y where bottom UI panel begins

    def cell_rect(self, row: int, col: int) -> pygame.Rect:
        """
        Return the screen rectangle for the cell at ``(row, col)``.

        Accounts for ``BOARD_LEFT``, ``BOARD_TOP``, and inter-cell gaps.
        """
        x_pos = BOARD_LEFT + col * (self.cell_size + GAP_SIZE)  # Column → x
        y_pos = BOARD_TOP + row * (self.cell_size + GAP_SIZE)  # Row → y
        return pygame.Rect(x_pos, y_pos, self.cell_size, self.cell_size)

    def horizontal_wall_rect(self, row: int, col: int) -> pygame.Rect:
        """
        Return the draw/hit rectangle for a horizontal wall between rows.

        Spans two adjacent cells horizontally across the gap below ``(row, col)``.
        """
        left = self.cell_rect(row, col).left  # Align with left edge of cell
        top = self.cell_rect(row, col).bottom  # Sit in the horizontal gap under the cell
        width = self.cell_size * 2 + GAP_SIZE  # Cover two cells plus middle gap
        return pygame.Rect(left, top, width, GAP_SIZE)

    def vertical_wall_rect(self, row: int, col: int) -> pygame.Rect:
        """
        Return the draw/hit rectangle for a vertical wall between columns.

        Spans two adjacent cells vertically across the gap right of ``(row, col)``.
        """
        left = self.cell_rect(row, col).right  # Sit in the vertical gap to the right
        top = self.cell_rect(row, col).top
        height = self.cell_size * 2 + GAP_SIZE  # Cover two cells plus middle gap
        return pygame.Rect(left, top, GAP_SIZE, height)

    def cell_at(self, mouse_pos: tuple[int, int]) -> Position | None:
        """
        Map a mouse position to board cell ``(row, col)`` or None if off-grid.

        Linear scan over all cells; board sizes are small so cost is negligible.
        """
        for row in range(self.board_size):
            for col in range(self.board_size):
                if self.cell_rect(row, col).collidepoint(mouse_pos):
                    return (row, col)
        return None

    def wall_slot_at(self, mouse_pos: tuple[int, int], orientation: str) -> WallPosition | None:
        """
        Map a mouse position to a wall slot ``(row, col)`` for orientation ``h`` or ``v``.

        Tests every legal wall rectangle for the given orientation.
        """
        for row in range(self.board_size - 1):
            for col in range(self.board_size - 1):
                rect = (
                    self.horizontal_wall_rect(row, col)
                    if orientation == "h"
                    else self.vertical_wall_rect(row, col)
                )
                if rect.collidepoint(mouse_pos):
                    return (row, col)
        return None


def build_game_buttons(panel_top: int) -> dict[str, pygame.Rect]:
    """
    Build hit rectangles for in-game panel buttons at the given ``panel_top``.

    Returns a dict keyed by button name: move, wall_h, wall_v, undo, redo,
    reset, save, menu. Layout is a single horizontal row.
    """
    button_width = 74  # Uniform button width in pixels
    button_height = 38
    start_x = BOARD_LEFT  # Left-align with the board
    start_y = panel_top + 88  # Vertical offset within the panel area
    spacing = 6  # Gap between adjacent buttons
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


def build_setup_buttons() -> dict[str, pygame.Rect]:
    """
    Build hit rectangles for the main menu / setup screen.

    Includes board size tiles, human/computer, player count or difficulty,
    and load saved game. Positions are fixed for ``WINDOW_WIDTH`` 700.
    """
    button_width = 180  # Wide buttons for opponent and player count
    button_height = 44
    size_button_width = 136  # Narrower tiles for 7/9/11 size choice
    center_x = WINDOW_WIDTH // 2  # Horizontal center of the window
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
