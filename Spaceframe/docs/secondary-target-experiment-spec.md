# STProbe - secondary-target experiment (spec for bc-implementer)

Date: 2026-11-18. Author: bc-architect (DESIGN, experiment only).
Purpose: answer, in game and on screen, whether the engine lets weapons of ONE
weapon system fire at DIFFERENT targets at the same time, before the
"SecondaryTarget" module is designed. Throwaway: removed after the user's test.

## 0. Already settled (no need to probe)

Sources: SWIG argument formats in `stbc.exe` (`"Ofi:Weapon_Fire"` = self, float,
int; found with a byte scan of the exe), vanilla bytecode via `tools/dis15.py`.

| Fact | Evidence |
|---|---|
| Player fire key = `pSystem.StartFiring(pShip.GetTarget(), pShip.GetTargetOffsetTG())` + `pSystem.SetForceUpdate(1)`; release = `pSystem.StopFiring()` (no args, whole system) | `TacticalInterfaceHandlers.pyc:FireWeapons:362-368` |
| `WeaponSystem.StartFiring` = `O|OO`: target and offset both optional | exe format string |
| A weapon system holds a TARGET LIST: `StartFiring` once per target, guarded by `IsInTargetList(t)` | `AI/PlainAI/StarbaseAttack.pyc:FireWeapons:113-115` (loop over all targets, same system) |
| `StopFiringAtTarget(t)` (`OO`) removes one target; `StopFiring()` (`O`) stops all | `AI/Preprocessors.pyc:FireScript.FireSystemAtTarget:469`, `StopFiring:274` |
| `IsInTargetList(t)` `OO`, `RemoveFromTargetList(t)` `OO`, `ClearTargetList()` `O`, `UpdateTargetList()` `O` (no args) | exe format strings |
| There is NO per-weapon target setter: `Weapon` has no `SetTarget`; `Weapon.Fire(float, int)` and `Weapon.FireDumb(float, int)` take no target | exe: `Ofi:Weapon_Fire`, `Ofi:Weapon_FireDumb`; App-index has no `Weapon.SetTarget` |
| `Weapon.FireDumb(0, 1)` = fire one tube straight ahead (AI dumb fire) | `AI/Preprocessors.pyc:FireScript.FireSystemAtTarget:458` |
| `Weapon.SetFiring(int)`, `Weapon.StopFiring()`, `Weapon.IsFiring()`, `Weapon.CanFire()`, `Weapon.GetTargetID()` exist (signatures `Oi`/`O`) | exe format strings |
| Torpedo retarget after launch: `Torpedo.SetTarget(objID)` (`Ol`), `Torpedo.SetTargetOffset(TGPoint3)` (`OO`), `Torpedo.GetTargetID()`, `GetParentID()`; catch new torpedoes with broadcast `ET_TORPEDO_ENTERED_SET`, torpedo = `App.Torpedo_Cast(pEvent.GetDestination())` | exe; `Maelstrom/Episode8/E8M2/E8M2.py:1672-1696, 4552` |
| `ET_WEAPON_FIRED`: `pEvent.GetSource()` is the weapon that fired | `Maelstrom/Episode6/E6M2/E6M2.pyc:PlayerWeaponFired:971` |
| `PulseWeapon.CanHitTarget` takes TWO args (`OOO`), not one; `TorpedoTube.CanHit` and `PhaserBank.CanHit` take one (`OO`) | exe format strings |

Consequence for the design: "one chosen weapon -> one chosen target" cannot be
ordered from Python. The only per-target mechanism is the system's target list,
and the ENGINE decides which weapon fires at which listed target. The probe
therefore measures that engine policy, plus two per-weapon levers (hold one
weapon; retarget a launched torpedo).

Side finding (not for this probe to fix): `AutoFire.PulseReady`
(`Modules/AutoFire/AutoFire.py:628-636`) calls `CanHitTarget(pTarget)` with one
arg; per the exe format it raises TypeError and the `except` returns 1, so the
pulse arc check is probably never applied. `learned.md` line "PulseWeapon.CanHitTarget(pTarget)"
is likely wrong. Test T1 settles the right form.

## 1. Questions -> tests

| Q | Test(s) |
|---|---|
| Q1 torpedo tube on B while group on A | T3 MULTI_TORP, T10 TORP_RETARGET |
| Q2 pulse weapon on B | T4 MULTI_PULSE |
| Q3 phaser banks of one system on A and B at once; per-weapon stop | T2 MULTI_PHASER, T8 HOLD_ONE |
| Q4 conflict with manual fire key; release only own weapons | T7 MANUAL, T6 RELEASE_B |
| Q5 signatures, IsFiring/GetTargetID, engine priority | T1 INFO, T5 ORDER, T9 FIRE_ONE |

## 2. Files

New (all CRLF, ASCII, tabs, Python 1.5.2, `lint15` clean):
- `Spaceframe/scripts/Custom/Spaceframe/Modules/STProbe/__init__.py` - empty.
- `Spaceframe/scripts/Custom/Spaceframe/Modules/STProbe/Config.py`:
  ```
  # STProbe - throwaway experiment. Delete the STProbe folder when done.
  AnyShip = 1		# 1 = works on any player ship, 0 = only ships with "STProbe": 1 in Ships.py
  SelectKey = "K"		# next test (lower-case k only; Shift+K is a game key)
  RunKey = "O"		# run / abort the selected test (lower-case o only)
  SampleSeconds = 2.0	# game seconds each firing window lasts
  BannerSeconds = 8.0	# how long result lines stay on screen
  ```
- `Spaceframe/scripts/Custom/Spaceframe/Modules/STProbe/STProbe.py`
- `Spaceframe/tests/test_stprobe.py`

Not touched: core `Spaceframe.py`, core `Config.py` (a module folder not listed
in `Config.Modules` loads by default, `Spaceframe.py:288-292`), `Ships.py`
(AnyShip = 1 avoids editing the user's Ships.py), AutoFire, StatusHUD, vanilla.
Do not bump any version. Removal after the experiment: delete the folder in the
repo; in the game set `"STProbe": 0` in core `Config.Modules` or delete
`scripts\Custom\Spaceframe\Modules\STProbe\` (coordinator tells the user).

Keys: default bindings (`DefaultKeyboardBinding.pyc`) use every lower-case
letter except k, l, o; l is AutoFire's toggle. So `k` = select, `o` = run.

## 3. STProbe.py structure

Module globals only (no nested scopes). Handler names as strings:
`PKG = "Custom.Spaceframe.Modules.STProbe.STProbe"`, `KEY_HANDLER = PKG + ".OnKeyboard"`,
`FIRE_HANDLER = PKG + ".OnManualFire"`, `FIRED_HANDLER = PKG + ".OnWeaponFired"`,
`TORP_HANDLER = PKG + ".OnTorpedoEntered"`.

State: `g_pCore`, `g_pTopWindow`, `g_pMission`, `g_iSel` (index in TESTS),
`g_dRun` (None or dict of the running test), `g_dResults` (test name -> list of
lines), `g_iKeySel`, `g_iKeyRun`, config values.

`TESTS = ("INFO", "MULTI_PHASER", "MULTI_TORP", "MULTI_PULSE", "ORDER",
"RELEASE_B", "MANUAL", "HOLD_ONE", "FIRE_ONE", "TORP_RETARGET")`

### Helpers (each App call guarded)
- `Call(sLabel, pFunc, tArgs)` -> `(1, value)` or `(0, "ExcType: msg")` using
  `apply(pFunc, tArgs)` in try/except. Every engine call in a test goes through
  `Call` and every failure is appended to the run's `lErrors` as `sLabel + " " + msg`.
- `Show(lLines)`: for i, line: `MissionLib.TextBanner(None, App.TGString(line), 0.02, 0.12 + 0.035 * i, g_fBanner, 12, 0, 0)`
  (form used by `BridgeHandlers.pyc:ShowSaved:1516`), each in try/except. Max 6
  lines (truncate to 70 chars). Also `g_pCore.Log(NAME, line)` (prints only with Debug = 1).
- `GetPlayer()`, `GetMission()`, `IsLive()`, `GetEnemies()`: copy AutoFire
  (`AutoFire.py:97-112, 358-395`).
- `GetAB(pShip)`: A = `App.ShipClass_Cast(pShip.GetTarget())` if live and enemy;
  B = nearest live enemy other than A. Return `(None, None, reason)` if missing.
- `FindSystem(pShip, sKind)`: loop `WG_PRIMARY, WG_SECONDARY, WG_TERTIARY`;
  `pShip.GetWeaponSystemGroup(e)`; kind by cast: `"torp"` TorpedoSystem_Cast,
  `"pulse"` PulseWeaponSystem_Cast, `"phaser"` PhaserSystem_Cast. Return
  `(eGroup, pSystem)` or `(None, None)`. Phasers = first group with PhaserSystem.
- `GetWeapons(pSystem)`: `App.Weapon_Cast(pSystem.GetChildSubsystem(i))` for i
  in `range(GetNumChildSubsystems())` (as `Preprocessors.pyc:455`).
- `Reach(pWeapon, sKind, pTarget)` -> 1 / 0 / "E":
  phaser `App.PhaserBank_Cast(w).CanHit(pTarget.GetWorldLocation())`;
  torp `App.TorpedoTube_Cast(w).CanHit(pTarget.GetWorldLocation())` (arg kind unconfirmed: "E" on error);
  pulse `App.PulseWeapon_Cast(w).CanHitTarget(pTarget, vZero)` with
  `vZero = App.TGPoint3(); vZero.SetXYZ(0.0, 0.0, 0.0)`.
- `Code(iID, dRun)`: `"A"` if iID == idA, `"B"` if == idB, `"-"` if None/0/NULL_ID, else `"X"`.
- `Lookup(dRun)`: ship, A, B re-fetched by ID each step with
  `App.ShipClass_GetObjectByID(None, id)`; any missing/dead/dying -> abort the
  run with "ABORT: <who> gone" (no further calls into ships).
- `Now()`: `App.g_kUtopiaModule.GetGameTime()` (as `Preprocessors.pyc:351`).

### Pure functions (mock-tested)
- `Classify(dSeen, dReach)` -> dict: `onA`, `onB` (weapons ever seen firing at
  A / B), `simul` (1 if a single sample had one weapon on A and another on B),
  `bothReach` (indices reaching A and B), `bothPickA`, `bothPickB`,
  `onlyB` (reach B not A), `onlyBFired` (of those, fired at B).
  `dSeen[i]` = dict code -> sample count; `dReach[i]` = (rA, rB).
- `Verdict(dClass)`: `"PASS"` if simul; `"INCONCLUSIVE geometry"` if no weapon
  reaches only one of A/B (tell user to turn the ship); else `"FAIL"`.
- `WeaponLine(dSeen, dReach)`: e.g. `"w0 r:AB f:A  w1 r:B f:B  w2 r:- f:-"`, split
  over 2 lines max.

### Keyboard (copy AutoFire.BindKey/UnbindKey/OnKeyboard pattern, `AutoFire.py:182-276`)
Raw `ET_KEYBOARD` on `App.TopWindow_GetTopWindow()`. Consume ONLY KS_KEYDOWN of
lower-case unicode `g_iKeySel` (107) / `g_iKeyRun` (111) and only if
`Allowed(pPlayer)` (AnyShip or `g_pCore.GetShipTech(pShip, "STProbe", 0)`);
everything else `pObject.CallNextHandler(pEvent)`.
- `k`: if a test runs: `Abort("aborted")`. Else `g_iSel = (g_iSel + 1) % len(TESTS)`
  and `Show(["STProbe " + str(g_iSel + 1) + "/10 " + TESTS[g_iSel] + ": " + HINT[name]] + g_dResults.get(name, []))`.
- `o`: if a test runs: `Abort("aborted")`; else `Begin(TESTS[g_iSel])`.

### Run engine
`Begin(sName)`: preconditions -> banner "STProbe <name>: NOT RUN - <reason>":
player ship allowed and alive; AutoFire off (`g_pCore.GetModule("AutoFire")`
and its `IsEnabled()`; say "press L to turn Auto Fire off"); ship not cloaked;
A and B found (except INFO); system of the needed kind found.
Then builds `g_dRun = {"name", "phase": 0, "ship", "idA", "idB", "group", "kind",
"t": Now() + delay, "seen": {}, "reach": {}, "fired": {}, "errors": [], "notes": [], "started": 0}`
and calls the test's phase-0 function. `Tick(lShips)` calls `Step()` when
`g_dRun != None`: `Lookup`; `Sample()` (if the phase samples); when
`Now() >= t`, next phase function. `Finish(lLines)` = `Release()`, store in
`g_dResults`, `Show`, `g_dRun = None`. `Abort(s)` = `Release()` + Show + clear.
`Release()`: only if `started` and the ship is still live: `pSystem.StopFiring()`
via Call (system re-fetched with `GetWeaponSystemGroup(group)`).

`Sample()`: for each weapon index i: `IsFiring()`; if 1, `Code(GetTargetID())`
-> `seen[i][code] += 1`; records simul for this sample. Cost: <= 20 weapons x 2
calls every 0.25 s, only while a test runs; nothing per tick when idle.

`OnWeaponFired(pObject, pEvent)` (broadcast on mission): if a run is active,
`pW = App.Weapon_Cast(pEvent.GetSource())`, index found by `GetName()` among the
run's cached weapon names; `fired[i][Code(pW.GetTargetID())] += 1`. Ends with
`pObject.CallNextHandler(pEvent)` in try (vanilla pattern `E8M2.py:1696`).

`OnManualFire(pObject, pEvent)`: like `AutoFire.OnManualFire`; only for MANUAL
test: store `("press"|"release", eType)` in `g_dRun["notes"]` and set the
run's `t = Now() + 0.5` with `phase` = "after press"/"after release".

`OnTorpedoEntered(pObject, pEvent)`: only when TORP_RETARGET armed (see T10). Ends with CallNextHandler.

### Tests (A = player's target, B = second enemy; "MULTI(sys, X, Y)" =
`Call StopFiring()`, `StartFiring(X, vZero)`, `StartFiring(Y, vZero)`,
`SetForceUpdate(1)`, `started = 1`, then record `IsInTargetList(A)`, `IsInTargetList(B)`)

1. **INFO** (no A/B needed, no firing): banner lines
   - per group: kind, weapon count, `GetGroupFireMode()`, `IsSingleFire()`;
   - `Weapon.GetTargetID()` / `IsFiring()` of weapon 0 of each group (idle values);
   - if A exists and a pulse system: `CanHitTarget(A)` 1-arg result/err and
     `CanHitTarget(A, vZero)` result/err; and `CanHitTarget(A.GetWorldLocation(), vZero)`;
   - if A exists and torps: `TorpedoTube.CanHit(A.GetWorldLocation())` result/err;
   - `pShip.GetAI() != None` -> "WARNING ship has AI (tactical orders?)".
2. **MULTI_PHASER**: cache reach (A,B) per bank; MULTI(phasers, A, B); sample for
   SampleSeconds; Finish lines:
   `"T2 PHASER list A:1 B:1  onA:2 onB:1 simul:1  PASS"`,
   `"both-reach picked A:n B:m  onlyB fired:k/j"`, WeaponLine (2 lines), errors.
3. **MULTI_TORP**: same on torpedo system; window = max(SampleSeconds, 4.0);
   uses `fired` (events) as well as `seen`. Line adds `NumReady` sum at start.
4. **MULTI_PULSE**: same on pulse system (window 4.0).
5. **ORDER**: like MULTI_PHASER but `StartFiring(B)` first, then `StartFiring(A)`.
   Line: `"T5 ORDER(B first) both-reach picked A:n B:m"` (compare with T2).
   If no phaser system, use the first non-tractor system found.
6. **RELEASE_B**: phase 0 MULTI(phasers, A, B); phase 1 at +2 s: snapshot
   (inA, inB, onA, onB this sample), `StopFiringAtTarget(B)`; phase 2 at +4 s:
   snapshot; `StartFiring(B, vZero)` + `SetForceUpdate(1)`; phase 3 at +5 s:
   `RemoveFromTargetList(B)`; phase 4 at +7 s: snapshot; Finish. Lines: the three
   snapshots `"S1 A1 B1 onA2 onB1 | S2 ... | S3 ..."`.
7. **MANUAL** (primary group, normally phasers): phase 0 MULTI(primary, A, B);
   banner "HOLD fire (F / left mouse) 2 s, then RELEASE" ; snapshot on next
   step after the press (+0.5 s) and after the release (+0.5 s): inA, inB,
   onA, onB, `IsFiring()`. Then phase "readd": `StartFiring(B, vZero)` only,
   `SetForceUpdate(1)`, snapshot +2 s: onB. Timeout 20 s without press ->
   Finish "no press seen". Lines:
   `"press: A1 B1 onA2 onB1 | release: A0 B0 firing0 | B alone: onB1"`.
8. **HOLD_ONE** (phasers; pulse if no phasers): phase 0 MULTI(A, B); phase 1 at
   +2 s: pick weapon w seen on B (else on A); `w.StopFiring()`; sample w every
   step, record seconds until it fires again (or "stayed off"); phase 2 at +4 s:
   `w.SetFiring(0)`; same measurement to +6 s; Finish. Line:
   `"w3 StopFiring: off 0.25s then refired | SetFiring(0): stayed off"`, plus
   whether other weapons kept firing (onA/onB during phases).
9. **FIRE_ONE** (torps; pulse if none): phase 0: `StopFiring()`, `ClearTargetList()`;
   tube t = first with `GetNumReady() > 0` (pulse: charge >= min);
   `t.Fire(0.0, 1)` -> record return/err; window 2 s: fired events of t and
   `t.GetTargetID()`; phase 1: `StartFiring(A, vZero)` (list = A), next ready
   tube u: `u.Fire(0.0, 1)`; window 2 s; phase 2: `u2.FireDumb(0.0, 1)`. Lines:
   `"Fire no-list: ret=.. fired=0/1 tgt=-"`, `"Fire list A: fired=.. tgt=A"`, `"FireDumb: fired=.."`.
10. **TORP_RETARGET**: arm for 20 s; banner "FIRE a torpedo at A now". In
   `OnTorpedoEntered`: `pT = App.Torpedo_Cast(pEvent.GetDestination())`; accept
   if `pT.GetParentID() == ship id` OR (fallback) `pT.GetTargetID() == idA`;
   record parent, old target code, `pT.SetTarget(idB)`, `pT.SetTargetOffset(vZero)`,
   new target code; disarm. Finish lines:
   `"torp parent=ship tgt A->B  SetTarget ok"` + "watch: does it turn to B?".
   The hit itself is judged by the user's eyes (B's shields/hull).

HINT texts (shown on select) say what to set up, e.g. MULTI: "A ahead, B to the
side/behind; red alert; Auto Fire off; press o".

## 4. Lifecycle

- `Start(pCore)`: `Stop()`; store core; `reload` Config; read config into
  globals; `BindKey()`; `g_pMission = GetMission()`; register broadcast handlers
  (`App.g_kEventManager.AddBroadcastPythonFuncHandler(eType, g_pMission, NAME)`)
  for ET_INPUT_FIRE_PRIMARY/SECONDARY/TERTIARY, ET_WEAPON_FIRED,
  ET_TORPEDO_ENTERED_SET. Each registration in its own try (log on failure).
  `g_dResults` survives across battles (module global, cleared only on reload).
- `Tick(lShips)`: `if g_dRun == None: return`; else `Step()` in try/except ->
  on error `Abort("error: " + msg)`.
- `WeaponHit`: not defined.
- `Stop()` (battle end, ships being destroyed): NO calls into ships or weapons
  (learned: battle end). `g_dRun = None`; remove the 5 broadcast handlers in
  try; `UnbindKey()`; `g_pMission = None`. The engine stops weapons with the ships.
- Second Quick Battle: `Start` calls `Stop` first -> no double handlers/keys.
- Player ship change mid-test: `Lookup` fails (ID differs from current player
  -> also abort if `GetPlayer().GetObjID() != run ship id`) -> Abort without
  touching the old ship except `Release` guarded by IsDead/IsDying.
- Multiplayer: core does not start modules with EnableInMultiplayer = 0; probe
  adds nothing.
- Another module failing: independent; AutoFire must be off (precondition).

## 5. Mock tests (`Spaceframe/tests/test_stprobe.py`, py3, `mock_app`)

Fakes local to the test file (extend, do not change, mock_app classes):
FakeWeapon (IsFiring, GetTargetID, GetName, StopFiring, SetFiring, Fire,
FireDumb, CanHit, CanHitTarget(t, v) raising TypeError with 1 arg, GetNumReady),
FakeSystem (target list: StartFiring(t=None, v=None) appends if absent,
StopFiring clears, StopFiringAtTarget/RemoveFromTargetList remove,
IsInTargetList, ClearTargetList, SetForceUpdate, GetGroupFireMode,
IsSingleFire, child list), casts `App.Weapon_Cast`, `App.PhaserSystem_Cast`,
`App.Torpedo_Cast`, `App.g_kUtopiaModule.GetGameTime` (settable clock),
`MissionLib.TextBanner` recorder, ET_WEAPON_FIRED / ET_TORPEDO_ENTERED_SET ids.

Expectations:
1. Start twice then Stop: handler add count == remove count for each event; key handler bound once; Stop makes no ship/weapon call (recorder empty after Stop).
2. Keys: `o`/`k` keydown consumed (SetHandled, no CallNextHandler); `K`, `O`, `l`, other keys and keyups passed on; nothing consumed when `Allowed` is 0.
3. `k` cycles 10 tests and wraps; shows stored results of the selected test.
4. `Begin` refuses with banner when AutoFire IsEnabled, when no B, when no system of the kind.
5. MULTI_PHASER: StartFiring called with A then B, SetForceUpdate(1); after the clock passes SampleSeconds, StopFiring called once; banner contains "PASS" when fakes put w0 on A and w1 on B in the same sample, "FAIL" when all on A with an only-B weapon, "INCONCLUSIVE" when all weapons reach both.
6. ORDER: StartFiring order B then A.
7. `Classify` / `Verdict` / `WeaponLine` table tests (pure).
8. A weapon whose GetTargetID raises: run completes, error text in lines, no exception.
9. Ship removed from SHIPS mid-run: Abort banner, no further calls into the ship.
10. TORP_RETARGET: fake torpedo event -> SetTarget(idB) called once; second torpedo ignored (disarmed).
11. MANUAL: press/release events drive snapshots; 20 s timeout finishes with "no press seen".
`python tools/check.py` green (lint15 + all suites).

## 6. Audit points (bc-auditor)

- Python 1.5.2: no nested scopes (handlers by module-string names), no `+=`,
  no `continue` inside try, `has_key`, `apply` for Call, CRLF/ASCII/tabs.
- Every engine call inside try (via `Call`); Tick never raises.
- Stop touches no ship; all 5 broadcast handlers + key handler removed; Start calls Stop first.
- Release only stops systems the probe started, ship re-fetched by ID and live.
- Keys consume only lower-case k/o keydown on allowed ships; L untouched.
- No per-tick work while idle; sampling bounded to the run.
- Banners: max 6 lines per Show, no UI objects kept (TextBanner is fire-and-forget,
  so nothing to free at KillChildren/battle end).
- No edits to Ships.py, core Config.py, AutoFire, StatusHUD, vanilla.

## 7. User test script (coordinator gives to the user)

Quick Battle, player Galaxy-class (phasers + torps), 2 enemies; red alert; Auto
Fire off (L). Target enemy A, turn so A is ahead and B to the side.
`k` until INFO, `o`. Then MULTI_PHASER, MULTI_TORP, ORDER, RELEASE_B, MANUAL,
HOLD_ONE, FIRE_ONE, TORP_RETARGET (each: `k` to select, read hint, `o`, read the
result lines; `k` re-shows the last result). Second battle with a pulse ship
(e.g. Defiant): INFO, MULTI_PULSE, HOLD_ONE. User reports the banner lines
(photo/screenshot is fine) plus what they SAW (beams to two ships at once?
torpedo turning to B?).

## 8. Reading the results (for the SecondaryTarget design)

- inB = 0 after StartFiring(B): list not additive for the player -> only torpedo
  retarget (T10) remains; phasers/pulse need a redesign (NEEDS USER).
- PASS + T5 shows both-reach weapons follow insertion order -> the agreed
  behavior is native: StartFiring(primary) first, secondaries after; exclusion
  "can reach primary" is the engine's own choice. Module = maintain the list.
- PASS but both-reach weapons do not follow order -> need per-weapon hold (T8):
  if StopFiring/SetFiring(0) keeps a weapon off, the module can hold weapons
  that reach A away from B; if the engine refires them, exclusion is not exact
  (NEEDS USER: accept engine choice).
- T7 release shows A0 B0 -> vanilla release wipes secondaries; module must
  re-add them on release (AutoFire already tracks the fire key).

## 9. Open questions (user)

- Probe gating: AnyShip = 1 (no Ships.py edit) vs Ships.py `"STProbe": 1`.
- Removal method after the test (delete folder vs Modules 0).
