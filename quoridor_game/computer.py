"""
Computer opponent for Human vs Computer Quoridor.

``ComputerPlayer`` selects one action per turn: either move a pawn to a cell or
place a horizontal/vertical wall. It assumes a **two-player** match where index
0 is the human and index 1 is the computer (as configured in ``QuoridorApp``).

Difficulty levels
-----------------
- **Easy**: Mostly follows shortest path; occasional random or blocking wall.
- **Medium**: Picks the best immediate action by static evaluation after one ply.
- **Hard**: Minimax with alpha-beta pruning (depth 2), repetition penalties, and
  a richer candidate action set including ranked walls.

Search and heuristics use ``QuoridorGame.snapshot`` / ``restore`` so the live
board is not corrupted during lookahead. Wall candidates are scored by how much
they lengthen the opponent's shortest path versus the computer's path.
"""

from __future__ import annotations  # Modern type hint syntax

import random  # Tie-breaking and easy-mode randomness

from .engine import Position, QuoridorGame, WallPosition
from .settings import ComputerAction


REVERSAL_PENALTY = 35.0  # Score penalty for undoing the immediately previous pawn move
RECENT_POSITION_PENALTY = 18.0  # Penalty for revisiting a recently occupied cell
RECENT_POSITION_LIMIT = 8  # How many past cells count as "recent" for repetition


class ComputerPlayer:
    """
    Stateless AI: given a ``QuoridorGame`` and difficulty string, return one action.

    All methods are safe to call from the main thread; they temporarily mutate
    ``game`` only inside snapshot/restore blocks.
    """

    def choose_action(self, game: QuoridorGame, difficulty: str | None) -> ComputerAction:
        """
        Entry point: dispatch to easy, medium, or hard strategy.

        ``difficulty`` None or unknown values default to easy. Returns either
        ``("move", (row, col))`` or ``("wall", orientation, (row, col))``.
        """
        difficulty = difficulty or "easy"  # Default when not specified
        if difficulty == "easy":
            return self._choose_easy_action(game)
        if difficulty == "medium":
            return self._choose_medium_action(game)
        return self._choose_hard_action(game)

    def _choose_easy_action(self, game: QuoridorGame) -> ComputerAction:
        """
        Easy AI: path-following with light randomness and rare blocking walls.

        ~22% chance to play best blocking wall if one exists; ~85% chance to
        follow shortest path; otherwise random non-repeating legal move.
        """
        wall = self._best_blocking_wall(game)
        if wall is not None and random.random() < 0.22:
            return ("wall", wall[0], wall[1])
        if random.random() < 0.85:
            return ("move", self._best_path_move(game, 1))  # Player index 1 = computer
        return ("move", self._random_non_repeating_move(game))

    def _choose_medium_action(self, game: QuoridorGame) -> ComputerAction:
        """
        Medium AI: maximize static evaluation after one ply (move or wall).

        Considers up to eight top wall candidates plus all legal pawn moves.
        """
        return self._best_immediate_action(game, wall_limit=8)

    def _choose_hard_action(self, game: QuoridorGame) -> ComputerAction:
        """
        Hard AI: minimax depth-2 with alpha-beta over candidate actions.

        Computer (player 1) maximizes; human (player 0) minimizes in search.
        Applies repetition penalty to root move choice.
        """
        actions = self._candidate_actions_for_current_player(game, wall_limit=8, exhaustive_walls=True)
        if not actions:
            return ("move", random.choice(game.legal_moves_for_current_player()))

        best_action = actions[0]
        best_score = -100000.0
        for action in actions:
            repetition_penalty = self._action_repetition_penalty(game, action)
            snapshot = game.snapshot()
            try:
                if not self._apply_action(game, action):
                    continue
                score = self._minimax(game, depth=2, alpha=-100000.0, beta=100000.0) - repetition_penalty
            finally:
                game.restore(snapshot)

            if score > best_score:
                best_score = score
                best_action = action

        return best_action

    def _best_path_move(self, game: QuoridorGame, player_index: int) -> Position:
        """
        Choose a legal move that advances along the shortest path toward goal.

        Prefers the second node on the BFS path if legal and not repetition-penalized;
        otherwise picks minimum penalty, then distance, with random tie-break.
        """
        path = game.shortest_path_for_player(player_index)
        legal_moves = game.legal_moves_for_current_player()
        if len(path) > 1 and path[1] in legal_moves:
            preferred_move = path[1]
            if self._move_repetition_penalty(game, preferred_move, legal_moves) <= 0:
                return preferred_move
        return min(
            legal_moves,
            key=lambda move: (
                self._move_repetition_penalty(game, move, legal_moves),
                self._distance_to_goal_after_move(game, player_index, move),
                random.random(),
            ),
        )

    def _random_non_repeating_move(self, game: QuoridorGame) -> Position:
        """
        Pick a random legal move, preferring cells without repetition penalty.
        """
        legal_moves = game.legal_moves_for_current_player()
        non_repeating_moves = [
            move for move in legal_moves if self._move_repetition_penalty(game, move, legal_moves) <= 0
        ]
        return random.choice(non_repeating_moves or legal_moves)

    def _best_immediate_action(self, game: QuoridorGame, wall_limit: int) -> ComputerAction:
        """
        Return the candidate action with highest one-ply ``_score_action`` value.
        """
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
        """
        Build list of legal moves and positively scored wall placements for current player.

        Walls with score <= 0 are excluded. ``exhaustive_walls`` adds all board
        slots after priority walls along opponent path.
        """
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
        """
        Return the top-ranked blocking wall (orientation, position) if score > 0, else None.
        """
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
        """
        Score wall placements by effect on shortest-path lengths (2-player).

        Priority candidates lie on edges of the opponent's shortest path. Each
        candidate is tentatively placed, paths recomputed, then removed. Higher
        score means more opponent delay with less self penalty.
        """
        if game.current_player.walls_remaining <= 0:
            return []

        player_index = game.current_turn
        opponent_index = 1 - player_index  # Two-player assumption
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
                score += 0.35  # Small bonus for path-aligned walls
            scored.append((orientation, position, score))

        scored.sort(key=lambda item: item[2], reverse=True)
        return scored[:limit]

    def _score_action(self, game: QuoridorGame, action: ComputerAction) -> float:
        """
        Evaluate ``action`` by applying it temporarily and calling ``_evaluate_position``.

        Returns large negative value if the action cannot be applied.
        """
        repetition_penalty = self._action_repetition_penalty(game, action)
        snapshot = game.snapshot()
        try:
            if not self._apply_action(game, action):
                return -100000.0
            return self._evaluate_position(game) - repetition_penalty
        finally:
            game.restore(snapshot)

    def _apply_action(self, game: QuoridorGame, action: ComputerAction) -> bool:
        """
        Apply a move or wall action to ``game``; return success flag from engine.
        """
        if action[0] == "move":
            return game.move_pawn(action[1])
        return game.place_wall(action[1], action[2])

    def _minimax(self, game: QuoridorGame, depth: int, alpha: float, beta: float) -> float:
        """
        Minimax with alpha-beta pruning from the current position.

        Player 1 (computer) maximizes; all other turns minimize. Leaf nodes use
        ``_evaluate_position``. Depth counts full plies; wall_limit 4 in recursion
        keeps branching manageable.
        """
        if depth == 0 or game.winner is not None:
            return self._evaluate_position(game)

        actions = self._candidate_actions_for_current_player(game, wall_limit=4)
        if not actions:
            return self._evaluate_position(game)

        if game.current_turn == 1:  # Computer maximizing node
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

        value = 100000.0  # Human minimizing node
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
        """
        Static evaluation from the computer's perspective (player 1).

        Positive is good for the AI: human farther from goal, computer closer,
        more walls in reserve, and bonus when it is the computer's turn.
        """
        if game.winner == 1:
            return 10000.0
        if game.winner == 0:
            return -10000.0

        computer_path = game.shortest_path_for_player(1)
        human_path = game.shortest_path_for_player(0)
        computer_distance = len(computer_path) - 1 if computer_path else 99
        human_distance = len(human_path) - 1 if human_path else 99
        wall_balance = game.players[1].walls_remaining - game.players[0].walls_remaining
        turn_bonus = 0.2 if game.current_turn == 1 else -0.2
        return (human_distance - computer_distance) * 10 + wall_balance * 0.7 + turn_bonus

    def _action_repetition_penalty(self, game: QuoridorGame, action: ComputerAction) -> float:
        """
        Repetition penalty for move actions only; walls return 0.
        """
        if action[0] != "move":
            return 0.0
        return self._move_repetition_penalty(game, action[1])

    def _move_repetition_penalty(
        self,
        game: QuoridorGame,
        destination: Position,
        legal_moves: list[Position] | None = None,
    ) -> float:
        """
        Relative repetition penalty: raw penalty minus best penalty among legal moves.

        Avoids over-penalizing when every move would revisit a recent cell.
        """
        raw_penalty = self._raw_move_repetition_penalty(game, destination)
        if raw_penalty <= 0:
            return 0.0

        legal_moves = legal_moves or game.legal_moves_for_current_player()
        best_available_penalty = min(
            self._raw_move_repetition_penalty(game, move)
            for move in legal_moves
        )
        return max(0.0, raw_penalty - best_available_penalty)

    def _raw_move_repetition_penalty(self, game: QuoridorGame, destination: Position) -> float:
        """
        Full penalty for immediate back-and-forth or revisiting a recent cell.
        """
        if self._is_immediate_pawn_reversal(game, destination):
            return REVERSAL_PENALTY
        if destination in self._recent_positions_for_current_player(game):
            return RECENT_POSITION_PENALTY
        return 0.0

    def _is_immediate_pawn_reversal(self, game: QuoridorGame, destination: Position) -> bool:
        """
        True if moving to ``destination`` would undo the player's last pawn move.
        """
        last_move = game.last_pawn_move_for_player(game.current_turn)
        return (
            last_move is not None
            and last_move.start == destination
            and last_move.end == game.current_player.pawn
        )

    def _recent_positions_for_current_player(self, game: QuoridorGame) -> set[Position]:
        """
        Collect cells the current player recently visited (for oscillation avoidance).
        """
        positions: list[Position] = []
        for move in reversed(game.recent_pawn_moves):
            if move.player_index != game.current_turn:
                continue
            if move.end != game.current_player.pawn:
                positions.append(move.end)
            if move.start != game.current_player.pawn:
                positions.append(move.start)
            if len(positions) >= RECENT_POSITION_LIMIT:
                break
        return set(positions[:RECENT_POSITION_LIMIT])

    def _distance_to_goal_after_move(self, game: QuoridorGame, player_index: int, destination: Position) -> int:
        """
        Shortest-path length to goal if ``player_index``'s pawn were at ``destination``.

        Temporarily moves pawn on ``PlayerState``; restores after BFS.
        """
        player = game.players[player_index]
        original_pawn = player.pawn
        player.pawn = destination
        try:
            path = game.shortest_path_for_player(player_index)
        finally:
            player.pawn = original_pawn
        return len(path) - 1 if path else 99

    def _walls_blocking_edge(self, game: QuoridorGame, start: Position, end: Position) -> list[tuple[str, WallPosition]]:
        """
        List wall (orientation, slot) candidates that could block movement along edge start→end.

        Returns up to two horizontal or vertical wall anchors adjacent to the edge,
        filtered to on-board wall coordinates.
        """
        start_row, start_col = start
        end_row, end_col = end
        candidates: list[tuple[str, WallPosition]] = []

        if start_row == end_row:  # Horizontal step along a row → vertical walls block
            row = start_row
            col = min(start_col, end_col)
            candidates.extend([("v", (row, col)), ("v", (row - 1, col))])
        else:  # Vertical step → horizontal walls block
            row = min(start_row, end_row)
            col = start_col
            candidates.extend([("h", (row, col)), ("h", (row, col - 1))])

        return [
            (orientation, position)
            for orientation, position in candidates
            if 0 <= position[0] < game.board_size - 1 and 0 <= position[1] < game.board_size - 1
        ]
