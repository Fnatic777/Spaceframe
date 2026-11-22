###############################################################################
#	Auto Fire - Spaceframe module configuration
#
#	Edit with a text editor (Notepad++ recommended). Close the file in the
#	editor when you are done, so an old copy is not saved over it later.
#	Only ships with "AutoFire" in Ships.py can use it.
###############################################################################

# Key that switches Auto Fire on and off (one letter). The "Auto Fire"
# button in the tactical officer's menu does the same.
ToggleKey = "L"

# 1 = Auto Fire starts switched on at the beginning of each battle.
StartEnabled = 0

# Seconds between firing decisions.
FireInterval = 0.1

# Which target Auto Fire shoots at (only ever the mission's enemies, never
# friendly or neutral ships, even when selected):
#   0 = only the player's selected target;
#   1 = the selected target; with none (or after a kill) the nearest enemy,
#       which becomes the selected target;
#   2 = each weapon group picks its own: phasers the nearest enemy they
#       can hit, torpedoes and pulse weapons the target with the best arc
#       score (see TorpedoRule; the selected target is left as it is).
TargetMode = 1

# Phasers fire when the target is within this percentage of their maximum
# damage range (100 = the range of full damage; beyond it they still hit,
# with less damage).
# 0 = off (no range check: they fire whenever a bank's arc reaches the target).
PhaserRange = 0

# Phasers fire only when charged at least this much (percent).
# 0 = off (no charge check).
PhaserMinCharge = 0

# Torpedoes and pulse weapons fire faster from quick presses of the fire
# key than from holding it: 1 = Auto Fire taps their fire key (pressed one
# cycle, released the next), 0 = holds it. Phaser beams are always held.
TapFire = 1

# How Auto Fire decides to launch torpedoes (both rules start from the arc
# percent below):
#   1 = arc percent only: a tube fires when where the target will be is inside
#       its fixed 30 degree cone by a percentage that depends on the distance
#       (TorpedoArc* settings below);
#   2 = rule 1 PLUS a flight-time filter: a tube is also held while the
#       estimated flight time (distance / torpedo speed) is longer than a
#       limit that depends on the distance (TorpedoFlightTime* settings
#       below).
# Any other value (including the old 3) counts as 2.
TorpedoRule = 2

# The same choice for pulse weapons (disruptors, pulse cannons): rule 1 =
# arc percent only (PulseArc* settings), rule 2 = plus the flight-time filter
# (PulseFlightTime* settings). With Secondary Target ON, the rule also
# chooses the secondary targets (Auto Fire and manual).
PulseRule = 2

# Pulse weapon arc percent. The arc is measured from its
# centre (0 = centre, 100 = its edge). A weapon starts to fire when the
# predicted target point is within PulseArcPercentFar percent of the arc at
# PulseArcFarDistance km and beyond, opening to PulseArcPercentNear percent
# at PulseArcNearDistance km and closer (in between, in proportion).
# Distances as shown in game. Once firing, it keeps firing until the point
# is more than PulseArcHysteresis percentage points past that limit (never
# beyond the edge of the arc), so it does not flicker at the border.
# PulseArcHysteresis 0 = off: a weapon is ready only while inside the allowed
# percent, no stickiness.
PulseArcPercentFar = 90
PulseArcPercentNear = 90
PulseArcFarDistance = 40
PulseArcNearDistance = 20
PulseArcHysteresis = 0

# Torpedo arc percent, the same idea on the tube's fixed 30
# degree cone (0 = centre, 100 = its edge, on both axes). With Secondary
# Target ON it also decides which secondary targets a tube may take (Auto
# Fire and manual fire).
TorpedoArcPercentFar = 90	# percent 0-100, at TorpedoArcFarDistance km and beyond
TorpedoArcPercentNear = 90	# percent 0-100, at TorpedoArcNearDistance km and closer
TorpedoArcFarDistance = 40	# km as shown in game
TorpedoArcNearDistance = 20	# km as shown in game
TorpedoArcShape = 1	# 1 = the percent is measured as one angle from the arc centre (cone for torpedoes: a corner of the box counts further out, so it is stricter than the sides); 0 = old box depth (deeper of the two axes)
PulseArcShape = 1	# same for pulse weapons, an ellipse inscribed in the weapon's own (possibly asymmetric) arc limits; 0 = old box depth
TorpedoArcHysteresis = 0	# percentage points; 0 = off: a tube is ready only while inside the allowed percent, no stickiness

# Separate arc percent for SECONDARY targets (same meaning as the settings
# above). Used for secondary targets only (Secondary Target ON; Auto Fire and
# manual filter); the main target keeps the settings above. The hysteresis
# stays shared. A setting left out here falls back to the main one.
PulseArcPercentFarSecondary = 90	# percent 0-100, at PulseArcFarDistanceSecondary km and beyond
PulseArcPercentNearSecondary = 90	# percent 0-100, at PulseArcNearDistanceSecondary km and closer
PulseArcFarDistanceSecondary = 30	# km as shown in game
PulseArcNearDistanceSecondary = 15	# km as shown in game
TorpedoArcPercentFarSecondary = 90	# percent 0-100, at TorpedoArcFarDistanceSecondary km and beyond
TorpedoArcPercentNearSecondary = 90	# percent 0-100, at TorpedoArcNearDistanceSecondary km and closer
TorpedoArcFarDistanceSecondary = 30	# km as shown in game
TorpedoArcNearDistanceSecondary = 15	# km as shown in game

# Flight-time filter (TorpedoRule / PulseRule 2 only; rule 1 ignores it).
# A weapon is held, as if outside the arc percent, while the estimated flight
# time (distance to the target / projectile speed: the current torpedo's
# launch speed, or the pulse weapon's) is longer than the limit for that
# distance. The limit is the Near value at the arc band's Near distance and
# closer, the Far value at its Far distance and beyond, in proportion
# between (it uses the same distances as the arc percent of the same kind
# and of main / secondary). Seconds; 0 = no limit for that band (the filter
# is off for that kind and role when either its Far or its Near value is 0).
# A guided projectile (torpedoes) is allowed its guidance time on top of the
# limit, never more than its lifetime (pulse weapons have no guidance).
# An unknown projectile speed never blocks. No hysteresis.
TorpedoFlightTimeFar = 1.0	# seconds, at TorpedoArcFarDistance km and beyond (0 = off)
TorpedoFlightTimeNear = 1.0	# seconds, at TorpedoArcNearDistance km and closer (0 = off)
PulseFlightTimeFar = 1.0	# seconds, at PulseArcFarDistance km and beyond (0 = off)
PulseFlightTimeNear = 1.0	# seconds, at PulseArcNearDistance km and closer (0 = off)

# The same limits for SECONDARY targets (a setting left out falls back to the
# main one).
TorpedoFlightTimeFarSecondary = 0.5	# seconds (0 = off)
TorpedoFlightTimeNearSecondary = 0.5	# seconds (0 = off)
PulseFlightTimeFarSecondary = 0.5	# seconds (0 = off)
PulseFlightTimeNearSecondary = 0.5	# seconds (0 = off)

# Minimum arc score (percent: 100 = target dead centre of the tube's cone,
# 1 = at its edge) to switch the torpedoes to spread.
SpreadMinSolution = 75

# Spread torpedoes leave in a fan and take a while to turn to the target:
# closer than this (in km, as shown in game) Auto Fire fires them Single.
SpreadMinDistance = 35

# Torpedoes kept back for manual use (Auto Fire stops launching when only
# this many are left in the magazine).
TorpedoReserve = 0

# 1 = with Secondary Target switched ON for this ship (torpedoes allowed there),
# torpedo tubes that cannot reach the target fire at secondary targets they can
# reach (same rule as the main target, TorpedoRule). 0 = off.
SecondaryTorpedoes = 1

# 1 = with Secondary Target switched ON for this ship (phasers allowed there),
# a phaser group whose banks cannot reach the main target (no ready bank can
# hit it) starts at the first secondary target a ready bank can reach, and goes
# back to the main target as soon as a bank can hit it. When a bank reaches
# the main target nothing changes (Secondary Target adds the secondaries while
# the group fires). 0 = off.
SecondaryPhasers = 1
