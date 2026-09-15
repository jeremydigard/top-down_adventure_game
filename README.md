# Adventure 2D

A top-down adventure game in which you explore maps, collect crystals, avoid hazards, activate levers, and progress from level to level.

## Starting the Game

From the project root folder, simply run:

```bash
python main.py
```

The game will load the default map.
You can also launch a specific map:

```bash
python main.py maps/map1.txt
```

## Objective

Your goal is to traverse the map, survive enemies and traps, collect as many crystals as possible, and reach the exit when one is available.

Some maps are linked together: touching the exit automatically loads the next map.

## Controls

- Arrow keys: Move the character
- `D`: Use the active weapon
- `R`: Switch weapon
- `ESC`: Restart the current map
- `H`: Toggle hitboxes display on/off (useful for navigation and debugging)

## Weapons

You have two weapons at your disposal:

- The **boomerang**, which flies in the player's facing direction and then returns
- The **sword**, which strikes around the player for a brief moment

Switch active weapons using `R`.
Trigger an attack using `D`.

## Objects and Map Elements

### Scenery and Obstacles

- **Ground**: Walkable area
- **Bush / Wall**: Blocks movement
- **Hole / Pit**: Fatal hazard if you get too close

### Collectibles

- **Crystal**: Increases the score and plays a collection sound

### Progression Mechanics

- **Lever**: Interactive object that toggles its state when struck by a weapon
- **Gate**: Can open or close depending on the state of one or more levers
- **Exit**: Allows progression to the next map when available

### Enemies

- **Horizontal Spinner**: Moves left and right between obstacles
- **Vertical Spinner**: Moves up and down between obstacles
- **Bat**: Moves unpredictably
- **Blob**: Chases the player upon spotting them

All enemies deal damage on contact.

## Core Mechanics

- Navigate without colliding with obstacles
- Avoid enemies and pits
- Collect crystals to increase your score
- Use the boomerang or sword to interact with the world
- Activate levers to open specific gates
- Reach the exit to advance to the next map

## Key Interactions

- Colliding with an enemy inflicts damage
- If your health bar drops to zero, the current map restarts
- Both the sword and the boomerang can trigger levers
- The sword can also hit enemies and collect crystals
- The boomerang automatically returns after its flight range or after a valid impact

## Custom Features

### Health Bar

The game is not limited to instant death:

- You have a **health bar**
- Certain hazards reduce health instead of causing instant death
- Remaining health is displayed directly on the HUD

This allows for a smoother exploration curve and gives the player room for error.

### Chained Map Loading

We added a progression system linking multiple maps together:

- A map can specify the next one in sequence
- The exit only appears if a subsequent map exists
- Reaching the exit automatically loads the next level
- File paths are handled to maintain consistent transitions between levels

## On-Screen HUD

In-game, you will see:

- The current score
- The health bar
- An FPS counter

## HAVE FUN!
