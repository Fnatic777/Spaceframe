# Bridge Commander engine & API - what has been verified

Facts measured in game or taken from vanilla scripts. Read the section you need,
not the whole file. Add a line when something new is confirmed in game; mark
guesses as `(unconfirmed)`. Names only are in `App-index.txt` (grep it).

## Finding things
- `App-index.txt` lists `Class.Member` names from App.pyc. Inherited members are
  listed only on the base class: grep `'\.Layout$'`, not `'TGPane\.Layout'`.
- Signatures: grep the game's `.py` files (`D:\GOG Games\Star Trek Bridge Commander\scripts`)
  for real calls. Many vanilla modules are `.pyc` only; Bedrock (`scripts\Custom\Bedrock`)
  and `scripts\py\` have sources. `bc_dauntless` was the reference for shields/phasers.
- Ship names: menu labels are not file names. Grep `scripts\Custom\Bedrock\Ships\*.py`
  for `Label = "..."`; the file name is the key for `Ships.py`
  ("NX Refit BC" = `ENTNXRefit`; "Peregrine FT" menu = `Fighter`, carrier-launched = `Peregrine`).
  Race = `Race`, family = `SubMenu` (`"N/A"` = none) in that plugin.
- Hardpoints (`scripts\ships\Hardpoints`) are `.pyc` only here.
- `.pyc`-only code: `python tools/dis15.py --calls-only <file.pyc|dir>` -> `path:func:line: call`
  (decodes all 2885 game .pyc). 1.5 SET_LINENO = LAST line of a multi-line simple statement;
  many vanilla `.pyc` (Bridge\Characters, Systems\Multi*) are older than the `.py` beside them.

## Lifecycle, events, SWIG proxies
- Scripts load once per game launch: `.py` code changes need a restart.
  `Ships.py` / `Config.py` are re-read at every Quick Battle (`reload`).
- Every call that returns a UI/ship object returns a NEW SWIG proxy: never compare
  proxies by identity, never keep one across timer ticks. Keep IDs/names and look up
  again (ships by ID; UI objects by the SWIG `this` address among the live parent's children).
- `WeaponsDisplay.Create` calls `KillChildren()` on the weapons panel when the player
  ship changes (battle end): child texts you added are freed. Touching them later = CTD.
- At battle end ships are being destroyed: `Stop()` must not call into ships
  (no StopFiring, no spread restore). Only remove own handlers/timers.
- Broadcast handlers: `App.g_kEventManager.AddBroadcastPythonFuncHandler(ET_..., pMission, "Module.Func")`;
  remove the same triple in `Stop()`.
- Raw keys: `ET_KEYBOARD` handler on TopWindow (like `BridgeUtils.ModalKeyboardHandler`);
  `SetHandled()` only for your key, `CallNextHandler` otherwise. KeyboardBinding loses keys
  while a clicked menu has focus. The game binds lower-case codes (`l` = 108).
- Menu clicks pass through the fire input; the game calls StopFiring on release. Cause (confirmed in game): the left mouse button is bound to the primary fire input in the game's controls; unbinding it removes the phaser stutter when clicking UI buttons with Auto Fire on.
- `App.CPyDebug().Print` is a compiled-out no-op in stbc.exe (target is a bare `ret 4` at 0x437350): it prints nowhere (static RE; no output in the user's runs, 2026-11-19). The old Spaceframe Log never produced output.
- Python `open` is blocked by the engine securelevel counter ([0x99ee38] > 0 at runtime): IOError "Securelevel prevents file IO." (confirmed in game, 2026-11-19). The optional `fileio` patch of tools/exe_patch.py (site 0x7551fa, `74 6c` -> `EB 6C`) lifts it for every script; applied by the user, game boots, file logging works (2026-11-19).
- Spaceframe core Log writes `Spaceframe_debug.log` in the game folder when Debug = 1 (needs the fileio patch; without it one banner "Spaceframe log file unavailable" shows); cap 5000 lines per session, each line stamped with game time (confirmed in game, 2026-11-19). Read it with Read/Grep. `tools/dbwin_capture.py` (OutputDebugString) does NOT see Python logs, only the engine's own TGTrace output.
- Without the fileio patch, show results on screen (MissionLib.TextBanner). Crash dumps: `stbc.RPT` in the game root (address only).

## UI
- Panels redraw only when their own content changes: call `pDisplay.Layout()` after a
  structural change (ship changed, lines shown/hidden), never every tick (flicker).
- `ShipDisplay.GetShipID()` lags until the UI redraws: use
  `App.ShipClass_Cast(pPlayer.GetTarget())`.
- Panel title paragraph is built once; it cannot be changed at runtime.

## Combat
- Shields (bc_dauntless): facing >= 60% absorbs, only excess passes; 10%..60% leaks
  `0.6 * (1 - 2 * (f - 0.1))`; <= 10% everything passes, facing not drained.
- `PhaserBank.CanHit(point)` takes a world point (`pTarget.GetWorldLocation()`), not a ship.
- `PulseWeapon.CanHitTarget(point, vector)`: (loc, vZero) accepted in game (returned 0 for a target the weapons were firing at - meaning of the 2nd arg unclear); `(ship)` and `(ship, vZero)` raise TypeError. CanHitTarget is not an arc query (exe: it uses the weapon's own target ID, its 2nd arg is an OUT param). Arc test: `PulseWeapon.IsInArc(pTarget.GetWorldLocation())` (one world point, 1/0); AutoFire.PulseReady uses it and Auto Fire pulse fire looked right in game (2026-11-19, tested without Debug). Charge `GetChargeLevel() >= GetMinFiringCharge()`.
- Tube direction: `Weapon.CalculateRoughDirection()` (world axes).
  Prediction: `PhysicsObjectClass.GetPredictedPosition(pos, vel, accel, t)` (as AI PredictTargetLocation).
- `TorpedoTube.IsInArc(worldPoint)` (one TGPoint3, e.g. `pTarget.GetWorldLocation()`) is the pure arc test of a torpedo tube: a FIXED +-30 deg cone on both axes, no property getter (STProbe TORPARC on a Galaxy DN, 2026-11-19: the model dot(D,Fwd) > 0 and |atan2(D.Right,D.Fwd)|, |atan2(D.Up,D.Fwd)| <= 30 deg matched on 12/12 points for every tube checked, with either tube position candidate). `TorpedoTube.GetDirection()/GetRight()` are LOCAL property vectors (not plain TGPoint3: use GetX/GetY/GetZ).
- Torpedo system target list works like the phaser one (STProbe MULTI_TORP, Galaxy DN, 7 forward + 7 aft tubes, single fire 0): with A (ahead) and B (behind) in the list and fire held, the forward tubes launched at A first and the aft tubes at B after them (the engine launches one torpedo per 0.5 s per system, round-robin: the main target's tubes starve the others until their torpedoes are gone); no ET_CANT_FIRE.
- Manual torpedo fire (fire key held, Galaxy DN, confirmed in game 2026-11-19, SecondaryTarget log): the engine only keeps the torpedo group firing in short windows (one launch per window, ~0.63 s apart) and the group stops after the forward tubes run empty although the key is held. Re-arming while held (`StartFiring(main, offset)` + `SetForceUpdate(1)` + secondaries) makes the tubes that reach the main target find no torpedo ready and a free tube reaching a secondary launch: 7 forward tubes at the main target, then all 7 aft tubes at the secondary. Guards used: 20 re-arms / 20 s per press, same main target, cleared on every release path, stale 25 s.
- AutoFire taps weapon groups via StartFiring/StopFiring (no fire key events) and decides by the cone/solution on the MAIN target: it fires whole torpedo volleys at it and SecondaryTarget sees the torpedo group firing only for fractions of a second, so no secondary torpedo launches happen under AutoFire (log of a 3-enemy fight, 2026-11-19: phasers spread over 3 targets, torpedoes only at the main target of the moment). Not implemented (future work).
- Torpedo spread fan / guidance delay are engine-side (hardpoint skew vectors).
- Single-fire phaser systems (hardpoint SetSingleFire(1)): with 2 targets in the system list only one is fired at (onA:1 onB:1 simul:0 on the probe). `pSystem.GetProperty().SetSingleFire(0)` at runtime lifts it: both targets fire at once (onA:2 onB:6, confirmed in game, STProbe SINGLEFIRE); the system's IsSingleFire follows the property; restoring SetSingleFire(1) works. SetGroupFireMode(1 or 2) did NOT lift it. The property is NOT shared between ships of the same class (confirmed in game, STProbe SHARED: player's lifted 1 -> 0, another ENTYorktown stayed 1); still restore it on the live ship.
- Torpedo retarget after launch (confirmed in game, STProbe TORP_RETARGET): on ET_TORPEDO_ENTERED_SET, `pT = App.Torpedo_Cast(pEvent.GetDestination())`; `pT.SetTarget(idB)` + `pT.SetTargetOffset(vZero)` makes a torpedo launched at A fly to B; `GetParentID() == ship id` identifies our torpedoes.
- Manual fire release (confirmed in game, STProbe MANUAL): the game's key release calls StopFiring() and empties the system's whole target list; pressing keeps extra targets already in the list; `StartFiring(B)` alone re-adds. Target-list order (probe ORDER, 3 samples incl. ORDER_PROP0 with single-fire lifted, confirmed in game): weapons that reach several listed targets fire at the first listed; weapons that reach only one fire at that one, all at the same time.
- `Weapon.SetFiring(0)` on a phaser bank that is firing leaves its beam frozen in space as a static line at the ships' positions (confirmed in game, SecondaryTarget PhaserPerTarget with several targets; gone with the feature off). Cause (read from the exe, docs/api/exe-weapons.md): SetFiring only writes the firing flag; only StopFiring ends a beam (and only when the flag is 1). Do not use SetFiring(0) on a firing bank. StopFiring does not hold a bank either: the engine retries a stopped bank every ~0.33 s (confirmed in game as flicker).
- Km to game units: `UtopiaModule.ConvertKilometersToGameUnits`.
- Enemy check: mission's enemy group `IsNameInGroup(name)`.
- Hull repair complexity usually 1.0 (Constitution 3.0; NX, Fighter 2.0); some ships
  have two repair subsystems.

## Spaceframe lifecycle (confirmed in game, Spaceframe 0.6 / AutoFire 0.4)
- A module that fails or is disabled still needs its `Stop()` (handlers, buttons, texts): the core now calls `Stop()` on every loaded module, disabled ones included.
- Subsystems added by a module (e.g. "Ablative Armor") stay on the ship: look for an existing one by `GetName()` among the ship's subsystems before creating another, and do not call `RepairSubsystem.AddSubsystem` a second time for it (a second registration is unconfirmed: avoided). Ship leaving and re-entering the set with the armor reused: played without problems, not tested on its own (unconfirmed).
- Config read once at `Start` into module globals (AutoFire) works: `Start` already reloads Config, so edits apply from the next battle.
- Game interpreter is Python 1.5.2: `dict.keys()` is a list (safe to `del` while looping); the py3 mocks must wrap it in `list(...)` (done in `tests/mock_app.py` `load_module`).

## Engine patch: one bank per target (confirmed in game 2026-11-19, stbc.exe build SHA-256 2d2ead67...8bc4)
- The engine has no per-target single fire: `SingleFire` is read in 4 places (WeaponSystem Update 0x58489a, UpdateWeapons 0x584b4e and 0x5849e8, force-fire 0x584700), all "one bank only". `SetSingleFire(0)` from Python removes all of them.
- Hook at 0x584f24 inside TryFire (0x584e40) with a 70-byte cave at 0x8879f2: a bank skips a candidate target when another bank of the same system is already firing (+0x88 == 1) at it (+0x8c). With single fire lifted this gave one bank per target, no flicker and no burst. Apply/revert with `python tools/exe_patch.py apply|revert` (hash-checked, backup `stbc.exe.orig-<sha8>`). The rule is engine-wide: it also applies to AI and enemy ships.
- The patch applies to PHASER systems only (confirmed in game 2026-11-19): the first cave version hit every WeaponSystem and made a Defiant's 4 pulse cannons fire one at a time. Cave v2 asks the system `IsA(0x801f)` (PhaserSystem type id, same test as `PhaserSystem_Cast`); pulse (0x8020) and torpedo (0x8021) systems keep the original behavior.
- Pulse arc formula confirmed in game (STProbe ARCFORMULA, NX Cruiser, 2026-11-19): with the weapon position `pWeapon.GetWorldLocation()` (candidate A) the box test (dot(D,Fwd) > 0, width/height angles from atan2 against `GetArcWidthAngleMin/Max` and `GetArcHeightAngleMin/Max`, radians, limits may be asymmetric: W[-15,15] H[-20,10] deg) matched `PulseWeapon.IsInArc(point)` on 12/12 probe points for every pulse weapon; the alternative position (ship + R*GetPosition) matched 0/12 (errors). Used by AutoFire PulseRule 3 (`Solution.ArcDepth`).
- `TorpedoTube.CanHit(world point)` works in game (returns 1/0 per tube, e.g. one tube reaches A and the other does not); `CanHit(ship)` raises TypeError. `PulseWeapon.CanHitTarget(point, vector)` returned 0 for all six pulse weapons of an NX Cruiser (not usable as an arc test; use IsInArc).
- NX Cruiser (stock hardpoints): phaser group n=6 single fire 0, torpedo group n=2 single fire 1, pulse group n=6 single fire 1.
- Torpedo secondaries under Auto Fire confirmed in game 2026-11-20 (Galaxy DN, 7 fwd + 7 aft tubes): a tapped torpedo group started with the target list [main, secondary] fires the forward tubes at main, and once they are empty a list holding ONLY the secondary (main left out) fires the aft tubes at it, about every 0.5 s with no forward launch; the full 14-tube volley takes ~8 s. The list must be rebuilt (StartFiring head, StartFiring each secondary, then SetForceUpdate) on every press.
- Arc-percent rule confirmed in game 2026-11-20 (AutoFire PulseRule 3 / TorpedoRule 3, user tests with logs): (a) torpedoes: a tube fires at a secondary only when the point is inside the allowed percent of its fixed cone; in manual fire SecondaryTarget skipped a secondary at the edge (ARC-SKIP torpedo <id>) and re-armed once it entered the allowed percent (Galaxy DN: aft tubes 1-7 launched at the secondary one every ~0.6 s). (b) pulse: a group started with a target list that does NOT contain the main target fires only the weapons that reach a listed target (Scimitar Delta, Emperor: forward/aft/port/starboard/dorsal/vent cannons fired at different secondaries while the forward ones kept the main target).
- Phaser secondaries under Auto Fire confirmed in game 2026-11-20 (Defiant with its single dorsal phaser; ENTNX): when no bank reaches the main target, StartFiring at a secondary the bank reaches makes it fire (`PhaserBank.CanHit(world point)`), and the group goes back to the main target once a bank reaches it. A phaser group started this way is restarted every Auto Fire cycle while the bank has no charge (PhaserMinCharge 0): about 4.7 starts per shot in the log. UNCONFIRMED: whether StopFiring then StartFiring on a head change cuts a beam that is already out.
- `App.HullClass_Create(property)` raises `TypeError - HullClass_Create requires exactly 0 arguments; 1 given` in this build (seen in game 2026-11-20 on Fighter, Defiant and SovereignR): the Ablative Armor subsystem mode is never available and the module runs in internal mode.
