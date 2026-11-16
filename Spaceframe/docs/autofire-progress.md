# SDD ledger - plan: Spaceframe Docs\2026-11-11-autofire-plan.md

Pre-flight: shared interfaces checked
- T1 -> T2: IsEnabled / g_dManual / timer ownership: consistent.
- T3 -> T4/T5: Solution.Score / GetProjectileInfo / BestTorpedoScore: consistent.
- T1 -> StatusHUD: GetModule("AutoFire").IsEnabled(): consistent.

Task 1: Ruling: "AUTO FIRE" shown by renaming the player panel title (e.g. "Shields - Auto Fire") instead of a text on the status line - the status line's left side already holds "Armor NN%", so a label there would collide; the title has free room and does not change the panel height - cost if wrong: one more HUD tweak.
Task 1: Ruling: no git in this project; "commit" = install on the PC with mtime guard + cmp, then the user's in-game check, as the plan states.
Task 1: Ruling: execution pauses after each task's install for the user's in-game test, because every task's Step 5 requires it (overrides "continuous execution").
Task 1: Ruling: ToggleKey letter converted to lower-case code by arithmetic (not string.lower) - the game binds lower-case codes (L = 108) - cost if wrong: key bound to wrong code, user reports.
Task 1: Ruling: "AutoFire": Def added to Galaxy, Defiant, Odyssey, Fighter (not Peregrine, carrier-launched AI) - user can edit Ships.py - cost if wrong: one line.
Task 1: installed (AutoFire 0.1, StatusHUD 0.12, core Config, Ships.py), cmp OK, tests 11/11 off-game. Awaiting in-game test.
Task 1: in-game: key L + button OK, no duplicates. Title not shown -> fix: also SetStringW on GetNameParagraph() (title bar paragraph built once). StatusHUD reinstalled, cmp OK.
Task 1: Ruling: AUTO indicator moved from Shields title (title not changeable at runtime) to a green 'AUTO' text in the top right of the weapons panel (GetWeaponsDisplay) - user's choice - cost if wrong: reposition.
Task 1: fix: AUTO tag flicker - GetWeaponsDisplay() returns a new SWIG proxy each call, identity compare rebuilt the text every tick; now created once per battle. test_hud_auto_tag RED->GREEN, 11/11.
Task 1: fix: AUTO tag only appeared after an officer switch - weapons panel Layout() on show/hide only. 11/11.
Task 1: complete (in-game confirmed by user: L, button, AUTO tag stable). Probe console print skipped - API taken from App.pyc method list.
Task 2: Ruling: PhaserBank.CanHit takes a world point (bc_dauntless + ConditionInPhaserFiringArc), not the ship: called with pTarget.GetWorldLocation() - plan said CanHit(pTarget) - cost if wrong: phasers never fire, user reports.
Task 2: Ruling: phaser distance = bank-to-target centre minus target radius (beams hit the hull) - cost if wrong: PhaserRange < 100 slightly generous.
Task 2: Ruling: StartFiring only when the group is not already firing at that target (no restart every cycle); StopFiring only for groups Auto Fire started, on the ship that started them (looked up by ID, not by stored proxy) - avoids fighting manual fire and dangling proxies.
Task 2: tests 15/15 (phasers) + 11/11 (base). Installed AutoFire 0.2.
Task 2: fix: crash when ending Quick Battle with Auto Fire on. Cause: WeaponsDisplay.Create calls KillChildren() on the weapons panel when the player ship changes (battle end), destroying the AUTO text; StatusHUD.Stop then DeleteChild'ed the freed object. Now the text's address (SWIG "this") is taken at creation and looked up among the live panel's children before any use; fallback without "this": player ship ID unchanged. AutoFire.Stop no longer calls StopFiring (ships being destroyed). Tests: base 14/14, phasers 16/16 (mock marks killed texts and records any touch).
Task 2: fix: firing stopped after UI clicks - menu clicks go through the fire input and the game StopFiring on release; now fire-key events clear g_dFiring and FireGroup also restarts when WeaponSystem.IsFiring() is 0. phasers 18/18, base 14/14.
Task 2: complete (in-game confirmed: phasers, manual priority, no crash at QB end, UI clicks).
Task 3: Ruling: tube arc check by angle (>= 90 deg -> 0, otherwise the miss distance grows with the angle) instead of TorpedoTube.IsInArc (signature unconfirmed) - cost if wrong: none, the score already sinks for misaligned tubes.
Task 3: Ruling: tube direction = Weapon.CalculateRoughDirection() (world axes, used by the game's AI dumb-fire); prediction = PhysicsObjectClass.GetPredictedPosition(pos, vel, accel, t) as in AI PredictTargetLocation, iterated twice; subsystem offset rotated by target GetWorldRotation (skipped on error).
Task 3: Ruling: MANEUVER_WEIGHT 0.5 (target assumed to spend half its top accel dodging) - to calibrate in game.
Task 3: Ruling: each group evaluated in its own try (spec 8): error -> that group stops, others continue.
Task 3: tests solution 8/8, torps 6/6, phasers 18/18, base 14/14. Installed AutoFire 0.3 + Solution.py.
Task 3: Ruling: torpedo score too strict in game - evasion term dominates (quadratic in flight time; Bug MaxAccel 3.0, Photon1 speed 100). Now Config TargetEvasion (percent, default 10, was 50 hard-coded). PhaserRange 150 at the user's request.
Task 3: Ruling: all firing-solution variables in Config (TargetEvasion, GuidanceStrength, GuidanceLimit, TargetSize; percent); AutoFire.ApplySolutionConfig sets Solution globals at Start. User's Config edits kept (TargetMode 1, TorpedoMinSolution 50, SpreadMinSolution 75, PulseMinSolution 50).
Task 3: Ruling: toggle key moved from KeyboardBinding+broadcast to a raw ET_KEYBOARD handler on TopWindow (as BridgeUtils.ModalKeyboardHandler) - L was lost while a clicked menu had focus. L/l keydown handled (SetHandled) only on a ship with the tech; other keys CallNextHandler - cost if wrong: L does nothing at all, user reports.
Task 6 (done before 4 and 5, the user tested TargetMode 1): Ruling: mode 1 with no live target selects the nearest live enemy as the player's target (SetTarget by name) so the reticle/HUD follow and it carries on after a kill; mode 2 picks per group (phasers nearest they can hit, torpedoes best solution) without changing the selection; aim offset = player's picked subsystem only for the selected target, else centre (zero TGPoint3). Enemies = mission GetEnemyGroup().GetActiveObjectTupleInSet(ship set), live and not cloaked.
Task 3: TubeMaxAngle (degrees, default 90 = no extra limit) in Config -> Solution.MAX_ANGLE.
Tests: targets 8/8, solution 12/12, torps 7/7, phasers 18/18, base 16/16.
Task 3: complete (in-game OK). Task 6: complete (in-game OK). L key fix OK.
Task 4: Ruling: spread restored on disable and on manual torpedo key, NOT at Stop (battle end destroys ships; touching them crashed before) - plan said restore at Stop - cost if wrong: none, a new battle has a new ship.
Task 4: Ruling: player's spread recorded at Auto Fire's first change (not at enable); if the player picks a spread while Auto Fire is on, that becomes the one to go back to. Spread changed only when torpedoes are about to fire (score >= TorpedoMinSolution): >= SpreadMinSolution -> GetNumFiringChains()-1, else 0.
Task 4: tests spread 9/9; all suites green. Panel "Spread:" text update unverified (spread button is C++, ET_TORP_SPREAD_TOGGLE_CLICKED).
Task 4: Ruling: spread fan/guidance delay is engine behavior (tube SetRight skew vectors in hardpoints; torpedo scripts only give speed 100, guidance 0.1 s, turn 10) - not readable; Config SpreadMinDistance in km as shown in game (UtopiaModule.ConvertKilometersToGameUnits), default 3, to calibrate in game.
Task 3: Ruling: user set TubeMaxAngle 120; the hard 90 deg cut removed - at >= 90 deg the miss is the whole distance (guidance may still bring it round). User's TargetEvasion 0 kept.
Tests: spread 11/11, solution 13/13, all suites green.
Task 4: complete (in-game OK, user calibrated SpreadMinDistance).
Task 5: Ruling: pulse weapons aim themselves inside their arc -> Score with vDirection None (no aim error); arc via PulseWeapon.CanHitTarget(pTarget) (assumed 1 if the call fails: the game only fires weapons that can hit); charge GetChargeLevel >= GetMinFiringCharge; lifetime from the projectile module (GetProperty().GetModuleName()). Plan said IsInArc (signature unconfirmed).
Task 5: tests pulse 6/6, solution 15/15, all suites green.
Task 5 extension (user): TorpedoRule 2 = firing cone like the game AI (CheckGoodShot): ConeAngleFar 15 deg at ConeFarDistance 30 km+, opening to ConeAngleNear 45 deg at ConeNearDistance 5 km-, linear between; in-cone score 1..100 (for SpreadMinSolution), TorpedoMinSolution unused. Ruling: default distances 30/5 km chosen by me (user's SpreadMinDistance is 30) - to calibrate.
Task 5 extension (user): TapFire 1 = torpedo and pulse groups pressed one cycle, released the next while they should fire (quick presses fire faster than holding); phasers always held. Default on.
Tests: solution 21/21, torps 14/14, pulse 7/7, all suites green.
Task 5: complete (in-game OK, user tuned config).
Task 7: README (EN/ES/PT) Auto Fire section + Status HUD AUTO note + Ships.py AutoFire line; header versions Status HUD v0.12, Auto Fire v0.3. Final review: self-review (no subagent dispatched) - no Critical/Important; minor: AutoFire header comment updated.
Task 7: complete. Backup 'Spaceframe v0.4 - 2026-11-12' (folder + zip, 20 files, from installed PC files incl. user configs) cmp OK.
Post-plan (user): PulseRule (1 solution / 2 cone around the weapon's mount direction, shared Cone* settings); Solution.Score takes an optional rule. Ruling: pulse cone reuses the torpedo cone settings - cost if wrong: add PulseCone* settings. Tests pulse 10/10, solution 22/22.
Fix (user): Auto Fire fired at a selected friendly - modes 0/1 used the selection unchecked. Now only ships in the mission's enemy group (IsNameInGroup); mode 1 with a friendly/neutral selected keeps the selection and fires at the nearest enemy; mode 2 enemies only. Ruling: neutrals excluded too. Tests targets 13/13, all suites green.
Post-plan (user): core v0.5 - Ships.py All/Races/Families (Race and SubMenu from the Bedrock plugin; SubMenu N/A = no family); order All < Races < Families < plugin < Ships; 0 = off. Diag shows race/family. Ships.py: All AutoFire Def, Races Federation MVShields Def; per-ship lines kept. Tests core 7/7.
Post-plan (user): separate pulse cone PulseConeAngleFar 45 / Near 90 / FarDistance 30 / NearDistance 5 (Solution.PULSE_CONE_*, Score bPulse). Tests pulse 12/12, solution 23/23.
