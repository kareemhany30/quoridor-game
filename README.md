# Quoridor Pygame Project

Local Quoridor built with Pygame. Play against another human on the same device or against the computer.

## Run

```bash
pip install -r requirements.txt
python main.py
```

## Controls

- Left click your pawn, then click a highlighted square to move.
- Click `Move`, `Wall H`, or `Wall V` in the bottom panel to change action mode.
- In wall mode, click a wall slot on the board to place a wall.
- Press `M` for move mode.
- Press `H` for horizontal wall mode.
- Press `V` for vertical wall mode.
- Press `R` to reset the match.

## Opponents

- Choose `Human` to play a local 2-player match.
- Choose `Computer`, then select `Easy`, `Medium`, or `Hard` difficulty.

## Rules Implemented

- 9x9 board
- Human-vs-human and human-vs-computer modes
- 10 walls per player
- Orthogonal movement
- Jumping over an adjacent pawn when open
- Diagonal moves around a blocked jump
- Wall overlap and crossing prevention
- Path validation so both players always keep at least one route to goal
