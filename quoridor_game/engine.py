"""
Quoridor game rules and state engine.

This module is the authoritative source of truth for match logic. It has no
Pygame dependency. ``QuoridorGame`` tracks pawns, walls, turns, and win state;
``GameSnapshot`` and related dataclasses provide immutable copies for undo,
save/load, and AI search.

Rules implemented
-----------------
- 2 or 4 players with configurable board sizes (typically 7, 9, or 11).
- Orthogonal pawn movement; jumping over adjacent opponent when not blocked.
- Diagonal moves when a straight jump is blocked by a wall or board edge.
- Wall placement with overlap, crossing, and path-existence validation.
- Shortest-path BFS used for AI evaluation and path checks (pawn-only graph).

Player goals
------------
- Players 1–2: reach opposite **rows** (top vs bottom).
- Players 3–4 (four-player mode): reach opposite **columns** (left vs right).
"""

from __future__ import annotations  # Postponed evaluation of type hints

from collections import deque  # BFS queue for shortest-path and connectivity
from dataclasses import dataclass  # Player and snapshot records


DEFAULT_BOARD_SIZE = 9  # Standard Quoridor board dimension when not specified
DEFAULT_PLAYER_COUNT = 2  # Default match is two-player
WALLS_BY_PLAYER_COUNT = {  # Official wall budget per player by mode
    2: 10,
    4: 5,
}

Position = tuple[int, int]  # Board cell (row, col)
WallPosition = tuple[int, int]  # Wall anchor on the (N-1) x (N-1) wall grid
MAX_RECENT_PAWN_MOVES = 16  # Cap history used for AI anti-repetition heuristics


@dataclass
class PlayerState:
    """
    Mutable per-player data during an active game.

    ``goal_axis`` is ``"row"`` or ``"col"``; ``goal_index`` is the target line
    on that axis (e.g. row 0 for player 1 in 2-player mode).
    """

    name: str  # Display label (e.g. "Player 1", "Computer (Hard)")
    pawn: Position  # Current cell coordinates
    goal_axis: str  # "row" or "col" — which coordinate must reach goal_index
    goal_index: int  # Target row or column index for victory
    walls_remaining: int  # Walls this player may still place


@dataclass(frozen=True)
class PlayerSnapshot:
    """Immutable copy of ``PlayerState`` for snapshots."""

    name: str
    pawn: Position
    goal_axis: str
    goal_index: int
    walls_remaining: int


@dataclass(frozen=True)
class PawnMoveSnapshot:
    """Record of one pawn move for undo history and AI repetition penalties."""

    player_index: int
    start: Position
    end: Position


@dataclass(frozen=True)
class GameSnapshot:
    """
    Full frozen game state for undo, redo, save, and AI simulation.

    Wall sets are ``frozenset`` so snapshots are hashable and safe to share.
    """

    board_size: int
    players: tuple[PlayerSnapshot, ...]
    current_turn: int  # Index into players of who moves next
    horizontal_walls: frozenset[WallPosition]
    vertical_walls: frozenset[WallPosition]
    winner: int | None  # Player index who won, or None if ongoing
    status: str  # Human-readable status line for the UI
    recent_pawn_moves: tuple[PawnMoveSnapshot, ...] = ()  # Newest moves at end


class QuoridorGame:
    """
    Mutable Quoridor match: rules enforcement, turn order, and path finding.

    Construct with ``board_size`` and ``player_count``, then call ``reset`` or
    ``restore`` to set positions. Public methods mutate state when moves are legal.
    """

    def __init__(self, board_size: int = DEFAULT_BOARD_SIZE, player_count: int = DEFAULT_PLAYER_COUNT) -> None:
        """
        Create a game and initialize to the standard starting position.

        Raises ``ValueError`` if ``player_count`` is not 2 or 4.
        """
        if player_count not in WALLS_BY_PLAYER_COUNT:
            raise ValueError("Quoridor supports 2 or 4 players")
        self.board_size = board_size
        self.player_count = player_count
        self.reset()  # Populate players, walls, turn, and status

    def reset(self) -> None:
        """
        Return all state to the opening position for current size and player count.

        Does not change ``board_size`` or ``player_count``.
        """
        center = self.board_size // 2  # Middle column/row for starting pawns
        walls_per_player = WALLS_BY_PLAYER_COUNT[self.player_count]
        self.players = [
            PlayerState(
                name="Player 1",
                pawn=(self.board_size - 1, center),  # Bottom row, center
                goal_axis="row",
                goal_index=0,  # Goal: top row
                walls_remaining=walls_per_player,
            ),
            PlayerState(
                name="Player 2",
                pawn=(0, center),  # Top row, center
                goal_axis="row",
                goal_index=self.board_size - 1,  # Goal: bottom row
                walls_remaining=walls_per_player,
            ),
        ]
        if self.player_count == 4:  # Add side players moving horizontally
            self.players.extend(
                [
                    PlayerState(
                        name="Player 3",
                        pawn=(center, 0),  # Left side
                        goal_axis="col",
                        goal_index=self.board_size - 1,  # Goal: right column
                        walls_remaining=walls_per_player,
                    ),
                    PlayerState(
                        name="Player 4",
                        pawn=(center, self.board_size - 1),  # Right side
                        goal_axis="col",
                        goal_index=0,  # Goal: left column
                        walls_remaining=walls_per_player,
                    ),
                ]
            )
        self.current_turn = 0  # Player 1 moves first
        self.horizontal_walls: set[WallPosition] = set()  # Mutable working sets
        self.vertical_walls: set[WallPosition] = set()
        self.winner: int | None = None
        self.status = "Player 1 to move"
        self.recent_pawn_moves: list[PawnMoveSnapshot] = []

    def snapshot(self) -> GameSnapshot:
        """
        Capture an immutable copy of the current state for history or saves.
        """
        return GameSnapshot(
            board_size=self.board_size,
            players=tuple(
                PlayerSnapshot(
                    name=player.name,
                    pawn=player.pawn,
                    goal_axis=player.goal_axis,
                    goal_index=player.goal_index,
                    walls_remaining=player.walls_remaining,
                )
                for player in self.players
            ),
            current_turn=self.current_turn,
            horizontal_walls=frozenset(self.horizontal_walls),
            vertical_walls=frozenset(self.vertical_walls),
            winner=self.winner,
            status=self.status,
            recent_pawn_moves=tuple(self.recent_pawn_moves),
        )

    def restore(self, snapshot: GameSnapshot) -> None:
        """
        Replace all mutable state from a previously captured ``GameSnapshot``.
        """
        self.board_size = snapshot.board_size
        self.player_count = len(snapshot.players)
        self.players = [
            PlayerState(
                name=player.name,
                pawn=player.pawn,
                goal_axis=player.goal_axis,
                goal_index=player.goal_index,
                walls_remaining=player.walls_remaining,
            )
            for player in snapshot.players
        ]
        self.current_turn = snapshot.current_turn
        self.horizontal_walls = set(snapshot.horizontal_walls)
        self.vertical_walls = set(snapshot.vertical_walls)
        self.winner = snapshot.winner
        self.status = snapshot.status
        self.recent_pawn_moves = list(snapshot.recent_pawn_moves[-MAX_RECENT_PAWN_MOVES:])

    @property
    def current_player(self) -> PlayerState:
        """The ``PlayerState`` for whoever moves next."""
        return self.players[self.current_turn]

    @property
    def waiting_player(self) -> PlayerState:
        """The next player in turn order (used sparingly; mostly for 2-player context)."""
        return self.players[(self.current_turn + 1) % len(self.players)]

    def legal_moves_for_current_player(self) -> list[Position]:
        """
        Return sorted unique legal destination cells for the current pawn.

        Includes orthogonal steps, jumps over adjacent opponents, and diagonal
        escapes when a jump is blocked. Empty when the game has a winner.
        """
        if self.winner is not None:
            return []

        player = self.current_player
        occupied_positions = {
            opponent.pawn
            for index, opponent in enumerate(self.players)
            if index != self.current_turn
        }
        row, col = player.pawn
        moves: list[Position] = []

        for delta_row, delta_col in [(-1, 0), (1, 0), (0, -1), (0, 1)]:  # N, S, W, E neighbors
            adjacent = (row + delta_row, col + delta_col)
            if not self._in_bounds(adjacent) or self._edge_blocked(player.pawn, adjacent):
                continue

            if adjacent not in occupied_positions:  # Simple step into empty cell
                moves.append(adjacent)
                continue

            jump_square = (adjacent[0] + delta_row, adjacent[1] + delta_col)  # Straight jump over pawn
            if (
                self._in_bounds(jump_square)
                and jump_square not in occupied_positions
                and not self._edge_blocked(adjacent, jump_square)
            ):
                moves.append(jump_square)
                continue

            if delta_row != 0:  # Vertical approach blocked: try diagonal left/right
                for side_col in (-1, 1):
                    diagonal = (adjacent[0], adjacent[1] + side_col)
                    if (
                        self._in_bounds(diagonal)
                        and diagonal not in occupied_positions
                        and not self._edge_blocked(adjacent, diagonal)
                    ):
                        moves.append(diagonal)
            else:  # Horizontal approach blocked: try diagonal up/down
                for side_row in (-1, 1):
                    diagonal = (adjacent[0] + side_row, adjacent[1])
                    if (
                        self._in_bounds(diagonal)
                        and diagonal not in occupied_positions
                        and not self._edge_blocked(adjacent, diagonal)
                    ):
                        moves.append(diagonal)

        return sorted(set(moves))  # Stable order, no duplicates

    def move_pawn(self, destination: Position) -> bool:
        """
        Move the current player's pawn to ``destination`` if legal.

        Updates ``status``, advances turn on success, sets ``winner`` if goal
        reached. Returns False for illegal moves without changing turn.
        """
        if destination not in self.legal_moves_for_current_player():
            self.status = "Illegal move"
            return False

        player_index = self.current_turn
        start = self.current_player.pawn
        self.current_player.pawn = destination
        self._record_pawn_move(player_index, start, destination)
        if self._player_reached_goal(self.current_player):
            self.winner = self.current_turn
            self.status = f"{self.current_player.name} wins!"
            return True

        self.current_turn = (self.current_turn + 1) % len(self.players)
        self.status = f"{self.current_player.name} to move"
        return True

    def place_wall(self, orientation: str, position: WallPosition) -> bool:
        """
        Place a horizontal (``h``) or vertical (``v``) wall for the current player.

        Decrements ``walls_remaining`` and advances turn on success. Returns False
        if game over, no walls left, or ``wall_is_valid`` fails.
        """
        if self.winner is not None:
            return False

        if self.current_player.walls_remaining <= 0:
            self.status = f"{self.current_player.name} has no walls left"
            return False

        is_valid, reason = self.wall_is_valid(orientation, position)
        if not is_valid:
            self.status = reason
            return False

        wall_set = self.horizontal_walls if orientation == "h" else self.vertical_walls
        wall_set.add(position)
        self.current_player.walls_remaining -= 1
        self.current_turn = (self.current_turn + 1) % len(self.players)
        self.status = f"{self.current_player.name} to move"
        return True

    def wall_is_valid(self, orientation: str, position: WallPosition) -> tuple[bool, str]:
        """
        Check whether a wall could be placed without mutating permanent state.

        Temporarily adds the wall to test path connectivity, then removes it.
        Returns ``(True, "")`` or ``(False, reason_string)``.
        """
        row, col = position
        if orientation not in {"h", "v"}:
            return False, "Unknown wall orientation"
        if not (0 <= row < self.board_size - 1 and 0 <= col < self.board_size - 1):
            return False, "Wall is outside the board"

        if orientation == "h":
            if any(existing_row == row and abs(existing_col - col) < 2 for existing_row, existing_col in self.horizontal_walls):
                return False, "Horizontal wall overlaps another wall"
            if position in self.vertical_walls:
                return False, "Walls cannot cross"
            self.horizontal_walls.add(position)  # Tentative placement for path test
            try:
                if not self._all_players_have_paths():
                    return False, "Wall would block all paths"
            finally:
                self.horizontal_walls.remove(position)
            return True, ""

        if any(existing_col == col and abs(existing_row - row) < 2 for existing_row, existing_col in self.vertical_walls):
            return False, "Vertical wall overlaps another wall"
        if position in self.horizontal_walls:
            return False, "Walls cannot cross"

        self.vertical_walls.add(position)
        try:
            if not self._all_players_have_paths():
                return False, "Wall would block all paths"
        finally:
            self.vertical_walls.remove(position)
        return True, ""

    def pawn_at(self, position: Position) -> int | None:
        """
        Return the player index occupying ``position``, or None if empty.
        """
        for index, player in enumerate(self.players):
            if player.pawn == position:
                return index
        return None

    def last_pawn_move_for_player(self, player_index: int) -> PawnMoveSnapshot | None:
        """
        Return the most recent pawn move by ``player_index``, or None.
        """
        for move in reversed(self.recent_pawn_moves):
            if move.player_index == player_index:
                return move
        return None

    def shortest_path_for_player(self, player_index: int) -> list[Position]:
        """
        BFS shortest path from the player's pawn to any goal cell (pawn-only graph).

        Returns ordered list of positions from start to goal inclusive, or []
        if unreachable. Used by AI for distance evaluation and wall scoring.
        """
        start = self.players[player_index].pawn
        queue: deque[Position] = deque([start])
        previous: dict[Position, Position | None] = {start: None}

        while queue:
            current = queue.popleft()
            if self._position_reaches_goal(self.players[player_index], current):
                path: list[Position] = []
                while current is not None:
                    path.append(current)
                    current = previous[current]
                return list(reversed(path))

            row, col = current
            for delta_row, delta_col in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nxt = (row + delta_row, col + delta_col)
                if not self._in_bounds(nxt) or nxt in previous or self._edge_blocked(current, nxt):
                    continue
                previous[nxt] = current
                queue.append(nxt)

        return []

    def _all_players_have_paths(self) -> bool:
        """
        Return True if every player can still reach their goal (wall rule).
        """
        return all(self._player_has_path(index) for index in range(len(self.players)))

    def _player_has_path(self, player_index: int) -> bool:
        """
        BFS connectivity test: can ``player_index`` reach any goal cell?
        """
        start = self.players[player_index].pawn
        queue: deque[Position] = deque([start])
        visited = {start}

        while queue:
            current = queue.popleft()
            if self._position_reaches_goal(self.players[player_index], current):
                return True

            row, col = current
            for delta_row, delta_col in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nxt = (row + delta_row, col + delta_col)
                if not self._in_bounds(nxt) or nxt in visited or self._edge_blocked(current, nxt):
                    continue
                visited.add(nxt)
                queue.append(nxt)

        return False

    def _record_pawn_move(self, player_index: int, start: Position, end: Position) -> None:
        """
        Append a pawn move to ``recent_pawn_moves``, trimming to max length.
        """
        self.recent_pawn_moves.append(PawnMoveSnapshot(player_index, start, end))
        if len(self.recent_pawn_moves) > MAX_RECENT_PAWN_MOVES:
            self.recent_pawn_moves = self.recent_pawn_moves[-MAX_RECENT_PAWN_MOVES:]

    def _player_reached_goal(self, player: PlayerState) -> bool:
        """True if the player's pawn sits on their goal line."""
        return self._position_reaches_goal(player, player.pawn)

    def _position_reaches_goal(self, player: PlayerState, position: Position) -> bool:
        """True if ``position`` is on the goal row or column for ``player``."""
        row, col = position
        if player.goal_axis == "row":
            return row == player.goal_index
        return col == player.goal_index

    def _edge_blocked(self, start: Position, end: Position) -> bool:
        """
        Return True if a wall blocks movement between adjacent cells ``start`` and ``end``.

        Only supports Manhattan distance 1; otherwise treated as blocked.
        """
        start_row, start_col = start
        end_row, end_col = end
        if abs(start_row - end_row) + abs(start_col - end_col) != 1:
            return True

        if start_row == end_row:  # Horizontal move: blocked by vertical wall between cols
            row = start_row
            left_col = min(start_col, end_col)
            return (row, left_col) in self.vertical_walls or (row - 1, left_col) in self.vertical_walls

        top_row = min(start_row, end_row)  # Vertical move: blocked by horizontal wall between rows
        col = start_col
        return (top_row, col) in self.horizontal_walls or (top_row, col - 1) in self.horizontal_walls

    def _in_bounds(self, position: Position) -> bool:
        """True if ``position`` is a valid cell on the board."""
        row, col = position
        return 0 <= row < self.board_size and 0 <= col < self.board_size
