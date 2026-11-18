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
  game scripts does not work. Crash dumps: `stbc.RPT` in the game root (address only).

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
- `PulseWeapon.CanHitTarget(pTarget)`; charge `GetChargeLevel() >= GetMinFiringCharge()`.
- Tube direction: `Weapon.CalculateRoughDirection()` (world axes).
  Prediction: `PhysicsObjectClass.GetPredictedPosition(pos, vel, accel, t)` (as AI PredictTargetLocation).
- `TorpedoTube.IsInArc` signature (unconfirmed) - avoided.
- Torpedo spread fan / guidance delay are engine-side (hardpoint skew vectors).
- Km to game units: `UtopiaModule.ConvertKilometersToGameUnits`.
- Enemy check: mission's enemy group `IsNameInGroup(name)`.
- Hull repair complexity usually 1.0 (Constitution 3.0; NX, Fighter 2.0); some ships
  have two repair subsystems.

## Spaceframe lifecycle (confirmed in game, Spaceframe 0.6 / AutoFire 0.4)
- A module that fails or is disabled still needs its `Stop()` (handlers, buttons, texts): the core now calls `Stop()` on every loaded module, disabled ones included.
- Subsystems added by a module (e.g. "Ablative Armor") stay on the ship: look for an existing one by `GetName()` among the ship's subsystems before creating another, and do not call `RepairSubsystem.AddSubsystem` a second time for it (a second registration is unconfirmed: avoided). Ship leaving and re-entering the set with the armor reused: played without problems, not tested on its own (unconfirmed).
- Config read once at `Start` into module globals (AutoFire) works: `Start` already reloads Config, so edits apply from the next battle.
- Game interpreter is Python 1.5.2: `dict.keys()` is a list (safe to `del` while looping); the py3 mocks must wrap it in `list(...)` (done in `tests/mock_app.py` `load_module`).
