# Quoridor Pygame Project

Local Quoridor built with Pygame. Play against another human on the same device or against the computer.

## Run

```bash
pip install -r requirements.txt
python main.py
```

## Code Structure

- `main.py` starts the app.
- `quoridor_game/app.py` coordinates the game loop, input, setup, saving, history, and computer turns.
- `quoridor_game/engine.py` contains the Quoridor rules and game state.
- `quoridor_game/renderer.py` draws the setup screen, board, pawns, walls, and buttons.
- `quoridor_game/computer.py` chooses computer moves for each difficulty.
- `quoridor_game/history.py` manages undo and redo snapshots.
- `quoridor_game/save_manager.py` reads and writes saved games.
- `quoridor_game/settings.py` keeps shared constants, layout, and board geometry helpers.

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
- `Easy` chooses the best immediate move or wall from the current board position.
- `Medium` uses minimax depth 1: it checks the computer move, the human reply, then scores the result.
- `Hard` uses minimax depth 2: it checks the computer move, the human reply, the next computer reply, then scores the result.
- Computer scoring uses legal pawn movement, including jumps and diagonal moves, so it avoids the old stuck-loop behavior without using repeat-position penalties.

## Build EXE

Build the Windows executable with Python 3.13:

```bash
py -3.13 -m PyInstaller --noconfirm --clean --onefile --windowed --name Quoridor main.py
```

The executable is created at `dist/Quoridor.exe`.

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
