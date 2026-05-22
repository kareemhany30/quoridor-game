"""
Quoridor Application Controller (Pygame front-end).

This module defines ``QuoridorApp``, the central coordinator between the user
interface (Pygame window, mouse, keyboard) and the rest of the Quoridor
package. It does not implement game rules itself; those live in
``quoridor_game.engine.QuoridorGame``. Instead, this file wires together:

- **Rendering** via ``QuoridorRenderer`` (board, setup menu, control panel).
- **Input** from mouse clicks and keyboard shortcuts.
- **Game flow** between the setup screen and an active match.
- **Persistence** through ``SaveManager`` (save/load JSON snapshots).
- **Move history** through ``GameHistory`` (undo/redo stacks).
- **Computer opponent** through ``ComputerPlayer`` when the user chooses
  Human vs Computer mode.

Lifecycle overview
------------------
1. ``main.py`` constructs ``QuoridorApp`` and calls ``run()``.
2. ``__init__`` initializes Pygame, creates subsystems, and shows the setup
   menu (``show_setup = True``).
3. Each frame in ``run()``: poll events → optionally let the AI move → draw
   → flip the display → cap frame rate at ``FPS``.

Screen modes
------------
- **Setup** (``show_setup``): user picks board size (7/9/11), opponent type
  (human or computer), then player count or difficulty before starting.
- **In-game**: user interacts with the board and bottom panel buttons; the
  computer acts automatically on its turn when enabled.

Human input model
-----------------
- **Move mode**: click own pawn to select, then click a highlighted legal
  destination; clicks outside the board clear selection.
- **Wall modes** (horizontal / vertical): click a wall slot on the board grid.
- **Panel buttons**: mode switches, undo, redo, reset, save, return to menu.
- **Keyboard**: mirrors many panel actions (M/H/V, U/Y, Ctrl+Z, Ctrl+S, R).

Computer turns
--------------
When ``play_against_computer`` is True, player index 1 is the AI. Each frame,
``_maybe_take_computer_turn`` checks whether it is the computer's turn; if so,
it waits briefly, asks ``ComputerPlayer`` for an action, applies it to the
engine, and records history. Human clicks are ignored during the AI turn.

State held on ``QuoridorApp``
-----------------------------
Match configuration (board size, player count, opponent, difficulty), UI mode
(move / wall_h / wall_v), pawn selection and legal-move hints, transient
``notice`` messages for save/load feedback, and references to geometry/button
layouts that update when board size changes.
"""

from __future__ import annotations  # Allow forward references in type hints without quotes

import sys  # Used to exit the process cleanly after pygame.quit()

import pygame  # Window, events, timing, and display for the game client

from .computer import ComputerPlayer  # AI opponent for Human vs Computer mode
from .engine import DEFAULT_BOARD_SIZE, DEFAULT_PLAYER_COUNT, Position, QuoridorGame  # Rules and state
from .history import GameHistory  # Undo/redo snapshot stacks
from .renderer import QuoridorRenderer  # All drawing for setup and in-game screens
from .save_manager import SaveManager  # JSON save/load of game snapshots
from .settings import (  # Shared constants and UI layout helpers
    BOARD_SIZE_OPTIONS,
    FPS,
    LEGACY_SAVE_FILES,
    SAVE_FILE,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    BoardGeometry,
    build_game_buttons,
    build_setup_buttons,
)


class QuoridorApp:
    """
    Main application object: owns Pygame resources, game state, and the event loop.

    Instantiate once from ``main.py``, then call ``run()`` to enter the blocking
    main loop until the user closes the window.
    """

    def __init__(self) -> None:
        """
        Initialize Pygame, subsystems, default match settings, and UI state.

        Starts on the setup menu with a placeholder ``QuoridorGame`` instance so
        geometry and history objects always have a valid board size to reference.
        """
        pygame.init()  # Start all Pygame modules required for display and input
        pygame.display.set_caption("Quoridor")  # Window title shown by the window manager

        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))  # Create the main window surface
        self.clock = pygame.time.Clock()  # Clock used to limit updates to FPS each frame
        self.renderer = QuoridorRenderer(self.screen)  # Drawing helper bound to the window surface
        self.save_manager = SaveManager(SAVE_FILE, LEGACY_SAVE_FILES)  # Read/write saves; support old filenames
        self.computer = ComputerPlayer()  # Strategy object that picks AI moves by difficulty

        self.selected_board_size = DEFAULT_BOARD_SIZE  # Board dimension chosen on setup (7, 9, or 11)
        self.selected_player_count = DEFAULT_PLAYER_COUNT  # 2 or 4 players for the next human match
        self.selected_opponent: str | None = None  # "human" or "computer"; None until user picks on setup
        self.play_against_computer = False  # True when player 2 is controlled by ComputerPlayer
        self.computer_difficulty: str | None = None  # "easy", "medium", or "hard" when vs computer
        self.show_setup = True  # True shows menu; False shows board and in-game panel
        self.notice = ""  # Short user-facing message (save/load errors or confirmations)

        self.game = QuoridorGame(self.selected_board_size, self.selected_player_count)  # Active rules engine
        self.geometry = BoardGeometry(self.game.board_size)  # Maps pixels to cells and wall slots
        self.buttons = build_game_buttons(self.geometry.panel_top)  # In-game panel button hit rectangles
        self.setup_buttons = build_setup_buttons()  # Setup menu button hit rectangles
        self.history = GameHistory(self.game)  # Undo/redo stacks seeded from initial game state

        self.mode = "move"  # Current action: "move", "wall_h", or "wall_v"
        self.selected_pawn = False  # True after user clicked their pawn awaiting destination
        self.legal_moves: list[Position] = []  # Destinations to highlight while pawn is selected

    def run(self) -> None:
        """
        Enter the main game loop until the process exits.

        Each iteration processes input, may execute one computer move, redraws
        the screen, presents the framebuffer, and sleeps to maintain ``FPS``.
        """
        while True:  # Run until pygame.QUIT triggers sys.exit in _handle_events
            self._handle_events()  # Drain keyboard and mouse events for this frame
            self._maybe_take_computer_turn()  # If AI's turn, apply one computer action
            self._draw()  # Paint either setup menu or active game to the screen surface
            pygame.display.flip()  # Show the newly drawn frame to the user
            self.clock.tick(FPS)  # Wait so the loop does not exceed the target frame rate

    def _handle_events(self) -> None:
        """
        Poll the Pygame event queue and dispatch quit, key, and mouse events.

        Quit closes the application. Key and left-click handlers route to
        specialized methods that respect setup vs in-game mode.
        """
        for event in pygame.event.get():  # Process every pending event once this frame
            if event.type == pygame.QUIT:  # User closed the window or OS requested exit
                pygame.quit()  # Shut down Pygame subsystems
                sys.exit()  # Terminate the Python process with a clean exit code
            if event.type == pygame.KEYDOWN:  # A key was pressed (not released)
                self._handle_key(event)  # Route to keyboard shortcuts for in-game actions
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:  # Left mouse button down
                self._handle_click(event.pos)  # Route click to setup or board/panel logic

    def _handle_key(self, event: pygame.event.Event) -> None:
        """
        Handle keyboard shortcuts during an active match (not on setup screen).

        Supports undo/redo (U, Y, Ctrl+Z, Ctrl+Y, Ctrl+Shift+Z), save (Ctrl+S),
        reset (R), and mode switches (M, H, V). Setup screen ignores keys.
        """
        if self.show_setup:  # Menu has no keyboard bindings; only mouse selects options
            return

        key = event.key  # Integer key code for the key that was pressed
        ctrl_pressed = bool(pygame.key.get_mods() & pygame.KMOD_CTRL)  # True if Ctrl held with this key
        shift_pressed = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)  # True if Shift held with this key

        if ctrl_pressed and key == pygame.K_z and shift_pressed:  # Ctrl+Shift+Z: redo (common on macOS/Linux)
            self._redo()
        elif ctrl_pressed and key == pygame.K_z:  # Ctrl+Z: undo
            self._undo()
        elif ctrl_pressed and key == pygame.K_s:  # Ctrl+S: save current match to disk
            self._save_game()
        elif ctrl_pressed and key == pygame.K_y:  # Ctrl+Y: redo (Windows-style)
            self._redo()
        elif key == pygame.K_u:  # U: undo without modifier
            self._undo()
        elif key == pygame.K_y:  # Y: redo without modifier
            self._redo()

        if key == pygame.K_r:  # R: reset board to starting position for current settings
            self._reset_game()
        elif key == pygame.K_m:  # M: switch to pawn move mode
            self._set_mode("move")
        elif key == pygame.K_h:  # H: switch to horizontal wall placement mode
            self._set_mode("wall_h")
        elif key == pygame.K_v:  # V: switch to vertical wall placement mode
            self._set_mode("wall_v")

    def _handle_click(self, mouse_pos: tuple[int, int]) -> None:
        """
        Dispatch a left-click to setup UI, panel buttons, or board interaction.

        Priority: setup menu → in-game buttons → ignore if computer turn →
        move or wall handler based on ``self.mode``.
        """
        if self.show_setup:  # Clicks on the main menu before a match starts
            self._handle_setup_click(mouse_pos)
            return

        clicked_button = self._clicked_game_button(mouse_pos)  # Check if click hit a panel button
        if clicked_button is not None:  # Panel button takes precedence over board clicks
            self._handle_game_button(clicked_button)
            return

        if self._is_computer_turn():  # Human cannot act while AI is thinking / moving
            return

        if self.mode == "move":  # Two-step pawn selection and move to legal cell
            self._handle_move_click(mouse_pos)
            return

        if self.mode in {"wall_h", "wall_v"}:  # Place a wall on the clicked slot if valid
            self._handle_wall_click(mouse_pos)

    def _clicked_game_button(self, mouse_pos: tuple[int, int]) -> str | None:
        """
        Return the name of the in-game panel button under ``mouse_pos``, if any.

        Button names match keys in ``self.buttons`` (e.g. "move", "undo", "menu").
        Returns ``None`` when the click is not on a panel control.
        """
        for name, rect in self.buttons.items():  # Test each panel button rectangle in turn
            if rect.collidepoint(mouse_pos):  # Point-in-rectangle hit test in screen coordinates
                return name  # First matching button wins
        return None  # Click was on the board or empty panel area

    def _handle_game_button(self, name: str) -> None:
        """
        Execute the action for a panel button identified by ``name``.

        Reset, menu, undo, redo, and save work on any turn. Mode buttons
        (move, wall_h, wall_v) are ignored during the computer's turn.
        """
        if name == "reset":  # Start a fresh game with same size, players, and opponent settings
            self._reset_game()
        elif name == "menu":  # Leave match and return to setup screen
            self._return_to_menu()
        elif name == "undo":  # Step back one ply in history (with computer skip rules)
            self._undo()
        elif name == "redo":  # Step forward one ply if available
            self._redo()
        elif name == "save":  # Persist snapshot and mode metadata to JSON
            self._save_game()
        elif not self._is_computer_turn():  # Mode buttons only when human may act
            self._set_mode(name)  # name is "move", "wall_h", or "wall_v"

    def _handle_setup_click(self, mouse_pos: tuple[int, int]) -> None:
        """
        Handle mouse input on the setup / main menu screen.

        Supports load saved game, board size tiles, opponent type (human vs
        computer), then delegates to human or computer sub-flow for final choice.
        """
        if self.setup_buttons["load"].collidepoint(mouse_pos):  # Resume last saved match from disk
            self._load_game()
            return

        for board_size in BOARD_SIZE_OPTIONS:  # User may pick 7x7, 9x9, or 11x11
            if self.setup_buttons[f"size_{board_size}"].collidepoint(mouse_pos):
                self.selected_board_size = board_size  # Store choice for next _start_match
                self.notice = ""  # Clear stale messages when changing size
                return

        if self.setup_buttons["human"].collidepoint(mouse_pos):  # Local multiplayer path
            self.selected_opponent = "human"
            return

        if self.setup_buttons["computer"].collidepoint(mouse_pos):  # AI opponent path (always 2 players)
            self.selected_opponent = "computer"
            self.selected_player_count = 2  # Computer mode does not support 4-player
            return

        if self.selected_opponent == "human":  # After opponent chosen, pick 2 or 4 players
            self._handle_human_setup_choice(mouse_pos)
        elif self.selected_opponent == "computer":  # After opponent chosen, pick easy/medium/hard
            self._handle_computer_setup_choice(mouse_pos)

    def _handle_human_setup_choice(self, mouse_pos: tuple[int, int]) -> None:
        """
        Start a local human-vs-human match when 2 Players or 4 Players is clicked.

        Only reacts when the corresponding setup button is hit; does nothing
        otherwise so other setup clicks can be handled elsewhere.
        """
        for player_count in (2, 4):  # Supported player counts from engine.WALLS_BY_PLAYER_COUNT
            if self.setup_buttons[f"players_{player_count}"].collidepoint(mouse_pos):
                self._start_match(play_against_computer=False, player_count=player_count)
                return

    def _handle_computer_setup_choice(self, mouse_pos: tuple[int, int]) -> None:
        """
        Start a human-vs-computer match when a difficulty button is clicked.

        Difficulty is passed to ``ComputerPlayer.choose_action`` for the whole
        match. Player count is fixed at 2.
        """
        for difficulty in ("easy", "medium", "hard"):  # Labels match setup button keys and AI logic
            if self.setup_buttons[difficulty].collidepoint(mouse_pos):
                self._start_match(play_against_computer=True, difficulty=difficulty, player_count=2)
                return

    def _handle_move_click(self, mouse_pos: tuple[int, int]) -> None:
        """
        Implement two-click pawn movement for the current human player.

        First click on own pawn selects it and loads legal moves for highlighting.
        Second click on a legal cell applies the move; click on own pawn again
        deselects; click off-board clears selection.
        """
        if self.game.winner is not None:  # Match over; no further moves allowed
            return

        cell = self.geometry.cell_at(mouse_pos)  # Convert pixel position to board (row, col) or None
        if cell is None:  # Click outside the grid
            self._clear_selection()
            return

        if not self.selected_pawn:  # First click: try to select the current player's pawn
            self._select_pawn_if_current_player(cell)
            return

        if cell == self.game.current_player.pawn:  # Second click on same cell: cancel selection
            self._clear_selection()
            return

        if self.game.move_pawn(cell):  # Engine validates and applies move; advances turn if legal
            self._after_player_action()  # Push history snapshot and clear selection hints
        else:
            self._clear_selection()  # Illegal destination: drop selection so user can retry

    def _select_pawn_if_current_player(self, cell: Position) -> None:
        """
        Select the current player's pawn at ``cell`` and compute legal destinations.

        Only succeeds when ``cell`` equals the active player's pawn position;
        otherwise selection state is unchanged.
        """
        if cell != self.game.current_player.pawn:  # Ignore clicks on empty cells or opponent pawns
            return

        self.selected_pawn = True  # UI will draw move hints on legal destination cells
        self.legal_moves = self.game.legal_moves_for_current_player()  # List of valid (row, col) targets

    def _handle_wall_click(self, mouse_pos: tuple[int, int]) -> None:
        """
        Place a horizontal or vertical wall at the wall slot under the cursor.

        Orientation follows ``self.mode`` (wall_h → "h", wall_v → "v"). Invalid
        placements are rejected by the engine without recording history.
        """
        orientation = "h" if self.mode == "wall_h" else "v"  # Map UI mode to engine orientation string
        slot = self.geometry.wall_slot_at(mouse_pos, orientation)  # Nearest wall grid coordinate or None
        if slot is not None and self.game.place_wall(orientation, slot):  # Rules check overlap, path, etc.
            self._after_player_action()  # Record successful wall in undo stack

    def _after_player_action(self) -> None:
        """
        Common post-move hook after a successful human pawn move or wall placement.

        Snapshots game state for undo/redo and clears pawn selection so the next
        turn starts in a neutral UI state.
        """
        self.history.record(self.game)  # Push current engine state onto the undo stack
        self._clear_selection()  # Hide move hints until the player selects again

    def _reset_game(self) -> None:
        """
        Restart the current match in place without returning to the setup menu.

        Preserves board size, player count, and computer settings; renames player 2
        if needed; clears history and UI selection.
        """
        self.game.reset()  # Engine returns pawns, walls, turn, and winner to initial state
        self.game.players[1].name = self._player_two_name()  # Restore "Player 2" or "Computer (Hard)" label
        self._refresh_board_layout()  # Rebuild button rects if board size unchanged (no-op for size)
        self.history.reset(self.game)  # Single fresh snapshot; undo/redo disabled until moves made
        self._reset_play_state()  # Default to move mode with no pawn selected
        self.notice = ""  # Clear save/load banners after reset

    def _start_match(
        self,
        play_against_computer: bool,
        difficulty: str | None = None,
        player_count: int = DEFAULT_PLAYER_COUNT,
    ) -> None:
        """
        Leave setup and begin a new match with the chosen options.

        Creates a new ``QuoridorGame``, configures AI flags, refreshes layout and
        history, and switches ``show_setup`` off so ``run()`` draws the board.
        """
        self.show_setup = False  # Transition from menu to in-game view
        self.play_against_computer = play_against_computer  # Whether player index 1 is AI-controlled
        self.computer_difficulty = difficulty  # None for human matches; otherwise easy/medium/hard
        self.selected_player_count = 2 if play_against_computer else player_count  # AI always uses 2 players
        self.game = QuoridorGame(self.selected_board_size, self.selected_player_count)  # New rules state
        self.game.players[1].name = self._player_two_name()  # Display name for second player on panel
        self._refresh_board_layout()  # Cell size and button positions depend on board_size
        self.history.reset(self.game)  # Undo stack starts at opening position
        self._reset_play_state()  # Move mode, no selection
        self.notice = ""  # Fresh match has no status banner from prior save/load

    def _return_to_menu(self) -> None:
        """
        Abandon the current match UI and show the setup screen again.

        Does not change ``selected_board_size`` or ``selected_player_count``;
        clears opponent/difficulty flags and replaces ``game`` with a idle instance
        so geometry remains valid while on the menu.
        """
        self.show_setup = True  # Next _draw() call renders setup instead of the board
        self.selected_opponent = None  # User must pick human or computer again to start
        self.play_against_computer = False
        self.computer_difficulty = None
        self.game = QuoridorGame(self.selected_board_size, self.selected_player_count)  # Placeholder game
        self._refresh_board_layout()  # Keep geometry consistent with selected board size
        self.history.reset(self.game)  # Discard match history from the session
        self._reset_play_state()
        self.notice = ""

    def _refresh_board_layout(self) -> None:
        """
        Recompute pixel layout and panel button rectangles for the current board size.

        Called after board size changes, load game, reset, start match, or return
        to menu so hit-testing stays aligned with drawn cells and walls.
        """
        self.geometry.update(self.game.board_size)  # Recalculate cell size and panel_top from board_size
        self.buttons = build_game_buttons(self.geometry.panel_top)  # Panel Y depends on board height

    def _reset_play_state(self) -> None:
        """
        Reset transient UI state used during a turn (mode and pawn selection).

        Does not modify engine rules state; only clears how the human interacts
        with the board until they click again.
        """
        self.mode = "move"  # Default action after reset, undo, redo, or computer move
        self._clear_selection()

    def _set_mode(self, mode: str) -> None:
        """
        Switch the active human action mode and drop any in-progress pawn selection.

        ``mode`` is typically "move", "wall_h", or "wall_v" from buttons or keys.
        """
        self.mode = mode
        self._clear_selection()  # Wall mode and move mode are mutually exclusive for selection UI

    def _clear_selection(self) -> None:
        """
        Deselect the pawn and remove legal-move highlights from the renderer.

        Safe to call repeatedly; used after moves, invalid clicks, and mode changes.
        """
        self.selected_pawn = False
        self.legal_moves = []

    def _save_game(self) -> None:
        """
        Serialize the current match to the configured save file via ``SaveManager``.

        On success, sets ``notice`` with the filename; on I/O failure, shows an
        error message and leaves disk state unchanged.
        """
        try:
            self.save_manager.save(
                self.game.snapshot(),  # Immutable copy of board, players, walls, turn, winner
                self.play_against_computer,  # Restored on load to re-enable AI
                self.computer_difficulty,  # Restored on load for AI strength
            )
        except OSError:  # Disk full, permission denied, or missing parent directory
            self.notice = "Could not save game"
            return

        self.notice = f"Game saved to {SAVE_FILE.name}"  # Brief confirmation using filename only

    def _load_game(self) -> None:
        """
        Load the most recent save file and resume play from that snapshot.

        Validates file contents through ``SaveManager``; on failure sets an error
        ``notice`` and leaves current state unchanged. On success, rebuilds game,
        history, layout, and opponent flags from saved metadata.
        """
        if not self.save_manager.exists():  # No primary or legacy save file on disk
            self.notice = "No saved game found"
            return

        try:
            loaded_game = self.save_manager.load()  # Parsed snapshot plus computer/human flags
        except (OSError, TypeError, ValueError):  # Missing file, corrupt JSON, or invalid fields
            self.notice = "Saved game could not be loaded"
            return

        snapshot = loaded_game.snapshot  # Frozen dataclass from save_manager
        self.game = QuoridorGame(snapshot.board_size, len(snapshot.players))  # Empty engine sized to save
        self.game.restore(snapshot)  # Apply players, walls, turn, winner, move history from file
        self.selected_board_size = snapshot.board_size  # Keep menu default aligned with loaded game
        self.selected_player_count = len(snapshot.players)
        self.show_setup = False  # Jump straight into the loaded position on the board
        self.play_against_computer = loaded_game.play_against_computer
        self.computer_difficulty = loaded_game.computer_difficulty
        self.selected_opponent = "computer" if self.play_against_computer else "human"
        self._refresh_board_layout()
        self.history.reset(self.game)  # Undo stack starts at loaded position only
        self._reset_play_state()
        self.notice = "Loaded saved game"

    def _can_undo(self) -> bool:
        """
        Report whether undo is available for the renderer to enable/disable the button.

        Delegates to ``GameHistory``; does not modify state.
        """
        return self.history.can_undo()

    def _can_redo(self) -> bool:
        """
        Report whether redo is available for the renderer to enable/disable the button.

        Delegates to ``GameHistory``; does not modify state.
        """
        return self.history.can_redo()

    def _undo(self) -> None:
        """
        Revert one ply using ``GameHistory``, with special handling vs computer.

        When playing the computer and it is the human's turn, undo also skips
        the computer's reply move so the human returns to their previous decision
        point. Switches to move mode on success.
        """
        skip_computer_reply = self.play_against_computer and self.game.current_turn == 0  # Human (P1) to move
        if self.history.undo(self.game, skip_computer_reply):  # May pop one or two snapshots
            self._set_mode("move")  # After undo, default to pawn movement

    def _redo(self) -> None:
        """
        Replay one previously undone ply, with the same computer skip rules as undo.

        See ``_undo`` for ``skip_computer_reply`` behavior in AI matches.
        """
        skip_computer_reply = self.play_against_computer and self.game.current_turn == 0
        if self.history.redo(self.game, skip_computer_reply):
            self._set_mode("move")

    def _player_two_name(self) -> str:
        """
        Return the display label for player index 1 on the status panel.

        Human matches use "Player 2"; computer matches include the difficulty
        in the name, e.g. "Computer (Hard)".
        """
        if not self.play_against_computer or self.computer_difficulty is None:
            return "Player 2"
        return f"Computer ({self.computer_difficulty.title()})"  # title() → "Easy", "Medium", "Hard"

    def _is_computer_turn(self) -> bool:
        """
        Return True when the AI should act and human board input must be blocked.

        Requires computer mode, player 1's turn (index 1), and no winner yet.
        """
        return self.play_against_computer and self.game.current_turn == 1 and self.game.winner is None

    def _maybe_take_computer_turn(self) -> None:
        """
        If it is the computer's turn, pause briefly, choose and apply one AI action.

        Called every frame from ``run()``; only does work when ``_is_computer_turn``
        is True. Records history on success and resets UI selection so the human
        sees a clean board on their next turn. Uses a fixed delay for readability.
        """
        if not self._is_computer_turn():  # Human turn or game over: nothing to do
            return

        pygame.time.delay(220)  # Short pause so the AI move is visible and not instantaneous
        action = self.computer.choose_action(self.game, self.computer_difficulty)  # ("move", pos) or wall tuple
        played = False  # Track whether engine accepted the AI action
        if action[0] == "move":  # AI chose to advance its pawn
            played = self.game.move_pawn(action[1])
        else:  # AI chose to place a wall: action is ("wall", orientation, position)
            orientation, position = action[1], action[2]
            played = self.game.place_wall(orientation, position)

        if played:  # Only snapshot state that the rules accepted
            self.history.record(self.game)
        self._reset_play_state()  # Clear any stale human selection after AI acts

    def _draw(self) -> None:
        """
        Render the current frame to ``self.screen`` (setup menu or active game).

        Does not call ``pygame.display.flip``; ``run()`` flips after this returns.
        Passes undo/redo availability so the renderer can dim disabled buttons.
        """
        if self.show_setup:  # Main menu: size, opponent, load, and follow-up choices
            self.renderer.draw_setup(
                self.setup_buttons,
                self.selected_board_size,
                self.selected_opponent,
                self.notice,
            )
            return

        self.renderer.draw_game(  # Board, walls, pawns, hints, panel, and notice
            self.game,
            self.geometry,
            self.buttons,
            self.mode,
            self.selected_pawn,
            self.legal_moves,
            self.notice,
            self._can_undo(),
            self._can_redo(),
        )
