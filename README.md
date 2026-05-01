# Quoridor Pygame Project

Local Quoridor built with Pygame. Play against another human on the same device or against the computer.

## Run

```bash
pip install -r requirements.txt
python main.py
```

## Controls

- Left click your pawn, then click a highlighted square to move.
- From the main menu, choose a `7x7`, `9x9`, or `11x11` board before starting.
- Click `Load Saved Game` from the main menu to resume the last saved match.
- Click `Move`, `Wall H`, or `Wall V` in the bottom panel to change action mode.
- Click `Undo` or `Redo` to step through move history.
- Click `Save` while playing to save the current game state.
- Click `Menu` to return to the main menu and choose another game mode.
- In wall mode, click a wall slot on the board to place a wall.
- Press `M` for move mode.
- Press `H` for horizontal wall mode.
- Press `V` for vertical wall mode.
- Press `U` to undo, `Y` to redo, `Ctrl+Z` to undo, or `Ctrl+Y` / `Ctrl+Shift+Z` to redo.
- Press `Ctrl+S` to save the current match.
- Press `R` to reset the match.

## Opponents

- Choose `Human`, then select `2 Players` or `4 Players` for a local match.
- Choose `Computer`, then select `Easy`, `Medium`, or `Hard` difficulty.

## Rules Implemented

- 7x7, 9x9, and 11x11 board options
- 2-player and 4-player human modes
- Human-vs-computer mode
- 10 walls per player in 2-player games, 5 walls per player in 4-player games
- Orthogonal movement
- Jumping over an adjacent pawn when open
- Diagonal moves around a blocked jump
- Wall overlap and crossing prevention
- Path validation so every player always keeps at least one route to goal
