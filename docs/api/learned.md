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
- `App.CPyDebug().Print` (Test Mode console) is the only log; writing files from
  game scripts does not work (confirmed in game: open() raises IOError "Securelevel prevents file IO"). Show results on screen (MissionLib.TextBanner). Crash dumps: `stbc.RPT` in the game root (address only).

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
- `TorpedoTube.IsInArc` signature (unconfirmed) - avoided.
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
