"""
Quoridor game package.

This package implements a local Quoridor board game client using Pygame. It is
organized into focused modules:

- ``app`` — Pygame event loop and UI coordination.
- ``engine`` — Rules, legal moves, walls, and path validation.
- ``renderer`` — Drawing setup menu, board, and control panel.
- ``computer`` — AI opponent (easy / medium / hard).
- ``history`` — Undo and redo snapshot stacks.
- ``save_manager`` — JSON persistence of matches.
- ``settings`` — Constants, colors, geometry, and button layouts.

The public entry point for running the game is ``main.py`` at the project root,
which constructs ``QuoridorApp`` from ``quoridor_game.app``.
"""
