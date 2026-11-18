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

# 1 = at most one phaser bank fires at each target at a time (the main target
# included): the banks that reach it take turns, the others are held for a
# moment. 0 = no limit (all banks that can fire do). Pulse weapons are never
# limited. Only applies while the module has lifted the group's single fire.
# EXPERIMENTAL: leave at 0 unless testing; held beams may flicker.
PhaserPerTarget = 1

# Seconds between the fast checks that hold the extra phaser banks of
# PhaserPerTarget (a second, faster timer that exists only while a phaser group
# is lifted; the normal Interval does everything else). Lower = less flicker.
# Minimum 0.02. The engine cannot go below one frame, and very low values may
# cost frames per second. Try 0.05, 0.03 or 0.02.
LimitInterval = 0.05

# How PhaserPerTarget holds an extra bank.
# 0 = StopFiring only (default); the engine refires the bank about 0.25 s later,
#     so a fast timer renews the hold (LimitInterval) and beams may flicker.
# 1 = StopFiring, then SetFiring(0). OBSOLETE: the engine analysis shows it does
#     the same as 0. Do not use.
# 2 = EXPERIMENTAL: StopFiring, then the bank's MinFiringCharge is raised above
#     its maximum charge, so the engine cannot refire it (no flicker; the bank
#     keeps recharging). The original value is written back when the bank is
#     released (kept bank, target gone, feature off, ship change, etc.). The fast
#     timer is not used. If the battle ends while a bank is held the value is not
#     restored (the ships are destroyed); a new battle starts clean.
HoldMode = 2

# HoldMode 2 only: seconds (game time) a bank stays held, and a released bank
# stays free, before it may change again (avoids back-and-forth).
HoldHysteresis = 1.0

# HoldMode 2 only: 1 = every cycle, forget (and restore if the ship is still
# live) held-bank records whose ship is gone or is not your ship any more.
HoldSafety = 1

# 1 = write messages in the log (for testing).
Debug = 0
