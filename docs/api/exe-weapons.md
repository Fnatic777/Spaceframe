# stbc.exe - weapon firing internals (static analysis)

Source: `stbc.exe` (BC Remastered, image base 0x400000), read with `python tools/exe_probe.py`.
Tags: READ FROM CODE = seen in the disassembly; INFERRED = deduced, not yet seen in game.
Field offsets are on the C++ object (`this`). Addresses are function starts.

## Object layout (READ FROM CODE)
Weapon (base of PhaserBank, PulseWeapon, ...):
- `+0x88` byte  firing flag. `Weapon.SetFiring(i)` = plain store (wrapper 0x60fbc0), `IsFiring` reads it.
- `+0x8c` int   target object ID (`GetTargetID`); `+0x90..+0x98` target offset (x,y,z).
- `+0x9c` float retry timer (see TryFire). `+0x48` float slow-update accumulator (0.33 s).
- EnergyWeapon `+0xa0` float charge (`Get/SetChargeLevel` = plain load/store).
- PhaserBank `+0xf4` beam state (0 none, 1/2/3 active), `+0xf8` beam effect object, `+0xfc` hit target.
- EnergyWeaponProperty `+0x74` MinFiringCharge (`Get/SetMinFiringCharge`).
WeaponSystem: `+0x1c` weapon count, `+0xa8` IsTryingToFire, `+0xa9` IsFiring, `+0xab` CanFire,
`+0xac` ForceUpdate, `+0xb0` GroupFireMode, `+0xb4` index of last weapon fired, `+0xb8/+0xbc`
firing chain / current chain group, `+0xc0` target count, `+0xc4` target list.

## Vtable slots (READ FROM CODE)
Weapon: #30 StopFiring, #31 Fire(float dt, int), #32 FireDumb, #33 CanFire, #34 CalculateRoughDirection.
PhaserBank vtable 0x893194: StopFiring 0x571200, Fire 0x570fe0, CanFire 0x571e60.
WeaponSystem vtable 0x8938c4, PhaserSystem 0x893240: #25 Update(dt) 0x5847d0 (shared),
#34 StartFiring-impl, #35 StartFiring, #36 StopFiring (WS 0x584560, Phaser 0x573f30 = MP notify + WS),
#37 SetGroupFireMode 0x573ce0 (plain store to +0xb0).

## Q1 - what stops/freezes a beam
- PhaserBank::StopFiring 0x571200 (READ FROM CODE): only if `+0x88 == 1`: clear flag, detach the beam
  by state (`+0xf4` 1 -> 0x4e7540, 2/3 -> 0x4e7a80), `+0xf4 = 0`, stop sounds, post
  ET_PHASER_STOPPED_FIRING (and ET_PHASER_STOPPED_HITTING if `+0xfc`). Always ends in Weapon base
  0x5833f0: target ID `+0x8c = 0`. If the flag is already 0 it does NOTHING to the beam.
- Beam geometry is refreshed only inside Fire -> 0x571f40 (start path when `+0x88 == 0`: sounds,
  ET_PHASER_STARTED_FIRING, ET_WEAPON_FIRED; then 0x572440 + beam 0x4e78b0 update every call).
- Frozen beam cause (READ FROM CODE): `SetFiring(0)` clears `+0x88` but leaves the beam attached
  (`+0xf4 != 0`). Next ticks TryFire skips the bank (not firing, retry timer < 0.33), so the beam is
  never updated (static line); any later StopFiring sees flag 0 and skips the teardown.
- `StopFiring(); SetFiring(0)` (HoldMode 1) = identical to StopFiring alone (flag already 0). INFERRED.

## Q2 - how the system assigns banks and refires
- WeaponSystem::Update 0x5847d0 (READ FROM CODE): system off/disabled -> system StopFiring. If
  IsTryingToFire: `chosen = UpdateWeapons(dt)` 0x584930. Else stops every bank with flag 1.
  Then per bank: if IsSingleFire and bank != chosen -> bank.StopFiring() EVERY tick.
- UpdateWeapons 0x584930: banks of the current firing-chain group (group 0 = all), round-robin
  from `+0xb4`+1 (single fire: from `+0xb4`, break after the first bank that fires). Calls
  SetGroupFireMode(current group) every tick -> a Python SetGroupFireMode is overwritten.
  GroupFireMode = firing-chain group filter (0 = none), not a per-target mode. (READ FROM CODE)
- TryFire(bank, dt) 0x584e40 (READ FROM CODE):
  - timer `+0x9c` += dt (ForceUpdate: = 0.33). If bank NOT firing and timer < 0.33 -> skip.
    Firing banks reset the timer to 0 every tick. => a stopped bank retries 0.33 s after StopFiring
    (the observed ~0.25 s). Retry cadence constant 0.33 at 0x893830.
  - if !CanFire -> StopFiring, skip.
  - Fire(dt,1) on its CURRENT target `+0x8c` (sticky). Only if that fails: `+0x8c = 0`, walk the
    system target list from the head, set target (0x584f70, not exported), Fire; first success wins.
  => "fires at the first listed target it reaches" holds only for banks without a valid target;
     a firing bank keeps its target while it can hit it.
- PhaserBank::Fire 0x570fe0: !CanFire, no target object, or target not hittable -> StopFiring (clean).
- Python `Weapon.Fire(dt,i)` = the same virtual; after StopFiring the target ID is 0, so it fails. INFERRED.
- StopFiringAtTarget 0x5845a0: StopFiring on banks whose `+0x8c` == target, remove target from list,
  clear IsTryingToFire if the list is empty. System StopFiring 0x584560: TryingToFire=0, clear list,
  StopFiring every bank.

## Q3 - per-bank hold / target from Python
- No per-bank target setter, no hold/standby flag is exported (Weapon_*, EnergyWeapon_*, PhaserBank_*,
  WeaponSystem_* wrappers all listed; the target setter 0x584f70 has one caller, TryFire). READ FROM CODE.
- PhaserBank::CanFire 0x571e60 (READ FROM CODE): false if ship check 0x5ac450 is true; if firing:
  false when charge <= 0; if NOT firing: false when MinFiringCharge (property +0x74) > charge;
  false when condition is at/below the disabled threshold.
- => Clean hold candidate (INFERRED, needs game test): `bank.StopFiring()` (clean teardown) then
  raise the bank's `GetProperty().SetMinFiringCharge()` above its max charge. Every 0.33 s TryFire
  sees CanFire false and only clears the target ID; the bank keeps recharging. Release = restore the
  original MinFiringCharge (optionally `WeaponSystem.SetForceUpdate(1)` to retry at once).
  Unknown: whether the bank property object is shared between ships of the same class
  (WeaponSystemProperty is not, see learned.md). The only other reader of
  EnergyWeapon::GetMinFiringCharge 0x56f910 is 0x5b6560, a serializer writing all weapon stats in a
  row (save/multiplayer stream, INFERRED) - not AI targeting.

## Per-bank TurnOff as a hold (checked 2026-11-19, bc-scout)
- PoweredSubsystem TurnOn/TurnOff wrappers 0x60e9d0/0x60ea40 vcall +0x7c/+0x80; PhaserBank slots resolve to Fire/stub (UNSURE). CanFire 0x571e60 / TryFire 0x584e40 ignore power flags; only WeaponSystem::Update 0x5847d0 gates on byte +0x9c (system-wide, off -> StopFiring of the whole list). Verdict: per-bank TurnOff is NOT usable as a hold (INFERRED).

## Patch: one bank per target (applied 2026-11-19, confirmed in game)
- Site: VA 0x584f24 (file offset 0x184f24), 6 bytes `85c074308b16` -> `jmp 0x8879f2; nop`. Cave: VA 0x8879f2 (offset 0x4879f2), 70 bytes in the zeroed slack at the end of .text (executable, last mapped page). Cave asm and bytes live in `tools/exe_patch.py` (keystone asserts them on every run).
- Logic: on entry `eax` = validated candidate; if non-zero, loop banks of the system ([sys+0x1c] count, 0x56c570 getter, thiscall ecx=sys): if another bank has +0x88 == 1 and +0x8c == target ID, reject the candidate (jmp 0x584f58); else continue at 0x584f2a. The system pointer is read from [esp+8] (saved caller esi; TryFire has one caller, 0x584b19).
- Not covered: the sticky path (0x584ee2): a bank that still holds its previous target keeps it even if another bank fires there. Not seen in game yet; second hook near 0x584eed if it shows.
- Cave v2 (88 bytes, VA 0x8879f2..0x887a4a, confirmed in game): starts with `mov ecx,[esp+4]; mov edx,[ecx]; push 0x801f; call [edx+8]` (virtual IsA, thiscall, ret 4); a system that is not a PhaserSystem takes the original path (`mov edx,[esi]; jmp 0x584f2a`). Type ids: PhaserSystem 0x801f, PulseWeaponSystem 0x8020, TorpedoSystem 0x8021, WeaponSystem 0x801d. `tools/exe_patch.py` keeps cave v1 as legacy (`status` shows patched-v1, `upgrade` moves to v2).

## PulseWeapon CanHitTarget vs IsInArc (static, not confirmed in game)

- `CanHitTarget`: wrapper 0x6192b0 -> C++ 0x575610. Args: P (world point) and an OUT param written on success. The target is NOT an argument: it is taken from the weapon's own target ID at +0x8c. It checks closing speed and time (time vs the property default 8.0), and its final gate is IsInArc (0x575a60). So it is not an arc query.
- `IsInArc`: wrapper 0x6199b0 -> C++ 0x575a60. One arg, a world point (e.g. `pTarget.GetWorldLocation()`). Dot with forward > 0, then the width/height angle test. Ignores charge, range and target ID. Returns 1 inside the arc, 0 outside.
- `PulseWeapon::Fire` (slot #128, 0x5752a0) gates on CanHitTarget at 0x575373.
- AutoFire `PulseReady` uses `IsInArc(pTarget.GetWorldLocation())` (falls back to ready if the call raises).
