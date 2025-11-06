#!/usr/bin/env python3
"""
Initialize a new Battleship game with Claude's random ship placement.
"""

import json
import random
from pathlib import Path
from typing import List, Tuple, Set

BOARD_SIZE = 10
ROWS = "ABCDEFGHIJ"
COLS = range(1, 11)

SHIPS = [
    {"name": "Carrier", "length": 5},
    {"name": "Battleship", "length": 4},
    {"name": "Cruiser", "length": 3},
    {"name": "Submarine", "length": 3},
    {"name": "Destroyer", "length": 2}
]


def cell_to_coords(cell: str) -> Tuple[int, int]:
    """Convert cell notation (e.g., 'A1') to coordinates (0, 0)."""
    row = ROWS.index(cell[0])
    col = int(cell[1:]) - 1
    return row, col


def coords_to_cell(row: int, col: int) -> str:
    """Convert coordinates to cell notation."""
    return f"{ROWS[row]}{col + 1}"


def get_ship_cells(row: int, col: int, length: int, horizontal: bool) -> List[str]:
    """Get list of cells occupied by a ship."""
    cells = []
    for i in range(length):
        if horizontal:
            cells.append(coords_to_cell(row, col + i))
        else:
            cells.append(coords_to_cell(row + i, col))
    return cells


def is_valid_placement(row: int, col: int, length: int, horizontal: bool, occupied: Set[str]) -> bool:
    """Check if ship placement is valid (in bounds and doesn't overlap)."""
    if horizontal:
        if col + length > BOARD_SIZE:
            return False
    else:
        if row + length > BOARD_SIZE:
            return False

    cells = get_ship_cells(row, col, length, horizontal)
    return not any(cell in occupied for cell in cells)


def place_ship_randomly(length: int, occupied: Set[str]) -> List[str]:
    """Place a ship randomly on the board, avoiding occupied cells."""
    max_attempts = 1000
    for _ in range(max_attempts):
        horizontal = random.choice([True, False])
        row = random.randint(0, BOARD_SIZE - 1)
        col = random.randint(0, BOARD_SIZE - 1)

        if is_valid_placement(row, col, length, horizontal, occupied):
            cells = get_ship_cells(row, col, length, horizontal)
            return cells

    raise RuntimeError(f"Could not place ship of length {length} after {max_attempts} attempts")


def generate_claude_board() -> dict:
    """Generate Claude's random ship placement."""
    occupied = set()
    ships = []

    for ship in SHIPS:
        cells = place_ship_randomly(ship["length"], occupied)
        occupied.update(cells)
        ships.append({
            "name": ship["name"],
            "length": ship["length"],
            "cells": cells,
            "hits": []
        })

    return {"ships": ships}


def init_game_state() -> dict:
    """Initialize empty game state."""
    return {
        "phase": "setup",
        "turn_number": 0,
        "current_turn": "human",
        "human_attacks": {},
        "claude_attacks": {},
        "human_ships_remaining": 5,
        "claude_ships_remaining": 5,
        "winner": None,
        "last_move": "Game started. Human needs to place ships.",
        "human_ships": []
    }


def main():
    """Initialize game files."""
    # Create game directory
    game_dir = Path.home() / "battleship_game"
    game_dir.mkdir(exist_ok=True)

    # Generate Claude's board
    claude_board = generate_claude_board()
    claude_file = game_dir / "claude_board.json"
    with open(claude_file, 'w') as f:
        json.dump(claude_board, f, indent=2)

    print(f"✓ Claude's board created at {claude_file}")
    print(f"  Ships placed: {', '.join(ship['name'] for ship in claude_board['ships'])}")

    # Initialize game state
    game_state = init_game_state()
    state_file = game_dir / "game_state.json"
    with open(state_file, 'w') as f:
        json.dump(game_state, f, indent=2)

    print(f"✓ Game state initialized at {state_file}")
    print(f"\nGame ready! Phase: {game_state['phase']}")
    print("Next step: Human needs to place ships using the setup artifact.")


if __name__ == "__main__":
    main()
