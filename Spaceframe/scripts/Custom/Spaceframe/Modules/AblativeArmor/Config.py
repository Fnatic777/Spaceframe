###############################################################################
#	Ablative Armor - Spaceframe module configuration
#
#	Edit with a text editor (Notepad++ recommended). Close the file in the
#	editor when you are done, so an old copy is not saved over it later.
#	Timer interval, multiplayer and debug settings are in the core
#	configuration: scripts\Custom\Spaceframe\Config.py
###############################################################################

# Which ships have ablative armor is set in the Spaceframe ship list:
#     scripts\Custom\Spaceframe\Ships.py    (e.g. "Galaxy": {"AblativeArmor": Def})
# An old "Ships = {...}" list here is still accepted.

# Default armor capacity, as a percentage of the ship's hull. Used for ships
# set to Def in Ships.py. A ship can use its own value instead, e.g.
# "Sovereign": {"AblativeArmor": 80}.
DefaultArmor = 50

# How hard the armor is to repair, as a percentage of how hard the ship's
# own hull is to repair (its repair complexity, set by each ship, usually
# 1.0). 200 = twice as hard: the armor is repaired at half the hull's speed
# (complexity 1.0 -> 2.0; a ship with a 3.0 hull -> 6.0). Higher = slower.
# Regeneration uses the ship's repair rate, and is slower when the repair
# system is damaged. The armor waits while the hull is damaged: the hull is
# repaired first, then the armor.
ArmorComplexity = 200

# Bleed-through, like the game's shields: a worn armor lets part of each
# hit reach the hull and subsystems.
# BleedStart: armor level (percent) below which hits start to bleed
#   through. Above it, the armor stops everything.
# BleedMax: share of each hit (percent) that goes through when the armor
#   is empty. In between, it grows in a straight line.
# With 50 and 50: armor at 50% or more -> 0% goes through; 25% -> 25%;
# almost empty -> 50%. BleedMax = 0 turns bleed-through off.
# (Hull damage also pauses regeneration: the hull is repaired first.)
BleedStart = 50
BleedMax = 50

# Armor cost of subsystem damage, as a percentage of the cost of the same
# hull damage. 100 = the same; 50 = subsystem damage costs half as much.
SubsystemDamageCost = 50

# 1 = create a real "Ablative Armor" subsystem on the ship: it appears in the
#     damaged systems list and drives a live HUD bar (StatusHUD module).
#     If the game crashes when an armored ship enters the battle,
#     set this to 0 (internal armor, as in version 0.1).
CreateSubsystem = 1

# 1 = the armor subsystem is targetable, like the hull: it shows in the
#     game's subsystem lists, and enemies can aim at it (any damage the armor
#     takes directly is simply armor used up). 0 = not targetable.
Targetable = 1

# The armor bar and percentages on the HUD are drawn by the StatusHUD module:
#     scripts\Custom\Spaceframe\Modules\StatusHUD\Config.py
