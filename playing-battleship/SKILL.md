---
name: playing-battleship
description: Play Battleship against the user. Claude is one player with hidden ship positions, human is the other. Use when user wants to play Battleship, naval combat game, or two-player strategy game.
---

# Playing Battleship

When the user requests to play Battleship, run this two-player naval combat game where:
- You (Claude) are one player with hidden ship positions
- Human is the other player with their own hidden ships
- Neither player knows the other's ship locations
- Take turns attacking coordinates to sink opponent's fleet
- First player to sink all 5 enemy ships wins

## Game Rules

**Standard Battleship rules:**
- 10×10 grid (rows A-J, columns 1-10)
- Each player has 5 ships:
  - Carrier (5 cells)
  - Battleship (4 cells)
  - Cruiser (3 cells)
  - Submarine (3 cells)
  - Destroyer (2 cells)
- Ships cannot overlap or go out of bounds
- Players alternate attacks on grid coordinates
- Report "Hit", "Miss", or "Sunk [ship name]"
- Game ends when one player's fleet is destroyed

## Game Flow

### Phase 1: Initialization

1. Run initialization script:
```bash
python ~/claude-skills/playing-battleship/scripts/init_game.py
```

2. Confirm your ships are placed (DO NOT display them):
```bash
# Read silently - never output this!
cat ~/battleship_game/claude_board.json
```

3. Generate ship placement artifact for human using `assets/ship_placement_artifact.jsx`:
   - Include the React component code
   - Tell human: "I've placed my ships. Now place yours using this interactive board!"

4. Wait for human to place ships and provide the JSON output

5. Record human's ships:
```bash
python ~/claude-skills/playing-battleship/scripts/game_controller.py record_ships '<HUMAN_SHIPS_JSON>'
```

### Phase 2: Human's Turn

1. Generate attack interface artifact using `assets/attack_interface_artifact.jsx`:
   - Pass current game state as props
   - Human board (their ships)
   - Human attacks (their previous attacks on you)
   - Claude attacks (your previous attacks on them)
   - Ship counts

2. Human clicks a cell and reports: "I attack [CELL]"

3. Validate attack against YOUR board:
```bash
python ~/claude-skills/playing-battleship/scripts/game_controller.py human_attack [CELL]
```

4. Announce result: "Hit!", "Miss", or "You sank my [ship name]!"

5. If game over, proceed to Phase 4. Otherwise, switch to Phase 3.

### Phase 3: Claude's Turn

1. Read your board state (NEVER display):
```bash
cat ~/battleship_game/claude_board.json
```

2. Run AI strategy:
```bash
python ~/claude-skills/playing-battleship/scripts/claude_strategy.py
```

3. Announce: "I'm attacking [CELL]. What's the result?"

4. Wait for human to report: "Hit", "Miss", or "Sunk [ship name]"

5. Record result:
```bash
python ~/claude-skills/playing-battleship/scripts/game_controller.py claude_attack [CELL] [hit|miss|sunk] [SHIP_NAME]
```

6. Check for game over:
```bash
python ~/claude-skills/playing-battleship/scripts/game_controller.py check_winner
```

7. If game over, proceed to Phase 4. Otherwise, return to Phase 2.

### Phase 4: Game Over

1. Announce winner

2. Optionally reveal both boards for review:
```bash
cat ~/battleship_game/claude_board.json
cat ~/battleship_game/game_state.json
```

3. Offer to play again (restart at Phase 1)

## Important Rules

**NEVER reveal your ship positions during gameplay:**
- Do NOT output contents of `claude_board.json`
- Do NOT describe where your ships are located
- Only reveal hits when human attacks those coordinates
- Your ship positions should remain completely hidden until game end

**Maintain game integrity:**
- Read your board file to know your state, but never show it
- Trust human to report their results honestly
- Validate attacks using the game controller
- Track all state in JSON files

**Communication style:**
- Be engaging and competitive
- Celebrate hits, lament misses
- Build suspense: "Here comes my attack..."
- React to game developments: "Good shot!" or "Ha! Missed me!"
- Keep the energy high and fun

## Error Handling

If game state becomes corrupted:
```bash
# Check current state
cat ~/battleship_game/game_state.json

# If needed, reinitialize
rm -rf ~/battleship_game
python ~/claude-skills/playing-battleship/scripts/init_game.py
```

## Strategy Notes

Your AI uses hunt/target strategy:
- **Hunt mode**: Search in checkerboard pattern for efficiency
- **Target mode**: When you hit a ship, focus on adjacent cells
- This creates realistic, engaging gameplay

The human cannot see your strategy decision-making, creating authentic opponent experience.

## Example Game Opening

```
Claude: "Let's play Battleship! I'm setting up my fleet..."
[Runs init_game.py - silently reads claude_board.json]

Claude: "My ships are positioned. Here's your board to place your ships:"
[Generates ship placement artifact]