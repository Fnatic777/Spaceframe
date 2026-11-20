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
StartEnabled = 1

# Seconds between firing decisions.
FireInterval = 0.1

# Which target Auto Fire shoots at (only ever the mission's enemies, never
# friendly or neutral ships, even when selected):
#   0 = only the player's selected target;
#   1 = the selected target; with none (or after a kill) the nearest enemy,
#       which becomes the selected target;
#   2 = each weapon group picks its own: phasers the nearest enemy they
#       can hit, torpedoes and pulse weapons the best firing solution
#       (the selected target is left as it is).
TargetMode = 1

# Phasers fire when the target is within this percentage of their maximum
# damage range (100 = the range of full damage; beyond it they still hit,
# with less damage).
# 0 = off (no range check: they fire whenever a bank's arc reaches the target).
PhaserRange = 0

# Phasers fire only when charged at least this much (percent).
# 0 = off (no charge check).
PhaserMinCharge = 0

# Minimum firing solution (percent) to launch a torpedo.
TorpedoMinSolution = 50

# Torpedoes and pulse weapons fire faster from quick presses of the fire
# key than from holding it: 1 = Auto Fire taps their fire key (pressed one
# cycle, released the next), 0 = holds it. Phaser beams are always held.
TapFire = 1

# How Auto Fire decides to launch torpedoes:
#   1 = firing solution (below): predicted miss against the target's size;
#   2 = firing cone, like the game's own AI: a tube fires when where the
#       target will be is within an angle of where the tube points. The
#       angle opens as the target gets closer (settings below);
#   3 = arc percent: a tube fires when where the target will be is inside its
#       fixed 30 degree cone by a percentage that depends on the distance
#       (TorpedoArc* settings below); TorpedoMinSolution is not used in this
#       rule.
TorpedoRule = 3

# The same choice for pulse weapons (disruptors, pulse cannons):
#   1 = firing solution: they aim themselves inside their arc, so only the
#       flight counts (target evasion, projectile lifetime, target size);
#   2 = firing cone around where each weapon points (pulse cone settings
#       below); PulseMinSolution is not used in this rule;
#   3 = arc percent: a weapon fires when where the target will be is inside
#       its firing arc by a percentage that depends on the distance
#       (PulseArc* settings below); PulseMinSolution is not used in this rule.
#       With Secondary Target ON, also chooses the secondary targets (Auto
#       Fire and manual).
PulseRule = 3

# Torpedo firing cone (TorpedoRule 2): ConeAngleFar degrees at
# ConeFarDistance km and beyond, opening to ConeAngleNear degrees at
# ConeNearDistance km and closer (in between, in proportion). Distances as
# shown in game. A weapon dead on the target counts as solution 100, one at
# the edge as 1, for SpreadMinSolution; TorpedoMinSolution is not used in
# this rule.
ConeAngleFar = 10
ConeAngleNear = 30
ConeFarDistance = 30
ConeNearDistance = 0

# Pulse weapon firing cone (PulseRule 2), the same way. Pulse weapons aim
# themselves across wide arcs, so their cone is usually much wider than the
# torpedoes'.
PulseConeAngleFar = 45
PulseConeAngleNear = 90
PulseConeFarDistance = 30
PulseConeNearDistance = 5

# Pulse weapon arc percent (PulseRule 3). The arc is measured from its
# centre (0 = centre, 100 = its edge). A weapon starts to fire when the
# predicted target point is within PulseArcPercentFar percent of the arc at
# PulseArcFarDistance km and beyond, opening to PulseArcPercentNear percent
# at PulseArcNearDistance km and closer (in between, in proportion).
# Distances as shown in game. Once firing, it keeps firing until the point
# is more than PulseArcHysteresis percentage points past that limit (never
# beyond the edge of the arc), so it does not flicker at the border.
# PulseArcHysteresis 0 = off: a weapon is ready only while inside the allowed
# percent, no stickiness.
PulseArcPercentFar = 50
PulseArcPercentNear = 90
PulseArcFarDistance = 30
PulseArcNearDistance = 5
PulseArcHysteresis = 0

# Torpedo arc percent (TorpedoRule 3), the same idea on the tube's fixed 30
# degree cone (0 = centre, 100 = its edge, on both axes). With Secondary
# Target ON it also decides which secondary targets a tube may take (Auto
# Fire and manual fire).
TorpedoArcPercentFar = 50	# percent 0-100, at TorpedoArcFarDistance km and beyond
TorpedoArcPercentNear = 90	# percent 0-100, at TorpedoArcNearDistance km and closer
TorpedoArcFarDistance = 30	# km as shown in game
TorpedoArcNearDistance = 5	# km as shown in game
TorpedoArcHysteresis = 0	# percentage points; 0 = off: a tube is ready only while inside the allowed percent, no stickiness

# --- Firing solution (torpedoes and pulse weapons) -----------------------
# For each loaded tube, Auto Fire predicts where the target will be when
# the shot arrives, then works out by how much the shot would miss:
#   aim error   - the tube's direction against the predicted position,
#                 less what the projectile's guidance can steer back;
#   evasion     - how far the target can dodge during the flight.
# The solution is how much of the target's size that expected miss leaves
# (100 = dead centre, 0 = a miss). Speed, guidance and turn rate come from
# each projectile's own script.

# How much the target is expected to dodge a shot in flight: percent of
# its top acceleration, during the whole flight. The biggest factor at long
# range: raise it for fewer, surer shots; lower it for more long shots.
# (0 = the target never dodges)
TargetEvasion = 5

# How much of the projectile's guidance is counted on to correct the aim
# (100 = all of it, 0 = none: only straight shots).
GuidanceStrength = 100

# Most the guidance can correct, in percent of the distance to the target.
GuidanceLimit = 50

# Largest angle, in degrees, between a tube and where the target will be
# for that tube to fire. Smaller: only tubes pointing at the target fire
# (the guidance corrects less); larger: tubes further off also fire and
# count on the guidance to turn the torpedo. Above 90, tubes pointing
# away may fire when the guidance can bring the torpedo round. (The game's
# own AI uses 10 to 50.)
TubeMaxAngle = 120

# Size of the target counted as a hit, in percent of its radius (raise it
# to accept shots that would only graze the shields).
TargetSize = 100

# Minimum firing solution (percent) to switch the torpedoes to spread.
SpreadMinSolution = 75

# Spread torpedoes leave in a fan and take a while to turn to the target:
# closer than this (in km, as shown in game) Auto Fire fires them Single.
SpreadMinDistance = 35

# Minimum firing solution (percent) to fire pulse weapons (disruptors).
PulseMinSolution = 50

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
