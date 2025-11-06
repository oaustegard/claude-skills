#!/usr/bin/env python3
"""
Claude's AI strategy for Battleship attacks.
Uses hunt/target mode: random hunting until hit, then targeting adjacent cells.
"""

import json
import random
from pathlib import Path
from typing import List, Tuple, Optional

ROWS = "ABCDEFGHIJ"
COLS = range(1, 11)


def load_game_state() -> dict:
    """Load current game state."""
    state_file = Path.home() / "battleship_game" / "game_state.json"
    with open(state_file, 'r') as f:
        return json.load(f)


def cell_to_coords(cell: str) -> Tuple[int, int]:
    """Convert cell notation to coordinates."""
    row = ROWS.index(cell[0])
    col = int(cell[1:]) - 1
    return row, col


def coords_to_cell(row: int, col: int) -> str:
    """Convert coordinates to cell notation."""
    return f"{ROWS[row]}{col + 1}"


def get_unattacked_cells(game_state: dict) -> List[str]:
    """Get list of cells Claude hasn't attacked yet."""
    all_cells = [f"{row}{col}" for row in ROWS for col in range(1, 11)]
    attacked = set(game_state["claude_attacks"].keys())
    return [cell for cell in all_cells if cell not in attacked]


def get_adjacent_cells(cell: str) -> List[str]:
    """Get orthogonally adjacent cells (up, down, left, right)."""
    row, col = cell_to_coords(cell)
    adjacent = []

    # Up, Down, Left, Right
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        new_row, new_col = row + dr, col + dc
        if 0 <= new_row < 10 and 0 <= new_col < 10:
            adjacent.append(coords_to_cell(new_row, new_col))

    return adjacent


def get_targeting_candidates(game_state: dict) -> List[str]:
    """Get cells adjacent to recent hits that haven't been attacked."""
    candidates = []
    attacks = game_state["claude_attacks"]

    # Find all hits
    hits = [cell for cell, result in attacks.items() if result == "hit"]

    # Get adjacent cells for each hit
    for hit_cell in hits:
        for adj_cell in get_adjacent_cells(hit_cell):
            if adj_cell not in attacks and adj_cell not in candidates:
                candidates.append(adj_cell)

    return candidates


def get_checkerboard_cells(unattacked: List[str]) -> List[str]:
    """
    Get cells in checkerboard pattern for efficient hunting.
    Since smallest ship is length 2, we can skip every other cell.
    """
    checkerboard = []
    for cell in unattacked:
        row, col = cell_to_coords(cell)
        # Checkerboard: (row + col) is even
        if (row + col) % 2 == 0:
            checkerboard.append(cell)
    return checkerboard if checkerboard else unattacked


def choose_attack(game_state: dict) -> str:
    """
    Choose next cell to attack using hunt/target strategy.

    Target mode: If there are recent hits, attack adjacent cells.
    Hunt mode: Attack in checkerboard pattern for efficiency.
    """
    # Target mode: prioritize cells adjacent to hits
    targeting = get_targeting_candidates(game_state)
    if targeting:
        return random.choice(targeting)

    # Hunt mode: use checkerboard pattern
    unattacked = get_unattacked_cells(game_state)
    if not unattacked:
        raise RuntimeError("No cells left to attack!")

    checkerboard = get_checkerboard_cells(unattacked)
    return random.choice(checkerboard)


def explain_strategy(attack_cell: str, game_state: dict) -> str:
    """Generate a narrative explanation of Claude's strategy."""
    targeting = get_targeting_candidates(game_state)

    if targeting and attack_cell in targeting:
        return f"I'm targeting near my recent hits. Attacking {attack_cell}."
    else:
        return f"I'm hunting with a search pattern. Attacking {attack_cell}."


def main():
    """Choose Claude's next attack and explain reasoning."""
    game_state = load_game_state()

    if game_state["phase"] != "claude_turn":
        print(f"Error: Not Claude's turn. Current phase: {game_state['phase']}")
        return

    attack = choose_attack(game_state)
    explanation = explain_strategy(attack, game_state)

    print(f"Attack: {attack}")
    print(f"Strategy: {explanation}")


if __name__ == "__main__":
    main()
