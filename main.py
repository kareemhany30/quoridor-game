"""
Quoridor application entry point.

This script is the executable front door for the project. It imports
``QuoridorApp`` from the ``quoridor_game`` package, creates one instance, and
runs the Pygame main loop until the user closes the window.

Typical usage::

    python main.py

Dependencies (Pygame, etc.) are listed in ``requirements.txt`` at the project
root. All game logic and rendering live inside ``quoridor_game/``; this file
intentionally stays minimal so packaging and testing can target a single class.
"""

from quoridor_game.app import QuoridorApp  # Main Pygame application controller


def main() -> None:
    """
    Bootstrap the Quoridor client and enter the blocking game loop.

    Instantiates ``QuoridorApp`` (initializes Pygame, setup menu, and engine)
    then calls ``run()`` until quit.
    """
    app = QuoridorApp()  # Construct window, renderer, save manager, and default state
    app.run()  # Process events, AI turns, and drawing until the user exits


if __name__ == "__main__":  # True when executed as ``python main.py``, not when imported
    main()  # Start the game only when this file is the program entry point
