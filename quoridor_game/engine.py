from __future__ import annotations

from collections import deque
from dataclasses import dataclass


DEFAULT_BOARD_SIZE = 9
WALLS_PER_PLAYER = 10

Position = tuple[int, int]
WallPosition = tuple[int, int]


@dataclass
class PlayerState:
    name: str
    pawn: Position
    goal_row: int
    walls_remaining: int = WALLS_PER_PLAYER


@dataclass(frozen=True)
class PlayerSnapshot:
    name: str
    pawn: Position
    goal_row: int
    walls_remaining: int


@dataclass(frozen=True)
class GameSnapshot:
    board_size: int
    players: tuple[PlayerSnapshot, ...]
    current_turn: int
    horizontal_walls: frozenset[WallPosition]
    vertical_walls: frozenset[WallPosition]
    winner: int | None
    status: str


class QuoridorGame:
    def __init__(self, board_size: int = DEFAULT_BOARD_SIZE) -> None:
        self.board_size = board_size
        self.reset()

    def reset(self) -> None:
        center_col = self.board_size // 2
        self.players = [
            PlayerState(name="Player 1", pawn=(self.board_size - 1, center_col), goal_row=0),
            PlayerState(name="Player 2", pawn=(0, center_col), goal_row=self.board_size - 1),
        ]
        self.current_turn = 0
        self.horizontal_walls: set[WallPosition] = set()
        self.vertical_walls: set[WallPosition] = set()
        self.winner: int | None = None
        self.status = "Player 1 to move"

    def snapshot(self) -> GameSnapshot:
        return GameSnapshot(
            board_size=self.board_size,
            players=tuple(
                PlayerSnapshot(
                    name=player.name,
                    pawn=player.pawn,
                    goal_row=player.goal_row,
                    walls_remaining=player.walls_remaining,
                )
                for player in self.players
            ),
            current_turn=self.current_turn,
            horizontal_walls=frozenset(self.horizontal_walls),
            vertical_walls=frozenset(self.vertical_walls),
            winner=self.winner,
            status=self.status,
        )

    def restore(self, snapshot: GameSnapshot) -> None:
        self.board_size = snapshot.board_size
        self.players = [
            PlayerState(
                name=player.name,
                pawn=player.pawn,
                goal_row=player.goal_row,
                walls_remaining=player.walls_remaining,
            )
            for player in snapshot.players
        ]
        self.current_turn = snapshot.current_turn
        self.horizontal_walls = set(snapshot.horizontal_walls)
        self.vertical_walls = set(snapshot.vertical_walls)
        self.winner = snapshot.winner
        self.status = snapshot.status

    @property
    def current_player(self) -> PlayerState:
        return self.players[self.current_turn]

    @property
    def waiting_player(self) -> PlayerState:
        return self.players[1 - self.current_turn]

    def legal_moves_for_current_player(self) -> list[Position]:
        if self.winner is not None:
            return []

        player = self.current_player
        opponent = self.waiting_player
        row, col = player.pawn
        moves: list[Position] = []

        for delta_row, delta_col in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            adjacent = (row + delta_row, col + delta_col)
            if not self._in_bounds(adjacent) or self._edge_blocked(player.pawn, adjacent):
                continue

            if adjacent != opponent.pawn:
                moves.append(adjacent)
                continue

            jump_square = (adjacent[0] + delta_row, adjacent[1] + delta_col)
            if self._in_bounds(jump_square) and not self._edge_blocked(adjacent, jump_square):
                moves.append(jump_square)
                continue

            if delta_row != 0:
                for side_col in (-1, 1):
                    diagonal = (adjacent[0], adjacent[1] + side_col)
                    if self._in_bounds(diagonal) and not self._edge_blocked(adjacent, diagonal):
                        moves.append(diagonal)
            else:
                for side_row in (-1, 1):
                    diagonal = (adjacent[0] + side_row, adjacent[1])
                    if self._in_bounds(diagonal) and not self._edge_blocked(adjacent, diagonal):
                        moves.append(diagonal)

        return sorted(set(moves))

    def move_pawn(self, destination: Position) -> bool:
        if destination not in self.legal_moves_for_current_player():
            self.status = "Illegal move"
            return False

        self.current_player.pawn = destination
        if destination[0] == self.current_player.goal_row:
            self.winner = self.current_turn
            self.status = f"{self.current_player.name} wins!"
            return True

        self.current_turn = 1 - self.current_turn
        self.status = f"{self.current_player.name} to move"
        return True

    def place_wall(self, orientation: str, position: WallPosition) -> bool:
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
        self.current_turn = 1 - self.current_turn
        self.status = f"{self.current_player.name} to move"
        return True

    def wall_is_valid(self, orientation: str, position: WallPosition) -> tuple[bool, str]:
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
            self.horizontal_walls.add(position)
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
        for index, player in enumerate(self.players):
            if player.pawn == position:
                return index
        return None

    def shortest_path_for_player(self, player_index: int) -> list[Position]:
        start = self.players[player_index].pawn
        goal_row = self.players[player_index].goal_row
        queue: deque[Position] = deque([start])
        previous: dict[Position, Position | None] = {start: None}

        while queue:
            current = queue.popleft()
            if current[0] == goal_row:
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
        return all(self._player_has_path(index) for index in range(len(self.players)))

    def _player_has_path(self, player_index: int) -> bool:
        start = self.players[player_index].pawn
        goal_row = self.players[player_index].goal_row
        queue: deque[Position] = deque([start])
        visited = {start}

        while queue:
            current = queue.popleft()
            if current[0] == goal_row:
                return True

            row, col = current
            for delta_row, delta_col in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nxt = (row + delta_row, col + delta_col)
                if not self._in_bounds(nxt) or nxt in visited or self._edge_blocked(current, nxt):
                    continue
                visited.add(nxt)
                queue.append(nxt)

        return False

    def _edge_blocked(self, start: Position, end: Position) -> bool:
        start_row, start_col = start
        end_row, end_col = end
        if abs(start_row - end_row) + abs(start_col - end_col) != 1:
            return True

        if start_row == end_row:
            row = start_row
            left_col = min(start_col, end_col)
            return (row, left_col) in self.vertical_walls or (row - 1, left_col) in self.vertical_walls

        top_row = min(start_row, end_row)
        col = start_col
        return (top_row, col) in self.horizontal_walls or (top_row, col - 1) in self.horizontal_walls

    def _in_bounds(self, position: Position) -> bool:
        row, col = position
        return 0 <= row < self.board_size and 0 <= col < self.board_size
