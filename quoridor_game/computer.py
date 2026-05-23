from __future__ import annotations

import random

from collections import deque

from .engine import Position, QuoridorGame, WallPosition
from .settings import ComputerAction


class ComputerPlayer:
    def choose_action(self, game: QuoridorGame, difficulty: str | None) -> ComputerAction:
        difficulty = difficulty or "easy"
        if difficulty == "easy":
            return self._choose_easy_action(game)
        if difficulty == "medium":
            return self._choose_medium_action(game)
        return self._choose_hard_action(game)

    def _choose_easy_action(self, game: QuoridorGame) -> ComputerAction:
        wall = self._best_blocking_wall(game)
        if wall is not None and random.random() < 0.22:
            return ("wall", wall[0], wall[1])
        if random.random() < 0.85:
            return ("move", self._best_path_move(game, 1))
        return ("move", random.choice(game.legal_moves_for_current_player()))

    def _choose_medium_action(self, game: QuoridorGame) -> ComputerAction:
        return self._best_immediate_action(game, wall_limit=8)

    def _choose_hard_action(self, game: QuoridorGame) -> ComputerAction:
        actions = self._candidate_actions_for_current_player(game, wall_limit=8, exhaustive_walls=True)
        if not actions:
            return ("move", random.choice(game.legal_moves_for_current_player()))

        best_action = actions[0]
        best_score = (-100000.0, -100000.0, 0.0)
        for action in actions:
            snapshot = game.snapshot()
            try:
                if not self._apply_action(game, action):
                    continue
                score = (
                    self._minimax(game, depth=1, alpha=-100000.0, beta=100000.0),
                    self._evaluate_position(game),
                    random.random(),
                )
            finally:
                game.restore(snapshot)

            if score > best_score:
                best_score = score
                best_action = action

        return best_action

    def _best_path_move(self, game: QuoridorGame, player_index: int) -> Position:
        path = game.shortest_path_for_player(player_index)
        legal_moves = game.legal_moves_for_current_player()
        if len(path) > 1 and path[1] in legal_moves:
            return path[1]
        return min(
            legal_moves,
            key=lambda move: (
                self._distance_to_goal_after_move(game, player_index, move),
                random.random(),
            ),
        )

    def _best_immediate_action(self, game: QuoridorGame, wall_limit: int) -> ComputerAction:
        actions = self._candidate_actions_for_current_player(game, wall_limit, exhaustive_walls=True)
        if not actions:
            return ("move", random.choice(game.legal_moves_for_current_player()))

        return max(actions, key=lambda action: self._score_action(game, action))

    def _candidate_actions_for_current_player(
        self,
        game: QuoridorGame,
        wall_limit: int,
        exhaustive_walls: bool = False,
    ) -> list[ComputerAction]:
        actions: list[ComputerAction] = [("move", move) for move in game.legal_moves_for_current_player()]
        actions.extend(
            ("wall", orientation, position)
            for orientation, position, score in self._ranked_wall_candidates_for_current_player(
                game,
                wall_limit,
                exhaustive=exhaustive_walls,
            )
            if score > 0
        )
        return actions

    def _best_blocking_wall(self, game: QuoridorGame) -> tuple[str, WallPosition] | None:
        walls = self._ranked_wall_candidates_for_current_player(game, limit=1, exhaustive=False)
        if walls and walls[0][2] > 0:
            return (walls[0][0], walls[0][1])
        return None

    def _ranked_wall_candidates_for_current_player(
        self,
        game: QuoridorGame,
        limit: int,
        exhaustive: bool,
    ) -> list[tuple[str, WallPosition, float]]:
        if game.current_player.walls_remaining <= 0:
            return []

        player_index = game.current_turn
        opponent_index = 1 - player_index
        player_path = game.shortest_path_for_player(player_index)
        opponent_path = game.shortest_path_for_player(opponent_index)
        if len(opponent_path) < 2:
            return []

        original_player_length = len(player_path) if player_path else 99
        original_opponent_length = len(opponent_path)
        priority_walls: set[tuple[str, WallPosition]] = set()

        for start, end in zip(opponent_path, opponent_path[1:]):
            priority_walls.update(self._walls_blocking_edge(game, start, end))

        candidates = list(priority_walls)
        if exhaustive:
            all_walls = [
                (orientation, (row, col))
                for orientation in ("h", "v")
                for row in range(game.board_size - 1)
                for col in range(game.board_size - 1)
            ]
            candidates.extend(wall for wall in all_walls if wall not in priority_walls)
        scored: list[tuple[str, WallPosition, float]] = []

        for orientation, position in candidates:
            is_valid, _ = game.wall_is_valid(orientation, position)
            if not is_valid:
                continue

            wall_set = game.horizontal_walls if orientation == "h" else game.vertical_walls
            wall_set.add(position)
            try:
                player_length = len(game.shortest_path_for_player(player_index)) or 99
                opponent_length = len(game.shortest_path_for_player(opponent_index)) or 99
            finally:
                wall_set.remove(position)

            score = (opponent_length - original_opponent_length) * 4 - (
                player_length - original_player_length
            ) * 2
            if (orientation, position) in priority_walls:
                score += 0.35
            scored.append((orientation, position, score))

        scored.sort(key=lambda item: item[2], reverse=True)
        return scored[:limit]

    def _score_action(self, game: QuoridorGame, action: ComputerAction) -> float:
        snapshot = game.snapshot()
        try:
            if not self._apply_action(game, action):
                return -100000.0
            return self._evaluate_position(game)
        finally:
            game.restore(snapshot)

    def _apply_action(self, game: QuoridorGame, action: ComputerAction) -> bool:
        if action[0] == "move":
            return game.move_pawn(action[1])
        return game.place_wall(action[1], action[2])

    def _minimax(self, game: QuoridorGame, depth: int, alpha: float, beta: float) -> float:
        if depth == 0 or game.winner is not None:
            return self._evaluate_position(game)

        actions = self._candidate_actions_for_current_player(game, wall_limit=4)
        if not actions:
            return self._evaluate_position(game)

        if game.current_turn == 1:
            value = -100000.0
            for action in actions:
                snapshot = game.snapshot()
                try:
                    if not self._apply_action(game, action):
                        continue
                    value = max(value, self._minimax(game, depth - 1, alpha, beta))
                finally:
                    game.restore(snapshot)
                alpha = max(alpha, value)
                if beta <= alpha:
                    break
            return value

        value = 100000.0
        for action in actions:
            snapshot = game.snapshot()
            try:
                if not self._apply_action(game, action):
                    continue
                value = min(value, self._minimax(game, depth - 1, alpha, beta))
            finally:
                game.restore(snapshot)
            beta = min(beta, value)
            if beta <= alpha:
                break
        return value

    def _evaluate_position(self, game: QuoridorGame) -> float:
        if game.winner == 1:
            return 10000.0
        if game.winner == 0:
            return -10000.0

        computer_distance = self._pawn_distance_to_goal(game, 1)
        human_distance = self._pawn_distance_to_goal(game, 0)
        wall_balance = game.players[1].walls_remaining - game.players[0].walls_remaining
        turn_bonus = 0.2 if game.current_turn == 1 else -0.2
        return (human_distance - computer_distance) * 10 + wall_balance * 0.7 + turn_bonus

    def _distance_to_goal_after_move(self, game: QuoridorGame, player_index: int, destination: Position) -> int:
        player = game.players[player_index]
        original_pawn = player.pawn
        player.pawn = destination
        try:
            distance = self._pawn_distance_to_goal(game, player_index)
        finally:
            player.pawn = original_pawn
        return distance

    def _pawn_distance_to_goal(self, game: QuoridorGame, player_index: int) -> int:
        player = game.players[player_index]
        start = player.pawn
        queue: deque[tuple[Position, int]] = deque([(start, 0)])
        visited = {start}
        original_turn = game.current_turn
        original_pawn = player.pawn

        try:
            while queue:
                current, distance = queue.popleft()
                player.pawn = current
                if game._player_reached_goal(player):
                    return distance

                game.current_turn = player_index
                for move in game.legal_moves_for_current_player():
                    if move in visited:
                        continue
                    visited.add(move)
                    queue.append((move, distance + 1))
        finally:
            player.pawn = original_pawn
            game.current_turn = original_turn

        return 99

    def _walls_blocking_edge(self, game: QuoridorGame, start: Position, end: Position) -> list[tuple[str, WallPosition]]:
        start_row, start_col = start
        end_row, end_col = end
        candidates: list[tuple[str, WallPosition]] = []

        if start_row == end_row:
            row = start_row
            col = min(start_col, end_col)
            candidates.extend([("v", (row, col)), ("v", (row - 1, col))])
        else:
            row = min(start_row, end_row)
            col = start_col
            candidates.extend([("h", (row, col)), ("h", (row, col - 1))])

        return [
            (orientation, position)
            for orientation, position in candidates
            if 0 <= position[0] < game.board_size - 1 and 0 <= position[1] < game.board_size - 1
        ]
