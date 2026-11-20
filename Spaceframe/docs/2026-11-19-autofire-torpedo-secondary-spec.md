# Spec: torpedo secondaries under Auto Fire (AutoFire 0.4 + SecondaryTarget)

Date 2026-11-19, branch feat/secondary-target (77998ee). Author: bc-architect (DESIGN).
Supersedes the ledger ruling "torpedoes at secondary targets under AutoFire are deferred".

## 1. Goal and agreed behavior
With Auto Fire ON and Secondary Target ON (ship has SecondaryTarget bit 2), torpedo tubes that
cannot reach the target Auto Fire is firing at shoot at secondary targets they can reach, by
themselves; tubes that reach the main target keep their torpedoes for it. Manual fire (key held)
is unchanged (Auto Fire hands off, SecondaryTarget TryRearm path as today).

## 2. Design decision (answers to the dossier's open questions)
Q1 Where: option (a). SecondaryTarget only says WHO may be a torpedo secondary (toggle, tech
   bit 2, enemies, SecondaryTorpedoRange, MaxCandidates) through one public function
   `TorpedoCandidates`. AutoFire decides WHEN and with WHICH tube (readiness, arc, solution,
   reserve, spread) and builds the target list itself in the same call that presses the group.
   SecondaryTarget stops touching torpedo groups that AutoFire is driving
   (`AutoFire.ManagesTorpedoSecondaries`). Both lookups are optional (try + hasattr): each module
   works alone exactly as today.
Q2 Trigger: the group is pressed when the main target has a shot (today's rule) OR, if not, when
   at least one secondary has a shot from a READY FREE tube. Priority of main-reaching tubes:
   - main has a shot: list = [main, sec...] (main first; confirmed order rule: a tube fires at
     the first listed target it reaches, so main-reaching tubes go to main);
   - main has no shot: list = [sec...] only, WITHOUT main, and every secondary that a READY
     main-reaching tube also has in arc is dropped, so no main-reaching tube can launch.
Q3 Tap vs hold: tapped groups are rebuilt on every press (StopFiring empties the list on the
   release cycle anyway). Sequence on a press: StartFiring(head, offset) -> StartFiring(sec, zero)
   for each other id -> SetForceUpdate(1) (moved AFTER the secondaries). Release cycle unchanged.
   Held groups (TapFire = 0): feature OFF (open question U1).
Q4 Per-tube API: none exists (exe-weapons.md Q3: no per-weapon target setter is exported; tube
   target is set only inside TryFire). The group target list is the only confirmed path.
Q5 Rules for secondary shots: TorpedoReserve gates them (same TorpedoesLeft check); the solution
   rule is AutoFire's own (TorpedoRule 1: Solution.Score >= TorpedoMinSolution; rule 2: >= 1)
   computed per READY FREE tube that has the secondary in arc (IsInArc(point) == 1); range =
   SecondaryTorpedoRange (inside TorpedoCandidates). Spread: unchanged when main has a shot
   (ApplySpread on main as today); Single (ApplySpread(..., 0.0)) when the head is a secondary
   (spread firing chains may not contain the free tubes - unconfirmed - Single always does).
Q6 Experiments before implementing: none blocking. Everything used is confirmed except the
   "[sec] only, no main" list (see section 9, verified by the first Debug run itself).

## 3. Verified API (all already used in the repo)
- `WeaponSystem.StartFiring(pTarget, TGPoint3)` adds to the list - AutoFire.py:909,
  SecondaryTarget.py:987 (torpedo secondaries in manual fire, confirmed in game, learned.md:59).
- `WeaponSystem.SetForceUpdate(1)` - AutoFire.py:911, SecondaryTarget.py:929.
- `WeaponSystem.StopFiring()` empties the list - AutoFire.py:897, learned.md:64.
- `TorpedoTube.IsInArc(worldPoint)` fixed +-30 deg cone - SecondaryTarget.py:425, learned.md:57.
- `TorpedoTube.GetNumReady()` - AutoFire.py:536.
- `Weapon.CalculateRoughDirection()` - AutoFire.py:537.
- `Solution.Score(pShip, pTarget, vOffset, pTube, vDir, tInfo)` / `GetProjectileInfo(None, pSys)`
  - AutoFire.py:531,537.
- `App.ShipClass_GetObjectByID(None, iID)` - AutoFire.py:616, SecondaryTarget.py:692.
- Core `GetModule(sName)` (active modules only) - Spaceframe.py:396; mock Core.GetModule
  tests/mock_app.py:815.
- `TorpedoSystem.GetNumAvailableTorpsToType` - AutoFire.py:546.
No new engine call.

## 4. File-by-file changes

### 4.1 Modules/AutoFire/Config.py (append after TorpedoReserve block)
```
# 1 = with Secondary Target switched ON for this ship (torpedoes allowed there),
# torpedo tubes that cannot reach the target fire at secondary targets they can
# reach (same firing solution rule as above). Only with TapFire = 1. 0 = off.
SecondaryTorpedoes = 1
```
Switch 1/0, default 1. No Ships.py key (the per-ship control is SecondaryTarget bit 2).

### 4.2 Modules/AutoFire/AutoFire.py
- Global `g_iSecondaryTorpedoes = 1`; LoadConfig: `int(getattr(pConfig, "SecondaryTorpedoes", 1))`.
- New `GetSecondaryTarget()`: `g_pCore.GetModule("SecondaryTarget")` in try; return it only if
  `hasattr(p, "TorpedoCandidates")`, else None. No caching (looked up per press; cheap loop).
- New public `ManagesTorpedoSecondaries(eGroup)` -> 1 iff `g_iSecondaryTorpedoes and g_iTapFire
  and IsEnabled() and not g_dManual.get(eGroup)`; whole body in try, 0 on error.
- New `SecondaryTorpedoPlan(pShip, pTorpedoes, pMain, bMainShot)` -> list of (fScore, iID),
  best score first:
  1. return [] if not g_iSecondaryTorpedoes, not g_iTapFire, pMain None, or
     `TorpedoesLeft(pTorpedoes) <= g_iTorpedoReserve`.
  2. pST = GetSecondaryTarget(); None -> []. `lIDs = pST.TorpedoCandidates(pShip, pTorpedoes,
     pMain)` in try (error -> [] and one Debug log line). Empty -> [].
  3. vMain = pMain.GetWorldLocation(). For each child tube (TorpedoTube_Cast) with
     GetNumReady() > 0: IsInArc(vMain) == 1 -> lMainReady; == 0 -> lFree; raising -> lMainReady
     (same ruling as SecondaryTarget: failure = not free). lFree empty -> [].
  4. tInfo = Solution.GetProjectileInfo(None, pTorpedoes); fMin = g_fTorpedoMinSolution
     (rule 2: 1.0).
  5. For each iID (skip iID == pMain.GetObjID()): pC = ShipClass_GetObjectByID; skip unless
     IsLive(pC). vC = pC.GetWorldLocation(). If not bMainShot and any tube of lMainReady has
     IsInArc(vC) (raise counts as 1): skip. fBest = max Score(pShip, pC, None, tube,
     tube.CalculateRoughDirection(), tInfo) over lFree tubes with IsInArc(vC) == 1 (raise = 0).
     Keep if fBest >= fMin; insert sorted (insertion sort, as SortByDistance).
  6. Every engine call per tube guarded; an exception in one candidate skips that candidate.
- New `PlanTorpedoGroup(pShip, pTorpedoes, pTarget, lTargets, eGroup)` -> (pHead, lSecIDs,
  bHeadSec):
  - pTarget != None: lPlan = SecondaryTorpedoPlan(..., pTarget, 1); return (pTarget, ids, 0).
  - else: lPlan = SecondaryTorpedoPlan(..., lTargets[0], 0); empty -> (None, [], 0);
    pHead = lookup lPlan[0][1] (None -> (None, [], 0)); g_dScore[eGroup] = lPlan[0][0];
    ApplySpread(pShip, pTorpedoes, pHead, 0.0) (forces Single); return (pHead, ids of
    lPlan[1:], 1).
- FireCycle (inside the per-group try, after GroupTarget):
  ```
  lSec = []
  bHeadSec = 0
  pTorpedoes = None
  if pSystem != None:
  	pTorpedoes = App.TorpedoSystem_Cast(pSystem)
  if (pTorpedoes != None) and IsTapped(pSystem) and (g_dFiring.get(eGroup) == None):
  	tPlan = PlanTorpedoGroup(pShip, pTorpedoes, pTarget, lTargets, eGroup)
  	pTarget = tPlan[0]
  	lSec = tPlan[1]
  	bHeadSec = tPlan[2]
  FireGroup(pShip, eGroup, pTarget, pTarget != None, lSec, bHeadSec)
  ```
  The plan runs ONLY on press cycles (g_dFiring None); release cycles cost nothing extra.
- FireGroup(pShip, eGroup, pTarget, bFire, lSec=None, bHeadSec=0) (defaults in the def are
  allowed; callers pass positionally). After `pSystem.StartFiring(pTarget, vOffset)`: if lSec,
  pZero = TGPoint3 0,0,0; for each iID != head id: pSec = ShipClass_GetObjectByID; if IsLive:
  `pSystem.StartFiring(pSec, pZero)` in its own try (Debug log on error). THEN the existing
  SetForceUpdate(1) block (moved below the loop). Debug line: unchanged text when lSec empty
  and not bHeadSec; else `"Group N fires at " + ("secondary " if bHeadSec) + str(headID) +
  ", solution S" + (" +sec " + ids if lSec)`.
- StopAll / Stop / SetEnabled: nothing new (plan is stateless; list emptied by StopFiring).
- Header comment + VERSION: see open question U4.

### 4.3 Modules/SecondaryTarget/SecondaryTarget.py
- New public `TorpedoCandidates(pShip, pSystem, pMain)` -> list of ship IDs, nearest first:
  return [] unless g_iOn, pShip/pSystem/pMain not None, pShip is GetPlayer() (by ObjID),
  `GetMask(pShip) & BIT_TORPEDO`, `pAF.IsEnemy(pMain)` (pAF = GetAutoFire(), None -> []).
  Body: ids of `GetCandidates(pShip, pMain, pSystem, "torpedo")`. Whole body in try, [] on error
  (DebugLog). No state written.
- New `AutoFireOwns(eGroup)`: pAF = GetAutoFire(); 1 iff pAF and
  hasattr(pAF, "ManagesTorpedoSecondaries") and pAF.ManagesTorpedoSecondaries(eGroup); try -> 0.
- MaintainGroup: right after `tKey = (iShip, eGroup)` (before lRecord use):
  ```
  if (sKind == "torpedo") and AutoFireOwns(eGroup):
  	# Auto Fire builds this group's list on every press (see AutoFire PlanTorpedoGroup).
  	ForgetAdded(iShip, eGroup)
  	return
  ```
  No StopAdded (AutoFire's own entries must stay); manual key held -> AutoFireOwns 0 -> old path.
- Header comment line: torpedoes under Auto Fire handled by Auto Fire.

### 4.4 Spaceframe/README.txt (EN/ES/PT)
AutoFire section: one paragraph per language for SecondaryTorpedoes; SecondaryTarget section:
remove "torpedoes under Auto Fire not supported" (if present), say Auto Fire handles them.

### 4.5 Ledger (Spaceframe/docs/secondary-target-progress.md), coordinator after the game test
Proposed rulings (only after the user confirms):
- Torpedo secondaries under AutoFire: AutoFire builds [main, sec...] on every tap when main has a
  shot, [sec...] without main when it has none (secondaries in arc of a ready main-reaching tube
  dropped); SecondaryTarget only supplies candidates and leaves AutoFire-driven torpedo groups
  alone - cost if wrong: free tubes stay idle under AutoFire (as before).
- Secondary-only shots use Single spread - cost if wrong: fewer torpedoes per launch.

## 5. Lifecycle
- No new handler, timer, key binding, UI object or ship-side state. Nothing to remove in Stop.
- Second Quick Battle: GetModule looked up per press, so no stale module/proxy; LoadConfig reads
  SecondaryTorpedoes at Start.
- Battle end: AutoFire.Stop stops its timer before ships die (existing); the plan only runs
  inside FireCycle with IsEnabled() (player alive) and IsLive on every looked-up candidate.
- Player ship change: IsEnabled() 0 -> SetEnabled(0) (existing); TorpedoCandidates also checks
  the ship is the player's.

## 6. Data flow and per-cycle budget (FireInterval 0.1 s, presses every 0.2 s)
Press cycle, torpedo group with N tubes, C candidates (MaxCandidates 4): N GetNumReady + N
IsInArc(main) + per candidate up to N IsInArc + Score only for ready free tubes in arc
(Galaxy DN: <= 14 + 14 + 4*14 IsInArc, a few Score) + SecondaryTarget GetCandidates (enemy
list, sort). Only when SecondaryTarget is ON with bit 2; otherwise one GetModule loop.
Nothing cached between cycles except module globals; ships always by ID.

## 7. Failure modes
- Candidate destroyed between plan and press: IsLive check at StartFiring time; engine drops
  dead targets itself.
- Missing torpedo system / no tubes: TorpedoTube_Cast None -> lFree empty -> [].
- IsInArc raising: tube counted main-reaching (never free); candidate conflict counted.
- SecondaryTarget not loaded, disabled, toggle OFF, no bit 2: [] -> AutoFire exactly as today.
- AutoFire not loaded/disabled: AutoFireOwns 0 -> SecondaryTarget exactly as today.
- An exception in the plan: caught by FireCycle's per-group try (existing) -> group released;
  phasers/pulse untouched. Prefer catching inside the plan so main fire still happens: wrap the
  PlanTorpedoGroup call; on exception keep (pTarget, [], 0) and log once (g_bTorpPlanLogged).
- Multiplayer: Spaceframe off unless EnableInMultiplayer (core); nothing new.
- Torpedo waste guard: a secondary launch needs ready free tube + arc + solution >= rule +
  reserve; engine caps 1 launch / 0.5 s per system; no re-arm loop (each tap re-evaluates).

## 8. Mock tests (py3, new file tests/test_autofire_torp_secondary.py)
Setup like test_autofire_torps.setup (tap=1, rule=1, Score stub) plus a fake SecondaryTarget
module in core.modules with `TorpedoCandidates` returning given ids; mock_app Tube with
pPos/vDir so IsInArc follows the cone (fwd tube dir +x, aft tube dir -x); enemies registered so
ShipClass_GetObjectByID finds them; Mission enemy group includes them.
1. main shot + aft tube ready + secondary behind -> calls == [start main, start sec] on press.
2. main has no ready fwd tube, secondary behind -> [start sec] only (no main), Single spread set.
3. main shot poor (Score below min) and a ready fwd tube also has the secondary in arc -> no start.
4. free tube ready but Score below TorpedoMinSolution vs secondary -> no secondary start.
5. TorpedoRule 2 uses 1.0 threshold for secondaries.
6. TorpedoesLeft <= TorpedoReserve -> no secondary (and no main) start.
7. No SecondaryTarget module (core.modules empty) -> behavior identical to test_tap_fire_alternates.
8. SecondaryTorpedoes = 0 -> no secondary start; TapFire = 0 -> no secondary start.
9. Release cycle: second FireCycle -> "stop", no plan call (count TorpedoCandidates calls == 1
   after 2 cycles).
10. Manual key (g_dManual[group] = 1) -> no start at all; ManagesTorpedoSecondaries == 0.
11. Candidate dead between plan and press -> skipped, head still started.
12. IsInArc raising on a tube -> that tube never free, no exception escapes.
13. Order: SetForceUpdate recorded after the secondary starts (add `self.forced` list/counter in
    mock WeaponGroup.SetForceUpdate recording len(self.calls) at call time; do NOT append to
    calls - existing tests compare calls lists).
SecondaryTarget (tests/test_secondary_cycle.py additions):
14. TorpedoCandidates: [] when OFF, no bit 2, not player ship, main not enemy; ids nearest first
    within SecondaryTorpedoRange otherwise.
15. MaintainGroup on a torpedo group with fake AutoFire.ManagesTorpedoSecondaries -> 1: no
    StartFiring/StopFiringAtTarget, record forgotten; -> 0: old behavior (existing tests green).
Game-only checks: section 9.

## 9. In-game verification (Debug = 1, fileio patch, read Spaceframe_debug.log)
Galaxy DN (7 fwd + 7 aft tubes), Quick Battle with 3 enemies, one ahead (main, selected) and one
behind within 30 km; Auto Fire ON, Secondary Target ON, no fire key pressed.
- V1 (main shot + secondary): expect `Group 2 fires, solution S +sec <id>` and FIRED lines
  `Forward Tube k tgt=<main>` then, interleaved or after, `Aft Tube k tgt=<sec>`.
- V2 (forward tubes empty, enemy behind): expect `Group 2 fires at secondary <id>` and FIRED
  `Aft Tube k tgt=<sec>` every ~0.5-0.6 s; NO forward tube launches. If V2 shows the group
  pressed but no aft launch, the "[sec] only" list is the cause: fallback = put main first
  ([main, sec]) when no ready tube has main in arc (same configuration as the confirmed manual
  re-arm), a 3-line change in PlanTorpedoGroup.
- V3: switch Secondary Target OFF (J): torpedoes back to main-only, aft tubes idle.
Candidates for learned.md only after V1-V2: "torpedo list without the selected target fires
only tubes that reach a listed target (unconfirmed)".

## 10. Rulings by the user (2026-11-20) - these OVERRIDE the text above where they differ
U1 TapFire = 0 (held torpedo groups) IS supported. A held group is also planned, but only at the
   moment AutoFire is about to (re)start it: g_dFiring[eGroup] is None, or the group is not
   IsFiring(). Then the same sequence runs (StartFiring(head), StartFiring(each sec), then
   SetForceUpdate(1)). While a held group keeps firing, no re-plan (list stays; the engine stops
   the group when the tubes are empty and the next cycle restarts it with a fresh plan). Changes:
   - FireCycle condition: `(pTorpedoes != None) and ((g_dFiring.get(eGroup) == None) or
     (not IsFiring(pSystem)))` instead of IsTapped(...) and g_dFiring None.
   - SecondaryTorpedoPlan step 1 and ManagesTorpedoSecondaries: drop the TapFire requirement
     (keep SecondaryTorpedoes switch, IsEnabled, not manual).
   - Tests: add a TapFire = 0 case for tests 1, 2 and a "held and still firing: no re-plan" case;
     test 8 keeps only the SecondaryTorpedoes = 0 half.
   - Config.py comment: remove "Only with TapFire = 1".
U2 Same threshold (TorpedoMinSolution / TorpedoRule) for secondary shots. No new setting.
U3 Secondary-only shots (head is a secondary) use Single spread. When main has a shot: unchanged.
U4 AutoFire VERSION 0.4 -> 0.5. SecondaryTarget.py VERSION "0.2" is stale: set it to "0.3"
   (README already says v0.3) and make sure the header comment matches.
