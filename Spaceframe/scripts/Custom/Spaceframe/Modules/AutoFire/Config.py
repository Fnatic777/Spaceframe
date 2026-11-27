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

# Arc percent depends on the estimated FLIGHT TIME of the shot (distance to the
# predicted point / projectile speed: the current torpedo's launch speed, or
# the pulse weapon's), not on the distance. One pair of times is shared by
# every kind and role (pulse, torpedo, main, secondary). Seconds.
ArcFlightTimeNear = 0.5	# at this flight time and less the NEAR percent applies
ArcFlightTimeFar = 1.5	# at this flight time and more the FAR percent applies
# Between the two times the allowed percent interpolates linearly between the
# Near and the Far percent. Unknown projectile speed: the Near percent.

# Pulse weapon arc percent. The arc is measured from its
# centre (0 = centre, 100 = its edge). A weapon starts to fire when the
# predicted target point is within PulseArcPercentNear percent of the arc at
# ArcFlightTimeNear seconds of flight and less, narrowing to
# PulseArcPercentFar percent at ArcFlightTimeFar seconds and more (in
# between, linear). Once firing, it keeps firing until the point
# is more than PulseArcHysteresis percentage points past that limit (never
# beyond the edge of the arc), so it does not flicker at the border.
# PulseArcHysteresis 0 = off: a weapon is ready only while inside the allowed
# percent, no stickiness.
PulseArcPercentFar = 70		# percent 0-100, at ArcFlightTimeFar seconds and more
PulseArcPercentNear = 90	# percent 0-100, at ArcFlightTimeNear seconds and less
PulseArcHysteresis = 0

# Torpedo arc percent, the same idea on the tube's fixed 30
# degree cone (0 = centre, 100 = its edge, on both axes). With Secondary
# Target ON it also decides which secondary targets a tube may take (Auto
# Fire and manual fire).
TorpedoArcPercentFar = 70	# percent 0-100, at ArcFlightTimeFar seconds and more
TorpedoArcPercentNear = 90	# percent 0-100, at ArcFlightTimeNear seconds and less
TorpedoArcShape = 1	# 1 = the percent is measured as one angle from the arc centre (cone for torpedoes: a corner of the box counts further out, so it is stricter than the sides); 0 = old box depth (deeper of the two axes)
PulseArcShape = 1	# same for pulse weapons, an ellipse inscribed in the weapon's own (possibly asymmetric) arc limits; 0 = old box depth
TorpedoArcHysteresis = 0	# percentage points; 0 = off: a tube is ready only while inside the allowed percent, no stickiness

# Separate arc percent for SECONDARY targets (same meaning as the settings
# above). Used for secondary targets only (Secondary Target ON; Auto Fire and
# manual filter); the main target keeps the settings above. The hysteresis
# stays shared. A setting left out here falls back to the main one.
PulseArcPercentFarSecondary = 70	# percent 0-100, at ArcFlightTimeFar seconds and more
PulseArcPercentNearSecondary = 90	# percent 0-100, at ArcFlightTimeNear seconds and less
TorpedoArcPercentFarSecondary = 70	# percent 0-100, at ArcFlightTimeFar seconds and more
TorpedoArcPercentNearSecondary = 90	# percent 0-100, at ArcFlightTimeNear seconds and less

# Flight-time filter (TorpedoRule / PulseRule 2 only; rule 1 ignores it).
# A weapon is held, as if outside the arc percent, while the estimated flight
# time (distance to the target / projectile speed: the current torpedo's
# launch speed, or the pulse weapon's) is longer than this limit. One limit
# per kind and role, in seconds; 0 = no limit (filter off for that kind and
# role).
# A guided projectile (torpedoes) is allowed its guidance time on top of the
# limit, never more than its lifetime (pulse weapons have no guidance).
# An unknown projectile speed never blocks. No hysteresis.
TorpedoFlightTimeLimit = 1.5	# seconds (0 = off)
# Hold fire on a target doing an in-system warp (the enemy intercept speed
# boost: its velocity is several times the normal one and the lead
# prediction is wrong). Auto Fire only, torpedoes and pulse weapons, main and
# secondary targets, rules 1 and 2; manual fire is never held.
HoldOnWarp = 1		# 1 = hold, 0 = off
# Seconds the hold continues after the warp ended (stale velocity data); 0 = none.
WarpHoldGrace = 1.0	# seconds
PulseFlightTimeLimit = 1.5	# seconds (0 = off)

# The same limits for SECONDARY targets (a setting left out falls back to the
# main one).
TorpedoFlightTimeLimitSecondary = 1.0	# seconds (0 = off)
PulseFlightTimeLimitSecondary = 1.0	# seconds (0 = off)

# Longer flight time against targets that cannot get out of the way: large
# ones, slow ones, damaged engines. Used only when a shot is over its limit
# above (rule 2; torpedoes and pulse weapons, main and secondary targets), and
# never makes a limit shorter. The time the target gets is
#   square root of (2 x allowance x target radius / its current acceleration)
# in game units, plus the guidance time. A target with no impulse engines or no
# acceleration gets the maximum. Small agile ships stay under the limits above.
TargetSizeAllowance = 100	# percent of the target radius (higher = more permissive; 0 = off)
TargetSizeFlightTimeMax = 5.0	# seconds, never longer than this (0 = off)

# Spread torpedoes leave in a fan and take a while to turn to the target:
# Auto Fire fires them in spread only while the estimated flight time
# (distance to the target / current torpedo speed) is between these two
# values, and Single otherwise (too close they would fly past the target,
# too far the fan is too wide). Seconds; Max 0 = no upper bound. Unknown
# torpedo speed: Single.
# The window only chooses HOW a torpedo is fired, never whether: the arc
# percent and the flight-time limit above (stretched by TargetSize* for large
# or hard to move targets) still decide that, main and secondary targets alike.
# So a target limited below SpreadFlightTimeMin never gets spread, and a limit
# inside the window allows spread only up to the limit. The spread mode
# belongs to the torpedo system: secondary targets fired in the same press as a
# spread shot at the main target leave in spread too. Pulse weapons are not
# affected. The distance used is tube to predicted point.
SpreadFlightTimeMin = 2.0
SpreadFlightTimeMax = 5.0

# Separate arc percent for spread torpedoes (percent 0-100, same measure as
# TorpedoArcPercent*: the depth of the predicted point inside the tube arc,
# TorpedoArcShape respected; 0 = tube axis, 100 = arc edge). A tube only
# counts as a spread shot when the flight time is in the window above AND its
# depth*100 is at most this value. Between this value and the normal arc
# percent it is fired Single. Fixed value, not interpolated by flight time, no
# hysteresis; main and secondary targets alike.
SpreadArcPercent = 10

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
