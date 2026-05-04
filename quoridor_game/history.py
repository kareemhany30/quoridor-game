from __future__ import annotations

from .engine import GameSnapshot, QuoridorGame


class GameHistory:
    def __init__(self, game: QuoridorGame) -> None:
        self.snapshots: list[GameSnapshot] = []
        self.index = 0
        self.reset(game)

    def reset(self, game: QuoridorGame) -> None:
        self.snapshots = [game.snapshot()]
        self.index = 0

    def record(self, game: QuoridorGame) -> None:
        self.snapshots = self.snapshots[: self.index + 1]
        self.snapshots.append(game.snapshot())
        self.index += 1

    def can_undo(self) -> bool:
        return self.index > 0

    def can_redo(self) -> bool:
        return self.index < len(self.snapshots) - 1

    def undo(self, game: QuoridorGame, skip_computer_reply: bool) -> bool:
        if not self.can_undo():
            return False

        steps = 2 if skip_computer_reply and self.index >= 2 else 1
        self.index = max(0, self.index - steps)
        game.restore(self.snapshots[self.index])
        return True

    def redo(self, game: QuoridorGame, skip_computer_reply: bool) -> bool:
        if not self.can_redo():
            return False

        steps = 2 if skip_computer_reply and self.index + 2 < len(self.snapshots) else 1
        self.index = min(len(self.snapshots) - 1, self.index + steps)
        game.restore(self.snapshots[self.index])
        return True
