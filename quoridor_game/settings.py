from __future__ import annotations

import os
import sys
from pathlib import Path

import pygame

from .engine import Position, WallPosition


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
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAVE_DIR = Path(os.environ.get("APPDATA", Path.home())) / "Quoridor"
SAVE_FILE = SAVE_DIR / "saved_game.json"
if getattr(sys, "frozen", False):
    EXE_DIR = Path(sys.executable).resolve().parent
    LEGACY_SAVE_FILES = (EXE_DIR / "saved_game.json", EXE_DIR.parent / "saved_game.json")
else:
    LEGACY_SAVE_FILES = (PROJECT_ROOT / "saved_game.json", PROJECT_ROOT / "dist" / "saved_game.json")
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


class BoardGeometry:
    def __init__(self, board_size: int) -> None:
        self.update(board_size)

    def update(self, board_size: int) -> None:
        self.board_size = board_size
        self.cell_size = CELL_SIZE_BY_BOARD_SIZE[board_size]
        self.board_pixels = board_size * self.cell_size + (board_size - 1) * GAP_SIZE
        self.panel_top = BOARD_TOP + self.board_pixels + 18

    def cell_rect(self, row: int, col: int) -> pygame.Rect:
        x_pos = BOARD_LEFT + col * (self.cell_size + GAP_SIZE)
        y_pos = BOARD_TOP + row * (self.cell_size + GAP_SIZE)
        return pygame.Rect(x_pos, y_pos, self.cell_size, self.cell_size)

    def horizontal_wall_rect(self, row: int, col: int) -> pygame.Rect:
        left = self.cell_rect(row, col).left
        top = self.cell_rect(row, col).bottom
        width = self.cell_size * 2 + GAP_SIZE
        return pygame.Rect(left, top, width, GAP_SIZE)

    def vertical_wall_rect(self, row: int, col: int) -> pygame.Rect:
        left = self.cell_rect(row, col).right
        top = self.cell_rect(row, col).top
        height = self.cell_size * 2 + GAP_SIZE
        return pygame.Rect(left, top, GAP_SIZE, height)

    def cell_at(self, mouse_pos: tuple[int, int]) -> Position | None:
        for row in range(self.board_size):
            for col in range(self.board_size):
                if self.cell_rect(row, col).collidepoint(mouse_pos):
                    return (row, col)
        return None

    def wall_slot_at(self, mouse_pos: tuple[int, int], orientation: str) -> WallPosition | None:
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
    button_width = 74
    button_height = 38
    start_x = BOARD_LEFT
    start_y = panel_top + 88
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


def build_setup_buttons() -> dict[str, pygame.Rect]:
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
