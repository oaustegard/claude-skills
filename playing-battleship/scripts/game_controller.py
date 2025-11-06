#!/usr/bin/env python3
"""
Game controller for validating attacks and updating game state.
"""

import json
import sys
from pathlib import Path
from typing import Tuple


def load_game_state() -> dict:
    """Load current game state."""
    state_file = Path.home() / "battleship_game" / "game_state.json"
    with open(state_file, 'r') as f:
        return json.load(f)


def save_game_state(game_state: dict):
    """Save updated game state."""
    state_file = Path.home() / "battleship_game" / "game_state.json"
    with open(state_file, 'w') as f:
        json.dump(game_state, f, indent=2)


def load_claude_board() -> dict:
    """Load Claude's board (used only by Claude, never shown to human)."""
    board_file = Path.home() / "battleship_game" / "claude_board.json"
    with open(board_file, 'r') as f:
        return json.load(f)


def save_claude_board(board: dict):
    """Save updated Claude board."""
    board_file = Path.home() / "battleship_game" / "claude_board.json"
    with open(board_file, 'w') as f:
        json.dump(board, f, indent=2)


def validate_human_attack(cell: str) -> Tuple[str, str, bool]:
    """
    Process human's attack on Claude's board.
    Returns: (result, message, ship_sunk)
    """
    game_state = load_game_state()
    claude_board = load_claude_board()

    # Check if already attacked
    if cell in game_state["human_attacks"]:
        return "error", f"You already attacked {cell}!", False

    # Check if hit or miss
    hit_ship = None
    for ship in claude_board["ships"]:
        if cell in ship["cells"]:
            hit_ship = ship
            break

    if hit_ship:
        # Record hit
        hit_ship["hits"].append(cell)
        game_state["human_attacks"][cell] = "hit"

        # Check if ship is sunk
        if len(hit_ship["hits"]) == hit_ship["length"]:
            game_state["claude_ships_remaining"] -= 1
            save_claude_board(claude_board)
            save_game_state(game_state)
            return "sunk", f"HIT! You sank my {hit_ship['name']}!", True
        else:
            save_claude_board(claude_board)
            save_game_state(game_state)
            return "hit", f"HIT!", False
    else:
        # Miss
        game_state["human_attacks"][cell] = "miss"
        save_game_state(game_state)
        return "miss", "Miss.", False


def record_claude_attack(cell: str, result: str, ship_name: str = None):
    """
    Record Claude's attack result (reported by human).
    result: 'hit', 'miss', or 'sunk'
    """
    game_state = load_game_state()

    if result not in ["hit", "miss", "sunk"]:
        print(f"Error: Invalid result '{result}'. Must be 'hit', 'miss', or 'sunk'.")
        return

    game_state["claude_attacks"][cell] = result if result != "sunk" else "hit"

    if result == "sunk":
        game_state["human_ships_remaining"] -= 1
        game_state["last_move"] = f"Claude attacked {cell}: SUNK {ship_name}!"
    elif result == "hit":
        game_state["last_move"] = f"Claude attacked {cell}: HIT!"
    else:
        game_state["last_move"] = f"Claude attacked {cell}: Miss."

    save_game_state(game_state)
    print(f"✓ Claude's attack recorded: {cell} = {result}")


def check_game_over() -> Tuple[bool, str]:
    """Check if game is over and return winner."""
    game_state = load_game_state()

    if game_state["human_ships_remaining"] == 0:
        game_state["phase"] = "game_over"
        game_state["winner"] = "Claude"
        save_game_state(game_state)
        return True, "Claude"

    if game_state["claude_ships_remaining"] == 0:
        game_state["phase"] = "game_over"
        game_state["winner"] = "Human"
        save_game_state(game_state)
        return True, "Human"

    return False, None


def update_phase(new_phase: str):
    """Update game phase."""
    game_state = load_game_state()
    game_state["phase"] = new_phase

    if new_phase == "human_turn":
        game_state["turn_number"] += 1

    save_game_state(game_state)
    print(f"✓ Game phase updated to: {new_phase}")


def record_human_ships(ships_data: str):
    """Record human's ship placements (from artifact)."""
    game_state = load_game_state()

    try:
        ships = json.loads(ships_data)
        game_state["human_ships"] = ships
        game_state["phase"] = "human_turn"
        game_state["turn_number"] = 1
        game_state["last_move"] = "Both players ready. Human goes first!"
        save_game_state(game_state)
        print("✓ Human ships recorded. Game started!")
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON format: {e}")


def main():
    """CLI interface for game controller."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python game_controller.py human_attack <cell>")
        print("  python game_controller.py claude_attack <cell> <result> [ship_name]")
        print("  python game_controller.py record_ships '<json>'")
        print("  python game_controller.py check_winner")
        print("  python game_controller.py set_phase <phase>")
        return

    command = sys.argv[1]

    if command == "human_attack":
        cell = sys.argv[2].upper()
        result, message, sunk = validate_human_attack(cell)
        print(f"Result: {result}")
        print(f"Message: {message}")

        # Check for game over
        game_over, winner = check_game_over()
        if game_over:
            print(f"\n🎉 GAME OVER! {winner} wins!")

    elif command == "claude_attack":
        cell = sys.argv[2].upper()
        result = sys.argv[3].lower()
        ship_name = sys.argv[4] if len(sys.argv) > 4 else None
        record_claude_attack(cell, result, ship_name)

        # Check for game over
        game_over, winner = check_game_over()
        if game_over:
            print(f"\n🎉 GAME OVER! {winner} wins!")

    elif command == "record_ships":
        ships_json = sys.argv[2]
        record_human_ships(ships_json)

    elif command == "check_winner":
        game_over, winner = check_game_over()
        if game_over:
            print(f"Game over: {winner} wins!")
        else:
            print("Game still in progress.")

    elif command == "set_phase":
        phase = sys.argv[2]
        update_phase(phase)

    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
