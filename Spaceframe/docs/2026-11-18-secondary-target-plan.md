# Secondary Target Implementation Plan

> **For agentic workers:** execute task by task with the project workflow in `CLAUDE.md`: `bc-implementer` writes the code and its py3 mock test, `python tools/check.py` must be green, `bc-auditor` before every install, then `python tools/deploy.py install Spaceframe` and WAIT for the user's in-game test. Never commit unless the user asks. Steps use checkbox syntax.

**Goal:** Spaceframe module `SecondaryTarget` (phase 1: phasers and pulse) that makes weapons which cannot reach the player's main target shoot at other enemies, without taking fire from the main target.

**Architecture:** Every `Interval` the module looks at each weapon group that is firing at the main target, and keeps its WeaponSystem target list as `[main, secondary...]` (`StartFiring`/`StopFiringAtTarget`). The engine distributes weapons by reach and the main target, being first in the list, keeps the weapons that reach it. `SetSingleFire(0)` is lifted on the live system and always restored.

**Tech Stack:** Python 1.5.2 game scripts (`tools/lint15.py` rules), py3 mocks in `Spaceframe/tests/` (`mock_app.py`), Spaceframe core v0.6 module API (see `Modules/AutoFire/AutoFire.py`).

**Spec:** `Spaceframe/docs/2026-11-18-secondary-target-design.md` (sections 3, 7, 9, 10, 12). Probe evidence: `secondary-target-experiment-spec.md`.

## Global Constraints

- Python 1.5.2 hard rules from `CLAUDE.md` (no `+=`, comprehensions, `x if c else y`, keyword args, nested scopes, `continue` inside `try`, etc.); CRLF, ASCII, tabs under `scripts/`.
- No Foundation / FoundationTech / KM; Spaceframe module, vanilla files untouched; `AutoFire` is not edited.
- Config: percentages 0-100, switches 1/0, `Interval` in seconds, `Def = -1` = module default.
- Ships.py value: `"SecondaryTarget": N`, bit sum 1 phaser, 2 torpedo, 4 pulse; `Def` = Config `Weapons` (7); `0` = off.
- Only enemies of the mission (`GetEnemies`), never aliens/neutrals/friendlies; never touch ships in `Stop()`.
- The single-fire property is always restored to the value read, by ship ID, with the ship live; never forced to 1.
- Engine calls guarded; an error in one group stops only that group.
- Debug output only via `App.CPyDebug().Print` when `Debug = 1`.

## Review Focus

- Tick runs with no enemy besides the main target, or none selected: must do nothing and leave no list changes.
- Player key released: the game empties the list; next cycle/keyboard event re-adds secondaries once, not twice.
- Main target dies while secondaries are in the list: the first-listed target changes; the module must not leave stale entries or stop the group.
- Player changes ship or the ship is destroyed mid-fire: restore only if live, otherwise skip silently, no CTD.
- Second Quick Battle without leaving the game: no duplicate handlers or timers, no leftover single-fire change.

---

### Task 0: Verification round (gate, no module code)

**Files:**
- Modify: `Spaceframe/scripts/Custom/Spaceframe/Modules/STProbe/STProbe.py`, `Spaceframe/tests/test_stprobe.py`
- Modify (after the user's run): `docs/api/learned.md`

**Interfaces:**
- Consumes: STProbe tests SINGLEFIRE, MULTI_TORP, MANUAL, ORDER (existing).
- Produces: a user-run checklist whose results settle design section 9 items 1-5; Task 2 and Task 4 depend on items 2 and 3 (shared property).

- [ ] **Step 1:** Make SINGLEFIRE take the system kind (phaser, pulse, torp) and add variant "prop0 + MANUAL/ORDER" so MANUAL and ORDER can run with single-fire lifted. Test: mock pulse/torp systems pass through SINGLEFIRE and restore (`restored: ok`).
- [ ] **Step 2:** Add test SHARED: reads `IsSingleFire` of the player's phaser system and of one enemy ship of the same class, lifts the player's, rereads the enemy's, restores; the banner says `shared: yes/no`. Test: fake enemy proxy whose property object is the same/different.
- [ ] **Step 3:** Add reach probe to INFO for `TorpedoTube.CanHit(point)` and `PulseWeapon.CanHitTarget(point, vector)` returning per weapon, and a 3-enemy variant of ORDER (A, B, C). Test: mock returns recorded.
- [ ] **Step 4:** `python tools/check.py` green; `bc-auditor`; `deploy.py install Spaceframe`; the user runs: SHARED (then starts a second Quick Battle with the same ship class and runs INFO: is `single` still the original?), SINGLEFIRE on torp and pulse, MANUAL with prop0, MULTI_TORP, INFO reach lines, ORDER with 3 enemies.
- [ ] **Step 5:** Record confirmed facts in `docs/api/learned.md`; if SHARED is yes, apply the fallback of design section 12 (lift only while the group fires) to Tasks 2 and 4 before they start.

### Task 1: Module skeleton, Config, Ships.py, lifecycle

**Files:**
- Create: `Modules/SecondaryTarget/__init__.py`, `Modules/SecondaryTarget/Config.py`, `Modules/SecondaryTarget/SecondaryTarget.py`, `Spaceframe/tests/test_secondary_lifecycle.py`
- Modify: `Spaceframe/scripts/Custom/Spaceframe/Ships.py` (comment block + the user's line only if the user asks; propose `"SecondaryTarget": Def` in All, do not overwrite the user's file blindly: `deploy.py pull` first)

**Interfaces:**
- Produces: `NAME = "SecondaryTarget"`; `LoadConfig()`; `GetMask(pShip) -> int` (bit sum from `g_pCore.GetShipTech(pShip, NAME, 0)`, `-1` -> Config `Weapons`); `Start(pCore)`, `Stop()` following the signatures of `AutoFire.Start/Stop`; `Tick()` as the timer target (no-op stub in this task); Config names `Weapons, Interval, MaxCandidates, SecondaryRange, SecondaryTorpedoMinSolution, Debug` with defaults of the design table.

- [ ] **Step 1:** Write `test_secondary_lifecycle.py`: `test_start_twice_then_stop_registers_once` (handler add count == remove count, one timer), `test_stop_touches_no_ship` (recorder empty), `test_mask_def_uses_config` (Def -> 7, `0` -> 0, `5` -> phaser+pulse), `test_no_tech_no_timer`.
- [ ] **Step 2:** Run `python tools/check.py` and see the new test fail.
- [ ] **Step 3:** Implement the module like `AutoFire.py` (config reload at `Start`, own timer only while the player's ship has the tech, handlers removed in `Stop` with the same triple).
- [ ] **Step 4:** `python tools/check.py` green; `bc-auditor`.

### Task 2: Single-fire lift and restore

**Files:**
- Modify: `SecondaryTarget.py`; Test: `Spaceframe/tests/test_secondary_singlefire.py`

**Interfaces:**
- Consumes: Task 1 module state; the probe's `GetProp/ReadState/RestoreState` patterns in `STProbe.py` (property via `pSystem.GetProperty()`, raw object fallback).
- Produces: `LiftSingleFire(pShip, pSystem, eGroup)` records `{shipID, group: original IsSingleFire}` in `g_dLifted` and sets 0; `RestoreSingleFire(pShip)` restores each recorded value for that ship ID if the ship is live (else just forgets it); `ForgetAll()`.

- [ ] **Step 1:** Tests: `test_lift_records_original_and_sets_zero`, `test_restore_writes_original_not_one` (original 0 stays 0), `test_restore_skipped_when_ship_gone` (no engine call), `test_lift_twice_keeps_first_original`, `test_error_in_lift_still_recorded` (partial change is restored).
- [ ] **Step 2:** Run, see failures. **Step 3:** Implement; **Step 4:** green, `bc-auditor`.

### Task 3: Candidates and free weapons

**Files:**
- Modify: `SecondaryTarget.py`; Test: `Spaceframe/tests/test_secondary_candidates.py`

**Interfaces:**
- Consumes: AutoFire helpers imported from `Custom.Spaceframe.Modules.AutoFire.AutoFire` (`GetEnemies(pShip)`, `SortByDistance(pShip, lShips)`, `IsLive(pTarget)`, `GetDistance(pFrom, pTarget)`, `GetOffset`); if the import fails the module disables itself.
- Produces: `GetCandidates(pShip, pMain) -> list of enemy ships` (live, not cloaked, not main, nearest `MaxCandidates`, within `SecondaryRange`-scaled reach of some weapon of the group kind); `FreeWeapons(pSystem, pMain, sKind) -> list` (weapons without firing condition on the main target: phaser `CanHit(main.GetWorldLocation())`, pulse `CanHitTarget(point, vZero)` when Task 0 confirmed it, otherwise all weapons counted as free); `WantedTargets(pShip, pSystem, pMain, sKind) -> list of target IDs` (candidates that at least one free weapon reaches).

- [ ] **Step 1:** Tests: `test_main_excluded`, `test_friendly_and_neutral_never_candidates`, `test_max_candidates_nearest`, `test_weapon_reaching_main_is_not_free`, `test_candidate_needs_a_free_weapon_that_reaches`, `test_no_enemies_returns_empty`.
- [ ] **Step 2-4:** fail, implement, green, `bc-auditor`.

### Task 4: List maintenance and cycle

**Files:**
- Modify: `SecondaryTarget.py`; Test: `Spaceframe/tests/test_secondary_cycle.py`

**Interfaces:**
- Consumes: Tasks 2 and 3; game fire events like `AutoFire.GetFireEvents()` (`ET_INPUT_FIRE_PRIMARY/SECONDARY/TERTIARY`).
- Produces: `Tick()` (cycle of design section 7: pre-conditions, only groups with `IsFiring()` at the main target, `LiftSingleFire`, add missing secondaries with `if not IsInTargetList(t): StartFiring(t, zero)`, `StopFiringAtTarget` for the ones no longer wanted, each group in its own `try`); `OnFireKey(pObject, pEvent)` handler that runs the same group maintenance immediately after key press/release and ends with `CallNextHandler`; `StopGroups()` used when the player's ship changes (restores via Task 2 only with the ship live).

- [ ] **Step 1:** Tests: `test_secondaries_added_in_order_after_main`, `test_group_not_firing_untouched`, `test_key_release_list_cleared_then_readded_once`, `test_main_dies_group_continues`, `test_candidate_gone_removed_from_list`, `test_group_error_isolated`, `test_player_ship_change_restores_only_if_live`, `test_idle_cost_no_calls_without_tech`.
- [ ] **Step 2-4:** fail, implement, green, `bc-auditor`.

### Task 5: Docs, install, in-game gate (phase 1 done)

**Files:**
- Modify: `Spaceframe/README.txt` (EN/ES/PT section + Ships.py line), `Spaceframe/docs/secondary-target-progress.md` (new ledger: rulings with "cost if wrong"), `docs/api/learned.md`

- [ ] **Step 1:** README section and header version bump; progress ledger with every ruling made while building.
- [ ] **Step 2:** `python tools/check.py` green; `bc-auditor` on the whole module; `deploy.py status` (pull if `edited`), `deploy.py install Spaceframe`; tell the user to restart the game.
- [ ] **Step 3:** The user tests in game with 2-3 enemies: phasers and pulse, manual key and AutoFire; reports. Do not claim it works until they confirm; escalate to `bc-architect` per `CLAUDE.md` if a bug survives 2 test cycles.

### Task 6: Phase 2, torpedoes (separate plan)

Written only after Task 0 and Task 5 results: either the torpedo system target list (if MULTI_TORP and single-fire lift work) or launch redirect on `ET_TORPEDO_ENTERED_SET` with `Torpedo.SetTarget`, with `SecondaryTorpedoMinSolution` and `TorpedoReserve`. Not in this plan's scope.
