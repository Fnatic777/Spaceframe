# Spec: arc-percent rule for pulse AND torpedo, main AND secondary, Auto Fire AND manual

Date 2026-11-20, main at 87c416b. Author: bc-architect (DESIGN). Target: AutoFire 0.5 ->
(see Q3), SecondaryTarget 0.3 -> (see Q3), Solution.py. Builds on
`2026-11-19-autofire-torpedo-secondary-spec.md` (sections 3, 4, 10 stay valid unless replaced here).

## 1. Agreed behavior (user rulings, final)
- "Arc-percent rule" = the target's predicted point must lie within an allowed percentage of the
  weapon's REAL arc (0 = centre, 100 = edge), allowed % interpolated by distance, with hysteresis
  per (weapon, target). Pulse: today's PulseRule 3. Torpedo: NEW TorpedoRule 3 (fixed +-30 deg
  cone, both axes), next to rules 1/2. Phasers: untouched.
- Auto Fire (rule 3 selected for that kind): the rule decides whether the group is pressed (main
  OR, if main has no shot, a secondary) and which secondaries are put in the list.
- Manual (fire key held): the rule ONLY filters which secondaries SecondaryTarget adds (a
  secondary is added only if a FREE weapon of that group reaches it inside the allowed %). The
  main target is never restricted; the held fire is never stopped.
- Rule 1/2 selected: everything exactly as today (pulse secondaries via SecondaryTarget's
  "all pulse weapons free" path, torpedo plan via Solution.Score / cone).

## 2. Design decisions
D1 Where the logic lives:
   - Solution.py (pure math, stateless): new torpedo cone depth (`TubeFrame`, `TubeDepth`,
     `TorpedoArcDepth`). Pulse depth `ArcDepth` unchanged.
   - AutoFire.py (state + config): one generic `ArcScore(...)` (generalized PulseArcScore:
     readiness, lead point, depth, distance band, hysteresis in the existing `g_dArcReady`) and
     public entry points `ArcRuleOn(sKind)`, `ArcReaches(...)`, `ManagesPulseSecondaries(eGroup)`.
   - SecondaryTarget reaches them through its existing `GetAutoFire()` + `hasattr` + try (as v0.3
     does for `ManagesTorpedoSecondaries`). AutoFire reaches SecondaryTarget through
     `GetSecondaryTarget()` (core GetModule + hasattr). Each module alone: SecondaryTarget without
     the AutoFire functions -> ArcRule 0 -> today's behavior; AutoFire without SecondaryTarget ->
     no secondaries (today).
   - The rule switch is AutoFire's `PulseRule` / `TorpedoRule` == 3 (single source of truth, also
     for manual). If the AutoFire module is not active its LoadConfig never ran -> rules read as 1
     -> manual filter off (documented, not a bug).
D2 Torpedo depth: the confirmed TORPARC model (learned.md:57, STProbe.py:2039 TpModel/2156
   TpTubeLines): Fwd = ship rotation * `pTube.GetDirection()`, Right = ship rotation *
   `pTube.GetRight()` (both LOCAL wrappers: read GetX/GetY/GetZ into a fresh TGPoint3 via SetXYZ,
   then MultMatrixLeft(ship.GetWorldRotation())), Up = cross(Right, Fwd) (its sign is irrelevant:
   the cone is symmetric). Origin = `pTube.GetWorldLocation()` (candidate A; B matched too).
   D = point - origin; behind if dot(D,Fwd) <= 0 -> ARC_BEHIND (99); else
   depth = max(|atan2(D.Right, D.Fwd)|, |atan2(D.Up, D.Fwd)|) / 30 deg. Vectors used raw, exactly as
   the confirmed probe (no normalization). Any failure -> None -> caller falls back to the boolean
   `IsInArc(point)` (ArcFallback: 1.0 inside, 0.0 outside, 1.0 if it raises - as pulse today).
D3 Which point: the lead point (`Solution.LeadPoint`) as PulseRule 3 does. Torpedo: lead point
   computed ONCE per target per call from the SHIP's world location with the torpedo speed
   (tube offsets are metres vs km) and passed in; pulse keeps today's per-weapon lead point.
   Free/main-reaching CLASSIFICATION stays on the engine's own `IsInArc(target.GetWorldLocation())`
   (what the engine uses to pick a target); the % rule only judges "good enough shot".
D4 Torpedo rule 3 also has the projectile lifetime check (flight time > lifetime -> 0), as rules 1
   and 2 have. Pulse rule 3 keeps today's behavior (no lifetime check): module constant
   `PULSE_ARC_LIFETIME = 0` in AutoFire.py (see Q1).
D5 Auto Fire pulse rule 3 now builds the pulse group's list itself on every press, exactly as the
   torpedo plan (main shot -> [main, sec...]; no main shot -> [sec...] without main, secondaries
   that a CHARGED main-reaching weapon also has in arc dropped). SecondaryTarget then leaves
   Auto-Fire-driven pulse groups alone (like torpedoes). No new switch: pulse secondaries under
   Auto Fire are on by SecondaryTarget's toggle + bit 4, the rule by PulseRule 3.
D6 Hysteresis keys stay per (weapon ID, target ID) in `g_dArcReady`, shared by Auto Fire and the
   manual filter (Auto Fire never evaluates a manual group). `ArcSettle` keeps the keys of the
   main AND of the group's current secondaries (new `g_dArcSec[eGroup]`); a key is dropped when
   its weapon is not ready (Auto Fire only, bNeedReady = 1) or the point leaves limit+hysteresis.
   The manual filter does NOT require charge/readiness (otherwise secondaries would be removed
   after every shot and re-added: list flapping).
D7 Flapping guard: the held-group guard (`g_dSecHead`) applies to pulse rule 3 groups too.
D8 Main target under Auto Fire: when the group is pressed at main, every main-reaching weapon fires
   at it, also one outside its %, as today (the engine cannot hold back one weapon). Same for a
   pressed secondary.
No new engine call; no STProbe experiment needed (section 9 is verified by the first Debug run).

## 3. Verified API (all already used in the repo)
- `TorpedoTube.GetDirection()/GetRight()` local wrappers, GetX/GetY/GetZ - STProbe.py:2159-2162,
  :1996; learned.md:57. `TGPoint3.SetXYZ` + `MultMatrixLeft(ship.GetWorldRotation())` -
  STProbe.py:2017-2019, Solution.py:259.
- `TorpedoTube.IsInArc(worldPoint)` - AutoFire.py:618, SecondaryTarget.py:464.
- `PulseWeapon.IsInArc(worldPoint)` - AutoFire.py:814,877 (learned.md:54).
- `TorpedoTube.GetWorldLocation()` - STProbe.py:2070; `GetNumReady()` - AutoFire.py:669.
- `Solution.LeadPoint/ArcDepth/GetProjectileInfo` - AutoFire.py:908-914.
- `Weapon/TorpedoTube.GetObjID()` (hysteresis key) - AutoFire.py:867 for pulse; for tubes
  (unconfirmed, any TGObject has it): `WeaponKey` already returns None on error -> no hysteresis
  for that tube, rule still works.
- `WeaponSystem.StartFiring/StopFiring/SetForceUpdate/IsFiring` - AutoFire.py:1057-1087.
- `App.PulseWeaponSystem_Cast/PulseWeapon_Cast/TorpedoTube_Cast` - AutoFire.py:945,1015,665.

## 4. File-by-file changes

### 4.1 Modules/AutoFire/Solution.py (append after ArcDepth)
```
TORP_ARC_HALF = 0.5235988	# the torpedo tube cone: +-30 degrees on both axes (fixed in the engine)

def Triple(vAny):		# any vector wrapper -> (x, y, z) floats (GetX/GetY/GetZ)
def LocalToWorld(pShip, vAny):	# fresh TGPoint3 via SetXYZ(Triple(vAny)), MultMatrixLeft(ship rotation); returns Triple
def TubeFrame(pShip, pTube):	# (tPos, tFwd, tRight, tUp) float tuples or None (whole body in try)
	# tFwd = LocalToWorld(GetDirection()), tRight = LocalToWorld(GetRight()),
	# tUp = cross(tRight, tFwd), tPos = Triple(pTube.GetWorldLocation())
def TubeDepth(tFrame, vPoint):	# 0 centre .. 1 cone edge, ARC_BEHIND behind, None on error (D2)
def TorpedoArcDepth(pShip, pTube, vPoint):	# TubeFrame + TubeDepth, None if the frame is None
```
Pure floats after the frame is read (no TGPoint3 arithmetic: cross/dot on tuples, math.atan2).

### 4.2 Modules/AutoFire/Config.py
- TorpedoRule comment: add
  `#   3 = arc percent: a tube fires when where the target will be is inside its fixed 30 degree`
  `#       cone by a percentage that depends on the distance (TorpedoArc* settings below);`
  `#       TorpedoMinSolution is not used in this rule.`
- PulseRule 3 comment: drop "(NEW, validate with the STProbe ARCFORMULA test)" (confirmed), add
  `#       With Secondary Target ON, also chooses the secondary targets (Auto Fire and manual).`
- New block after the PulseArc* block (defaults = the pulse code defaults; only read with
  TorpedoRule = 3, so current behavior is unchanged):
```
# Torpedo arc percent (TorpedoRule 3), the same idea on the tube's fixed 30
# degree cone (0 = centre, 100 = its edge, on both axes). With Secondary
# Target ON it also decides which secondary targets a tube may take (Auto
# Fire and manual fire).
TorpedoArcPercentFar = 50	# percent 0-100, at TorpedoArcFarDistance km and beyond
TorpedoArcPercentNear = 90	# percent 0-100, at TorpedoArcNearDistance km and closer
TorpedoArcFarDistance = 30	# km as shown in game
TorpedoArcNearDistance = 5	# km as shown in game
TorpedoArcHysteresis = 10	# percentage points
```
- SecondaryTorpedoes comment: "same firing solution rule as above" -> "same rule as the main
  target (TorpedoRule)". No Ships.py key.

### 4.3 Modules/AutoFire/AutoFire.py
Globals (with comments): `g_fTorpArcFar = 50.0`, `g_fTorpArcNear = 90.0`,
`g_fTorpArcFarDistance = 171.0`, `g_fTorpArcNearDistance = 29.0`, `g_fTorpArcHysteresis = 10.0`,
`g_dArcSec = {}` (group -> IDs of the secondaries of the last plan, incl. a secondary head),
`g_dPlanNote = {}` (group -> last Debug plan line), `PULSE_ARC_LIFETIME = 0`.
LoadConfig: read the five TorpedoArc* (distances through KilometersToUnits), `g_dPlanNote = {}`.
ForgetArc: also `g_dArcSec = {}`. Start/Stop: nothing else (both call ForgetArc / LoadConfig).

Functions (new or changed; callers always positional; defaults only in `def`):
1. `ArcAllowed(fDistance, tBand=None)`: tBand = (far %, near %, far dist, near dist); None -> the
   pulse globals (tests call `ArcAllowed(d)`). Body unchanged otherwise.
2. `ArcBand(sKind)` -> (tBand, fHysteresis) for "pulse" / "torpedo".
3. `WeaponReady(pWeapon, sKind)`: pulse -> PulseCharged; torpedo -> GetNumReady() > 0; error -> 0.
4. `TorpedoShot(pShip, pTorpedoes, pTarget, vOffset)` -> (vPoint, fSpeed, fLifetime):
   tInfo = GetProjectileInfo(None, pTorpedoes); vPoint = LeadPoint(pTarget, vOffset,
   pShip.GetWorldLocation(), tInfo[0]); on error (target location, 0.0, 0.0).
5. `ArcScore(pShip, pSystem, pWeapon, pTarget, vOffset, sKind, bNeedReady, tFrame=None, tShot=None)`
   = today's PulseArcScore body generalized:
   - key (WeaponKey, target ID); if bNeedReady and not WeaponReady: drop key, return 0.0;
   - point: tShot[0] if tShot given; else per weapon as today: tInfo = GetProjectileInfo(pWeapon,
     pSystem) for pulse, GetProjectileInfo(None, pSystem) for torpedo; vPoint = LeadPoint(pTarget,
     vOffset, pWeapon.GetWorldLocation(), tInfo[0]); on error the target's location;
   - depth: torpedo -> TubeDepth(tFrame or TubeFrame(pShip, pWeapon)) (frame None -> depth None);
     pulse -> ArcDepth; None -> `return ArcFallback(pWeapon, vPoint)`;
   - distance weapon -> point (as today);
   - lifetime: torpedo always, pulse only if PULSE_ARC_LIFETIME: speed > 0 and lifetime > 0 and
     distance / speed > lifetime -> drop key, return 0.0 (speed/lifetime from tShot or tInfo);
   - limit = ArcAllowed(distance, band) (+ hysteresis if key present, cap 100); rest unchanged.
6. `PulseArcScore(pShip, pSystem, pWeapon, pTarget, vOffset)` = `ArcScore(..., "pulse", 1)`
   (kept: tests and BestPulseScore call it).
7. `ArcRuleOn(sKind)` (public): 1 iff (pulse and g_iPulseRule == 3) or (torpedo and
   g_iTorpedoRule == 3).
8. `ArcReaches(pShip, pSystem, pWeapon, pTarget, sKind)` (public, manual filter): whole body in
   try -> 0; `ArcScore(pShip, pSystem, pWeapon, pTarget, None, sKind, 0) >= 1.0`.
9. `ManagesPulseSecondaries(eGroup)` (public): 1 iff g_iPulseRule == 3 and IsEnabled() and not
   g_dManual.get(eGroup); try -> 0.
10. `GetSecondaryTarget(sFunc="TorpedoCandidates")`: hasattr(pModule, sFunc).
11. `TubeScore(pShip, pTorpedoes, pTube, pTarget, vOffset, tInfo, tFrame, tShot)`: rule 3 ->
    ArcScore(..., "torpedo", 1, tFrame, tShot); else EXACTLY today's call
    `GetSolution().Score(pShip, pTarget, vOffset, pTube, pTube.CalculateRoughDirection(), tInfo)`.
12. `BestTorpedoScore`: rule 3 -> tShot = TorpedoShot(pShip, pSystem, pTarget, vOffset) once;
    loop EVERY tube (ArcScore checks readiness and drops stale keys); else unchanged.
13. `TorpMinimum()` -> 1.0 for TorpedoRule 2 or 3, else g_fTorpedoMinSolution. Use it in
    TorpedoTarget and SecondaryTorpedoPlan (replaces the two inline `if rule == 2`).
14. `ArcSettle(pSystem, keep)`: keep = None, an ID, or a list of IDs; iterate children cast to
    PulseWeapon OR TorpedoTube; drop keys of those weapons whose target is not in keep. Keep the
    `continue` OUTSIDE any try (as today).
15. `PulseTarget` and `TorpedoTarget` (rule 3 only): every `ArcSettle(pSystem, X)` becomes
    `ArcSettle(pSystem, ArcKeep(eGroup, X))`, `ArcKeep` = [X if not None] + g_dArcSec.get(eGroup, []).
    TorpedoTarget gets the same three settle points as PulseTarget (reserve return, None, chosen).
16. `SecondaryTorpedoPlan`: fMin = TorpMinimum(); under rule 3 compute `tFrame` once per free
    tube (parallel list, `TubeFrame`) and `tShot` once per candidate (TorpedoShot, vOffset None);
    fScore = TubeScore(...). IsInArc pre-check, main-reaching drop rule, reserve: unchanged.
17. NEW `SecondaryPulsePlan(pShip, pPulse, pMain, bMainShot)` -> [(score, ID)] best first:
    [] unless g_iPulseRule == 3 and pMain; pST = GetSecondaryTarget("PulseCandidates") (None ->
    []); lIDs = pST.PulseCandidates(pShip, pPulse, pMain) in try (LogPlanError). Children
    PulseWeapon_Cast; charged (WeaponReady, error = not charged): TubeInArc(w, vMain, 1) ->
    lMainReady else lFree. lFree empty -> []. Per candidate (skip main, IsLive): drop if not
    bMainShot and AnyTubeInArc(lMainReady, vC); fBest = max over lFree with TubeInArc(w, vC, 0)
    of ArcScore(pShip, pPulse, w, pC, None, "pulse", 1); keep if >= 1.0 (insertion sort as
    torpedo). Per-candidate try (LogPlanError). (TubeInArc/AnyTubeInArc only call IsInArc: reuse.)
18. NEW `PlanPulseGroup(pShip, pPulse, pTarget, lTargets, eGroup)`: as PlanTorpedoGroup without
    ApplySpread (head secondary: g_dScore[eGroup] = its score).
19. NEW `PlanGroup(pShip, pSystem, pTarget, lTargets, eGroup)`: torpedo -> PlanTorpedoGroup;
    pulse system and g_iPulseRule == 3 -> PlanPulseGroup; else (pTarget, [], 0).
    `Plannable(pSystem)` -> "torpedo" / "pulse" (rule 3 only) / None.
20. FireCycle (inside the per-group try):
    - `sPlan = Plannable(pSystem)` replaces `pTorpedoes`; plan condition unchanged
      (`g_dFiring None or not IsFiring`), call `PlanGroup` (same try/LogPlanError).
    - After a successful plan, if ArcRuleOn(sPlan): `g_dArcSec[eGroup]` = lSec (+ head ID if
      bHeadSec); `ArcSettle(pSystem, ([head ID] if head) + lSec)`.
    - Held guard (line 1174): `(pTorpedoes != None)` -> `(sPlan != None)`.
    - Debug only: `PlanNote(eGroup, text)` logs "Group N plan: main <id|-> sec <ids|-> head
      <main|sec>" only when the text differs from g_dPlanNote[eGroup].
21. Header comment: pulse rule 3 / torpedo rule 3 choose secondaries too. VERSION: see Q3.

### 4.4 Modules/SecondaryTarget/SecondaryTarget.py
1. `KindCandidates(pShip, pSystem, pMain, iBit, sKind)` = today's TorpedoCandidates body with the
   bit and kind as parameters; `TorpedoCandidates(...)` -> KindCandidates(..., BIT_TORPEDO,
   "torpedo"); NEW `PulseCandidates(...)` -> KindCandidates(..., BIT_PULSE, "pulse"). Error text
   `sKind + " candidates error"`.
2. `AutoFireOwns(eGroup, sKind="torpedo")`: torpedo -> ManagesTorpedoSecondaries; pulse ->
   hasattr + ManagesPulseSecondaries. MaintainGroup: condition becomes
   `((sKind == "torpedo") or (sKind == "pulse")) and AutoFireOwns(eGroup, sKind)` (same body).
3. `ArcRule(sKind)`: pAF = GetAutoFire(); 1 iff hasattr(pAF, "ArcRuleOn") and
   hasattr(pAF, "ArcReaches") and pAF.ArcRuleOn(sKind); try -> 0.
4. `Reaches`: add `sKind == "pulse"` -> `pWeapon.IsInArc(pPoint)`; error handling as torpedo
   (logged once via g_bArcLogged).
5. `FreeWeapons`: pulse -> if ArcRule("pulse"): weapons with `not Reaches(w, mainPoint, "pulse",
   1)` (failure = not free); else all (today).
6. `SecReach(pShip, pSystem, pWeapon, pCandidate, sKind)`: `Reaches(w, cand point, sKind, 0)` and
   `GetAutoFire().ArcReaches(pShip, pSystem, pWeapon, pCandidate, sKind)`; try -> 0.
7. `WantedTargets`: `bArc = ArcRule(sKind)` once (pulse/torpedo only). Pulse: bReach = 1 if not
   bArc, else any free w with SecReach. Torpedo: if bArc use SecReach instead of Reaches.
   Debug only: collect the IDs that passed Reaches but failed SecReach; if that list differs from
   `g_dArcSkip[(ship ID, sKind)]`, store it and `TraceAdd("ARC-SKIP " + sKind + " " +
   IDText(list))` (also when it becomes empty: "ARC-SKIP pulse none"). `g_dArcSkip = {}` in ForgetAll.
8. `RearmReason` bSec loop: `Reaches(pTube, pSecPoint, "torpedo", 0)` ->
   `Reaches(...) and ((not bArc) or SecReach(pShip, pSystem, pTube, pSec, "torpedo"))`,
   bArc = ArcRule("torpedo") read once. Everything else in TryRearm unchanged.
9. Header comment: "pulse weapons under Auto Fire with PulseRule 3 are handled by Auto Fire;
   with rule 3 (pulse or torpedo) only secondaries a free weapon reaches inside the allowed arc
   percent are added". VERSION: see Q3.

### 4.5 tests/mock_app.py
- `Tube.GetObjID()` with a class counter starting at 7000 (like Pulse).
- `Pulse.iArc == "box"`: IsInArc follows the box of `limits`/`axes` from pPos (identity ship
  rotation), so free/main-reaching classification is geometric in pulse plan tests.

### 4.6 README.txt (EN/ES/PT, each language)
- AutoFire torpedo bullet: add TorpedoRule 3 (arc percent on the fixed 30 degree cone,
  TorpedoArcPercentFar/Near, TorpedoArcFarDistance/NearDistance, TorpedoArcHysteresis).
- PulseRule 3 bullet: remove "(NEW, validate with the STProbe ARCFORMULA test)"; add "with
  Secondary Target ON it also picks the secondary targets of the free weapons, and fires at a
  secondary alone when no weapon has a shot at the main target".
- SecondaryTorpedoes bullet: "same firing solution rule" -> "same rule as the main (TorpedoRule)".
- SecondaryTarget section: new bullet "With PulseRule 3 / TorpedoRule 3 (Auto Fire Config) a
  secondary is added only if a weapon that does not reach the main target has it inside the
  allowed arc percent; with manual fire your main target is never restricted. Pulse weapons
  under Auto Fire with PulseRule 3 are handled by Auto Fire."

### 4.7 Ledger rulings (coordinator, after the in-game test; autofire-progress.md and
secondary-target-progress.md)
- Arc-percent rule extended: TorpedoRule 3 (fixed cone depth from GetDirection/GetRight, lead
  point from the ship) and pulse/torpedo secondaries by the rule under Auto Fire and manual; rule
  switch = AutoFire PulseRule/TorpedoRule 3 also for manual - cost if wrong: one SecondaryTarget
  setting to add.
- Manual: the rule only filters the secondaries added, never the main - user ruling.
- Pulse rule 3 under Auto Fire builds [main, sec] / [sec] lists itself; SecondaryTarget leaves
  those groups alone - cost if wrong: pulse secondaries idle under Auto Fire.
- Manual filter ignores charge/readiness (no list flapping) - cost if wrong: a secondary stays
  listed while the free weapon recharges (harmless).

## 5. Lifecycle
No new handler, timer, key binding or UI object. New state: `g_dArcSec`, `g_dPlanNote` (AutoFire,
reset by ForgetArc/LoadConfig, i.e. Start, Stop, toggle off), `g_dArcSkip` (SecondaryTarget,
ForgetAll). Second Quick Battle: Start -> Stop -> ForgetArc/ForgetAll; modules looked up per
press. Battle end: unchanged (timers stopped in Stop; plans only inside FireCycle with
IsEnabled(); candidates by ID with IsLive). Player ship change: IsEnabled() 0 -> SetEnabled(0) ->
ForgetArc.

## 6. Per-cycle budget (FireInterval 0.1 s, SecondaryTarget Interval 0.2 s)
- Torpedo rule 3 main (every cycle): 1 LeadPoint per target + per READY tube 1 frame (~10 SWIG
  calls) - comparable to today's Solution.Score per ready tube.
- Plans: only on press cycles (every 0.2 s tapped): frames once per free tube, 1 LeadPoint per
  candidate, depth is float math. Galaxy DN, 7 free tubes x 4 candidates: 7 frames, 4 LeadPoints,
  <= 28 IsInArc. Pulse: per free charged weapon per candidate one PulseArcScore (as main today).
- Manual filter: per 0.2 s per group, free weapons x candidates (<= 4) ArcReaches; frames not
  cached (accepted: <= 28 frames per 0.2 s on a Galaxy). Nothing cached across cycles but IDs.

## 7. Failure modes
- GetDirection/GetRight/rotation fail -> frame None -> boolean IsInArc fallback (logged once).
- Tube GetObjID fails -> no hysteresis for it (rule still applied).
- Candidate dies between plan and press -> IsLive at StartFiring (existing).
- PulseCandidates missing (old SecondaryTarget) -> hasattr fails -> [] -> main-only as today.
- ArcReaches missing / raising -> SecReach 0 -> that secondary not added (manual); ArcRule 0
  when missing -> today's path.
- Exception in a plan -> LogPlanError, group fires main as planned before (existing try).
- AutoFire module inactive -> ArcRuleOn 0 -> SecondaryTarget as today.
- Multiplayer: core gate (EnableInMultiplayer), nothing new.

## 8. Mock tests (py3)
New `tests/test_torpedo_arc.py` (Solution + AutoFire torpedo rule 3):
1. TubeDepth centre 0; 15 deg on width 0.5; 30 deg 1.0; 33 deg > 1; both axes -> max; behind 99.
2. Ship rotated 90 deg yaw: frame follows (depth 0 at the rotated forward).
3. Agreement: grid of points (both iUpSign values) -> `depth <= 1` iff mock `Tube.IsInArc`.
4. GetDirection raising -> TorpedoArcDepth None; ArcScore falls back to IsInArc (1.0 / 0.0).
5. Config read: TorpedoArc* globals (km converted); defaults when absent.
6. TorpedoRule 3: ready tube within % -> TorpedoTarget returns target, g_dScore = 100*(1-depth);
   outside % (still IsInArc 1) -> None; Solution.Score stub NOT called.
7. Hysteresis per (tube, target): ready at 45%, holds at 55% (limit 50 + 10), released at 65%.
8. Unready tube (iReady 0) -> 0 and its key dropped.
9. Lifetime: flight time > lifetime -> 0.
10. Rules 1/2: g_dArcReady stays {}; Score stub called as before.
`tests/test_autofire_torp_secondary.py` additions (rule=3 variant of setup with geometric tubes):
11. main shot + aft tube with secondary within % -> [start main, start sec].
12. secondary inside the aft cone but outside % -> only main started.
13. no main shot, secondary within % of a free tube -> [start sec] only, Single spread.
14. sec hysteresis key survives the release cycle (ArcSettle keeps g_dArcSec).
New `tests/test_autofire_pulse_secondary.py` (fake ST with PulseCandidates; Pulse iArc "box"):
15. rule 3: main shot + free weapon reaches sec within % -> [start main, start sec].
16. sec outside % of every free weapon -> main only.
17. no main shot, free charged weapon reaches sec -> [start sec], log "at secondary".
18. no main shot, a charged main-reaching weapon also has sec in arc -> no start.
19. uncharged free weapon -> sec not added.
20. rules 1/2 -> PulseCandidates never called; ManagesPulseSecondaries 0.
21. manual key -> hands off, ManagesPulseSecondaries 0. 22. release cycle -> no plan call.
23. PulseCandidates raising -> main still started. 24. TapFire 0 held at a secondary head keeps
    firing without re-plan (g_dSecHead guard).
`tests/test_secondary_candidates.py` / `test_secondary_cycle.py` additions (fake AF with
ArcRuleOn/ArcReaches):
25. PulseCandidates: [] when OFF, no bit 4, not player, main not enemy; ids otherwise;
    TorpedoCandidates results unchanged.
26. ArcRule pulse on: FreeWeapons = weapons with IsInArc(main) 0 (raise -> not free);
    WantedTargets only candidates with Reaches 1 and ArcReaches 1. Rule off -> existing results.
27. Torpedo ArcRule on: IsInArc 1 but ArcReaches 0 -> not wanted; RearmReason -> "nosec".
28. MaintainGroup pulse + ManagesPulseSecondaries 1 -> no StartFiring, record forgotten.
29. Existing suites green unchanged (test_autofire_arc.py calls ArcAllowed(d), ArcSettle(p, id),
    PulseArcScore(5 args)). Then `python tools/check.py` (lint15 + all).

## 9. In-game checks (Debug = 1, fileio patch, read Spaceframe_debug.log; user restarts the game)
V1 Pulse, Auto Fire (PulseRule 3, SecondaryTarget ON, bit 4): ship with pulse weapons both fore and
   aft (e.g. Defiant has fore only -> use a Bedrock ship with aft disruptors), one enemy ahead
   selected, one behind. Expect "Group N plan: main <A> sec <B>" and "+sec <B>"; FIRED lines of
   aft pulse weapons with tgt=<B>.
V2 Same, turn so A is outside every arc: expect "fires at secondary <B>", no FIRED at A.
V3 Torpedo, Auto Fire, TorpedoRule 3 (Galaxy DN): enemy far ahead slightly off-centre ->
   "solution S" with S = arc score; enemy behind within 30 km -> aft FIRED tgt=<B> only when it is
   near the aft cone centre (move it to the cone edge: no aft launch, ARC/plan line shows no sec).
V4 Manual (Auto Fire OFF with L, keys held): pulse/torpedo secondaries: "ADD <B>" only while B is
   inside the allowed %; at the cone/arc edge "ARC-SKIP ..." and no ADD; main fire never stops.
V5 Rule 1/2 (set PulseRule 2, TorpedoRule 2): behavior as before (no "plan" lines for pulse).
Learned candidates after V1-V4 only: "pulse target list without the main fires only weapons
that reach a listed target (unconfirmed)".

## 10. Open questions (user)
Q1 Pulse rule 3 has no projectile-lifetime (range) check today (main): far enemies inside the
   allowed % are fired at. Apply the lifetime check to pulse rule 3 (main + secondary), as rules
   1/2 and torpedo rule 3 do? Default in this spec: NO (PULSE_ARC_LIFETIME = 0), one-line switch.
Q2 Manual filter switch = AutoFire PulseRule/TorpedoRule 3. Want a separate SecondaryTarget
   setting instead (manual filter independent of Auto Fire's rule)? Default: no new setting.
Q3 Versions: AutoFire 0.5 -> 0.6, SecondaryTarget 0.3 -> 0.4? Implementer does NOT bump until
   the user says so.
Q4 Single-fire pulse groups (NX pulse group single fire 1) get secondaries too (as today under
   SecondaryTarget): with one weapon firing at a time a free weapon may take the turn of a
   main-reaching one. Skip pulse secondaries on single-fire groups? Default: no change.
Q5 Torpedo defaults 50/90 % at 30/5 km, hysteresis 10 (= +-15 deg far, +-27 deg near). OK?
