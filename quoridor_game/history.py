"""
Game history manager for undo and redo.

This module provides ``GameHistory``, a linear stack of immutable ``GameSnapshot``
objects from ``quoridor_game.engine``. Each time a player (or the computer)
completes a legal action, ``QuoridorApp`` calls ``record()`` to append the new
state. Undo/redo move an index backward or forward and restore the corresponding
snapshot into the live ``QuoridorGame``.

Computer-match behavior
-----------------------
When playing against the computer, undoing on the human's turn should skip both
the human's last move and the computer's reply. ``undo`` and ``redo`` accept
``skip_computer_reply``: when True and enough history exists, they step by two
snapshots instead of one. ``QuoridorApp`` sets this flag when it is player 0's
turn in a computer game.

Design notes
------------
- Branching is discarded: recording after undo truncates snapshots after the
  current index (standard undo-stack semantics).
- ``reset`` seeds the stack with a single snapshot (opening or loaded position).
"""

from __future__ import annotations  # Postponed evaluation of type hints in annotations

from .engine import GameSnapshot, QuoridorGame  # Immutable state copies and live rules engine


class GameHistory:
    """
    Maintain a timeline of ``GameSnapshot`` instances for undo/redo.

    The ``index`` points at the snapshot currently reflected in the attached
    ``QuoridorGame`` after the last successful undo, redo, or record.
    """

    def __init__(self, game: QuoridorGame) -> None:
        """
        Create an empty history and seed it from the given game's current state.

        Typically called when ``QuoridorApp`` constructs or replaces ``game``.
        """
        self.snapshots: list[GameSnapshot] = []  # Ordered timeline of board states
        self.index = 0  # Current position in snapshots (0 = oldest)
        self.reset(game)  # Initialize with one snapshot so undo is disabled until moves occur

    def reset(self, game: QuoridorGame) -> None:
        """
        Replace history with a single snapshot of ``game`` (opening or load).

        Clears redo branch and sets ``index`` to 0.
        """
        self.snapshots = [game.snapshot()]  # Deep-enough copy via engine snapshot API
        self.index = 0  # Point at the only snapshot

    def record(self, game: QuoridorGame) -> None:
        """
        Append a new snapshot after a successful move or wall placement.

        Truncates any snapshots after ``index`` so redo history is invalidated
        when the user makes a new move after undoing.
        """
        self.snapshots = self.snapshots[: self.index + 1]  # Drop redo branch
        self.snapshots.append(game.snapshot())  # Store post-action state
        self.index += 1  # Advance cursor to the new tip

    def can_undo(self) -> bool:
        """
        Return whether at least one earlier snapshot exists.

        Used by the renderer to enable or dim the Undo button.
        """
        return self.index > 0  # Index 0 is the root; cannot go before it

    def can_redo(self) -> bool:
        """
        Return whether snapshots exist after the current index.

        Used by the renderer to enable or dim the Redo button.
        """
        return self.index < len(self.snapshots) - 1  # More snapshots ahead on the stack

    def undo(self, game: QuoridorGame, skip_computer_reply: bool) -> bool:
        """
        Restore an earlier snapshot into ``game``.

        ``skip_computer_reply``: when True and ``index >= 2``, move back two steps
        (human + computer ply in AI matches). Returns False if undo is impossible.
        """
        if not self.can_undo():  # Already at oldest snapshot
            return False

        steps = 2 if skip_computer_reply and self.index >= 2 else 1  # Double-step for AI reply
        self.index = max(0, self.index - steps)  # Never go below 0
        game.restore(self.snapshots[self.index])  # Apply frozen state to live engine
        return True

    def redo(self, game: QuoridorGame, skip_computer_reply: bool) -> bool:
        """
        Restore a later snapshot into ``game`` after a prior undo.

        Mirrors ``undo`` with forward steps; returns False if redo is impossible.
        """
        if not self.can_redo():  # Already at newest snapshot
            return False

        steps = 2 if skip_computer_reply and self.index + 2 < len(self.snapshots) else 1
        self.index = min(len(self.snapshots) - 1, self.index + steps)  # Clamp to tip
        game.restore(self.snapshots[self.index])
        return True
