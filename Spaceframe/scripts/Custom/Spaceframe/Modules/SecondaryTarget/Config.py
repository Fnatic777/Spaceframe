###############################################################################
#	Secondary Target - Spaceframe module configuration
#
#	Edit with a text editor (Notepad++ recommended). Close the file in the
#	editor when you are done, so an old copy is not saved over it later.
#	Only ships with "SecondaryTarget" in Ships.py can use it. Changes apply
#	from the next battle.
###############################################################################

# Weapon types used when Ships.py says Def for this ship. Add the numbers:
# 1 = phasers, 2 = torpedoes, 4 = pulse weapons (7 = all of them).
# A number written in Ships.py for a ship works the same way; 0 = off.
Weapons = 7

# Seconds between cycles (the safety net: the fire keys act at once).
Interval = 0.2

# How many of the nearest enemies are looked at each cycle (the cost grows
# with this number).
MaxCandidates = 4

# An enemy becomes a secondary target when it is within this percentage of
# the phaser's maximum damage range (100 = the range of full damage).
SecondaryRange = 100

# Minimum firing solution (percent) to launch a torpedo at a secondary
# target.
SecondaryTorpedoMinSolution = 70

# 1 = write messages in the log (for testing).
Debug = 0
