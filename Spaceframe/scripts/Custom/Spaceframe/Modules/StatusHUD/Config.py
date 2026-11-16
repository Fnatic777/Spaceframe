###############################################################################
#	Status HUD - Spaceframe module configuration
#
#	Edit with a text editor (Notepad++ recommended). Close the file in the
#	editor when you are done, so an old copy is not saved over it later.
###############################################################################

# 1 = show "Hull NN%" above the hull bar (on the right), for every ship.
ShowHull = 1

# 1 = for ships with ablative armor, show the white armor bar over the hull
#     bar and "Armor NN%" above it (on the left).
ShowArmor = 1

# 1 = also show this on the target's panel ("Target Shields").
ShowTarget = 1

# 1 = make the panels taller so the line does not overlap the ship picture:
#     the player's panel grows upwards, the target's panel grows downwards
#     and pushes the "Targets" list down if needed. 0 = original sizes.
ExpandDisplay = 1

# 1 = the other panels in the player's row (weapons, etc.) grow by the same
#     amount, so the whole row stays even. 0 = only the player's panel grows.
ExpandRow = 1

# How much each panel grows for the status line, as a percentage of the
# height of one text line. Smaller = more compact. The game already leaves
# some empty space between the ship picture and the hull bar, so values
# below 100 let the line use part of it; too small and it touches the
# picture.
# Player's panel:
PlayerLineSpace = 120
# Target's panel:
TargetLineSpace = 120

# Height of the armor bar, as a percentage of the hull bar height.
# 100 = exactly over the hull bar; 50 = top half only.
HudBarHeight = 100
