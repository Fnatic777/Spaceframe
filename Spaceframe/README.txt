Spaceframe v0.6 - lightweight module framework for Bridge Commander
====================================================================
Included modules: MV Shields (Multivectral Shields) v0.7, Ablative Armor v1.6,
Status HUD v0.12, Auto Fire v0.5, Secondary Target v0.3

  [EN] English ........ section 1
  [ES] Espanol ........ seccion 2
  [PT] Portugues ...... secao 3


===============================================================================
1. [EN] ENGLISH
===============================================================================

What it is
----------
Spaceframe is a small core that loads gameplay modules and gives them shared
services: one timer, one weapon hit handler, ship identification, logging and
error isolation. Modules do not touch the game files, and a module that fails
is disabled alone while the others keep running. A module that fails on one
ship does not stop the others, and it is only disabled after 50 failing
cycles in a row. Built for BC Remastered and
Orion Delta, in plain Python 1.5.2, with no Foundation, QBautostart or
Kobayashi Maru.

Files
-----
scripts\Custom\Spaceframe\Spaceframe.py   - the core
scripts\Custom\Spaceframe\Config.py       - core settings
scripts\Custom\Spaceframe\Ships.py        - which ships use which technology
scripts\Custom\Spaceframe\Modules\        - one folder per module
scripts\QuickBattle\QuickBattle.py        - got 2 small blocks (marked "Spaceframe")
scripts\QuickBattle\QuickBattle.py.mvbak  - backup of the original

Core settings (scripts\Custom\Spaceframe\Config.py)
---------------------------------------------------
Modules             - modules are enabled automatically; set one to 0 to
                      disable it, e.g. "MVShields": 0
Interval            - time between timer cycles (default 0.25 s)
EnableInMultiplayer - 1 = also run in multiplayer (may desync)
Debug               - 2 = the log (as 1) plus short banners on screen (plans, errors).
                      1 = write Spaceframe_debug.log in the game folder (needs the
                      optional "fileio" engine patch, see "Engine patches"; without
                      it one banner says the log is unavailable). Max 20000 lines
                      per session, each stamped with the game time. Leave it 0
                      for normal play.
In every Config.py, percentages are written from 0 to 100 (50 = 50%), and
on/off settings as 1 or 0.

Ship list (scripts\Custom\Spaceframe\Ships.py)
-------------------------------------------------
Which technologies (module names) each ship uses, for every ship, by race,
by family and ship by ship:
      All      = {"AutoFire": Def}
      Races    = {"Federation": {"MVShields": Def}}
      Families = {"Galaxy": {"AblativeArmor": 80}}
      Ships    = {"Defiant": {"AblativeArmor": 100},
                  "Excelsior": {"MVShields": 0}}
Each level overrides the one before (All < Races < Families < the ship's
Bedrock plugin < Ships); 0 switches a technology off for that ship. Race and
family come from the ship's Orion Delta plugin: Race ("Federation",
"Romulan"...) and SubMenu (the family, e.g. "Galaxy" for all its variants).
Ships without a plugin, or with SubMenu "N/A", have no race or family. The
diagnostics command shows each ship's race and family.
An explicit 0 (ship, race or family) switches the technology off for real: an
old "Ships" list in a module's Config.py no longer turns it back on.
Def = the default value set in the module's Config.py; or a number:
- "MVShields": efficiency, 1 to 100 (default: DefaultEfficiency, 100). It is
  the share of the difference between the facings corrected each time; lower
  values leave the hit facing weak for longer.
- "AblativeArmor": capacity as a percentage of the hull (default:
  DefaultArmor, 50).
- "AutoFire": Def (the ship can use Auto Fire).
- "SecondaryTarget": Def, or a number that adds the weapon types: 1 phasers,
  2 torpedoes, 4 pulse weapons (e.g. 5 = phasers and pulse). Def = the
  Weapons setting of the module.
On Orion Delta a ship can also get a technology from its own Bedrock plugin
(scripts\Custom\Bedrock\Ships\<Ship>.py, above "###Do Not Change Below###"),
e.g. "MVShields = 80" (-1 there = default value); Ships wins over it.

MV Shields module
-----------------
The 6 shield facings of a ship work as a single shield. The total charge is
redistributed among the facings on every timer cycle and also immediately on
every weapon hit, in proportion to each facing's maximum capacity. The total
charge never changes, it only moves between facings. It works together with
Orion's Shield Transfer and Power Macros.

Settings: scripts\Custom\Spaceframe\Modules\MVShields\Config.py
- Mode: when the shields are redistributed: 0 = off, 1 = on hit only,
  2 = cycle only, 3 = both (default).
- DefaultEfficiency: efficiency of ships set to Def (100).

Ablative Armor module
---------------------
Once damage gets past the shields, the armor absorbs it before it reaches the
hull or any subsystem. When the armor runs out, damage passes normally.
- Capacity: a percentage of the ship's hull (default 50%).
- The armor is a real "Ablative Armor" subsystem of the ship. It is
  repaired with the ship's repair rate, as a subsystem harder to repair than
  the ship's own hull (ArmorComplexity, default 200%: twice as hard, so half
  the hull's speed), slower when the repair system is damaged. It waits
  while the hull is damaged: the hull is repaired first, then the armor.
  (It does not show in the repair list yet.)
- Bleed-through, like the game's shields: with the armor at 50% or more it
  stops everything; below that, part of each hit goes through to the hull
  and subsystems, growing in a straight line up to 50% with the armor
  empty (BleedStart, BleedMax).
- HUD: drawn by the Status HUD module (below).
- If the game refuses the subsystem, the module uses internal armor with its
  own regeneration instead (with Debug = 1, a message shows which mode is on).
- A ship that leaves and comes back keeps its single Ablative Armor
  subsystem (no duplicate, its condition is kept).

Settings: scripts\Custom\Spaceframe\Modules\AblativeArmor\Config.py
- DefaultArmor (50), ArmorComplexity (200), BleedStart (50), BleedMax (50),
  SubsystemDamageCost (100), CreateSubsystem (1), Targetable (1).
- If the game crashes when an armored ship enters the battle, set
  CreateSubsystem = 0.

Status HUD module
-----------------
Adds a status line to the ship panels of the tactical HUD, right above the
hull bar:
- "Hull NN%" on the right, for every ship.
- For ships with ablative armor: "Armor NN%" on the left, and a white bar
  over the hull bar showing the armor level live.
- On the player's panel ("Shields") and on the target's panel ("Target
  Shields"). The player's panel grows upwards and the other panels of its
  row grow with it; the target's panel grows downwards and pushes the
  "Targets" list down if needed. Each panel grows by a fixed amount for the
  whole battle (with or without armor, with or without a target), and goes
  back to normal at the end of the battle.
Settings: scripts\Custom\Spaceframe\Modules\StatusHUD\Config.py
- ShowHull (1), ShowArmor (1), ShowTarget (1), ExpandDisplay (1),
  ExpandRow (1), PlayerLineSpace (130), TargetLineSpace (150),
  HudBarHeight (100).
- While the Auto Fire module is on: "AUTO" in the top right corner of the
  weapons panel.

Auto Fire module
----------------
Fires the weapons of the ship you control by arc and flight-time rules, so you
can concentrate on manoeuvring. Only for the player's ship, and only if it
has "AutoFire" in Ships.py.
- On and off: the L key (ToggleKey) or the "Auto Fire" button in the
  tactical officer's menu. While on, "AUTO" shows in green in the top right
  corner of the weapons panel (the one titled with the speed).
- It fires only at the mission's enemies (never at friendly or neutral
  ships, even when selected), only at red alert and never while cloaked;
  it does not change the alert level. Holding a fire key yourself takes that weapon group over
  until you let go.
- Phasers: fire while the target is within PhaserRange percent of their
  full-damage range, in arc, and charged to at least PhaserMinCharge
  (0 = off for either check).
- Torpedoes: the target is predicted where it will be when the torpedo
  arrives (the same prediction the game's AI uses). A tube fires only when
  that point is inside a share of its fixed 30 degree cone (0 = centre,
  100 = edge) that depends on the estimated flight time (distance / torpedo
  speed): TorpedoArcPercentNear % (90) at ArcFlightTimeNear seconds (0.5) and
  less, narrowing to TorpedoArcPercentFar % (70) at ArcFlightTimeFar seconds
  (1.5) and more, in proportion in between. Once firing it keeps firing until
  the point is TorpedoArcHysteresis points past that (0 = off).
  TorpedoReserve torpedoes are kept back.
- TorpedoRule 1 = the arc percent only. TorpedoRule 2 (default; any other
  value counts as 2) adds a flight-time limit: a tube is held while the
  flight time is over TorpedoFlightTimeLimit seconds (1.5) plus the torpedo's
  own guidance time, never more than its lifetime. 0 = no limit; an unknown
  speed never blocks.
- Large or slow targets (rule 2): a shot over the limit still fires when the
  target cannot get out of the way in time. It gets
  square root of (2 x TargetSizeAllowance% x target radius / its current
  acceleration), in game units, plus the guidance time, up to
  TargetSizeFlightTimeMax seconds (5.0). A target with no impulse engines or
  no acceleration gets that maximum; damaged engines raise the time. It never
  makes a limit shorter, so small agile ships keep the limits above.
  TargetSizeAllowance 100 = the target's own radius, higher = more
  permissive; 0 in either setting = off.
- Spread: Auto Fire uses the ship's largest spread when the flight time is
  between SpreadFlightTimeMin (2.0) and SpreadFlightTimeMax (5.0; 0 = no
  upper bound) and the predicted point is within SpreadArcPercent (10) of the
  cone; Single otherwise. This only chooses HOW to fire: the flight-time
  limit still applies, so a target limited below SpreadFlightTimeMin never
  gets spread. The spread mode belongs to the torpedo system: secondaries
  fired in the same press as a spread shot at the main target leave in spread
  too. Your own spread comes back when Auto Fire is switched off or when you
  fire torpedoes by hand.
- Pulse weapons (disruptors, pulse cannons), when charged: the same arc and
  flight-time rules on the weapon's own firing arc, with PulseRule,
  PulseArcPercentNear / PulseArcPercentFar, PulseArcHysteresis and
  PulseFlightTimeLimit; large or slow targets get the longer limit too.
  Spread does not apply. With Secondary Target ON it also picks the secondary
  targets of the free weapons, and fires at a secondary alone when no weapon
  has a shot at the main target.
- Secondary targets have their own values: TorpedoArcPercentNearSecondary /
  TorpedoArcPercentFarSecondary and TorpedoFlightTimeLimitSecondary (1.0),
  and the same Pulse... settings. A setting left out falls back to the main
  one; the flight times of the arc percent and the hysteresis are shared.
- Arc shape (TorpedoArcShape / PulseArcShape, 1 = default): the percent is
  measured as ONE angle from the arc centre (the cone for torpedoes; an
  ellipse inscribed in the weapon's own, possibly asymmetric, limits for
  pulse weapons). In the corners of the arc it is stricter than on the axes.
  0 = the old box depth (each axis apart).
- HoldOnWarp = 1: torpedoes and pulse weapons are held while the target does
  an in-system warp and for WarpHoldGrace seconds (1.0) after it; manual fire
  is never held. 0 = off.
- TapFire = 1: torpedoes and pulse weapons are fired with quick presses
  (faster than holding the key); phasers are always held.
- SecondaryTorpedoes = 1: with Secondary Target switched ON for the ship
  (torpedoes allowed), torpedo tubes that cannot reach the target fire at
  other enemies they can reach, by themselves, with the same rule as the
  main target (TorpedoRule) and TorpedoReserve. Tubes that reach the main
  target keep their
  torpedoes for it. If no tube reaches the main target, the free tubes fire
  at the best secondary, with the same spread rule. 0 = off.
- SecondaryPhasers = 1: with Secondary Target switched ON for the ship
  (phasers allowed), a phaser group whose banks cannot reach the main target
  fires at a secondary target a ready bank reaches (nearest first), and goes
  back to the main target as soon as a bank reaches it. When a bank reaches
  the main target nothing changes. 0 = off.
- TargetMode: 0 = your selected target only; 1 = your target, and with none
  (or after a kill) the nearest enemy becomes your target; 2 = each weapon
  group picks its own enemy (phasers the nearest they can hit, torpedoes
  and pulse weapons the best arc score).
Settings: scripts\Custom\Spaceframe\Modules\AutoFire\Config.py (each setting
is described there). They are read once
when a battle starts: edits apply from the next battle (Quick Battle), not
mid-battle.

Secondary Target module
-----------------------
With several enemies, many weapons sit idle because they cannot reach the
target you selected. This module makes those weapons shoot at other enemies
they can reach, while your main target keeps every weapon that reaches it.
Only for the player's ship, and only if it has "SecondaryTarget" in Ships.py.
- It works while a weapon group is firing at your main target, whether you
  hold the fire key yourself or Auto Fire is on. Release the key and it
  stops with it: it never fires on its own and fires only at the mission's
  enemies (never at friendly or neutral ships).
- Each cycle it looks at the nearest enemies (MaxCandidates) that are within
  SecondaryRange percent of the phaser's full-damage range (0 = off, no
  limit), and adds them
  after your main target in the weapon group's target list. The game then
  sends each weapon to a target it can reach, and the main target, being
  first, keeps the weapons that reach it. Pulse weapons: all of them count
  as free, the game decides which ones reach the main target.
- It is switched on and off with a key (ToggleKey, default J) or with the
  "Secondary Target" button in the tactical officer's menu (like Auto Fire);
  the button shows the state. StartEnabled = 1 switches it on at the start of
  each battle. While OFF the module does nothing to your weapons. If J already
  does something in the game, on a ship with the technology the key now
  toggles the module: change ToggleKey in the Config.
- While ON, the "one shot at a time" restriction (single fire) of the ship's
  phasers is switched off. Pulse weapons keep their own setting (single stays
  single, multi stays multi) and torpedoes are unchanged. The
  original value is put back when you switch it OFF, change ship, the ship
  dies or the technology is lost. Switching OFF also removes the secondary
  targets.
- Weapons (Ships.py number or Config): 1 phasers, 2 torpedoes, 4 pulse
  weapons.
- Torpedoes: the tubes that cannot reach your main target (it is outside
  their fixed 30 degree cone) shoot at the other enemies they reach, within
  SecondaryTorpedoRange km (30; 0 = no limit). The game launches one torpedo
  every 0.5 s per system, in turn, so the secondary ones wait their turn and
  the main target goes first. Torpedo single fire is left as the ship has it.
- Torpedoes with manual fire: while you hold the fire key the game only keeps
  the torpedo group firing in short windows (one launch per window) and stops
  it when the forward tubes run empty, even with the key held. The module
  re-arms the group while the key is held, so the tubes that reach your main
  target fire there and the free tubes launch at the secondary targets (e.g.
  7 forward tubes at the main target, then the 7 aft tubes at a secondary).
  Safety limits: at most 20 re-arms or 20 s per key press, only while the main
  target stays the same; every release of the key clears it.
- Torpedoes with Auto Fire: Auto Fire itself sends the tubes that cannot
  reach the target to secondary targets they can reach (see
  SecondaryTorpedoes in the Auto Fire section); tubes that reach the main
  target keep their torpedoes for it.
- Phasers with Auto Fire: while a bank reaches the main target, this module
  adds the secondaries as above. If no ready bank reaches the main target,
  Auto Fire starts the group at a secondary a ready bank reaches (see
  SecondaryPhasers in the Auto Fire section; candidates as above).
- With the Auto Fire arc rules (PulseRule / TorpedoRule 1 or 2) a secondary
  is added only if a weapon that does not reach the main target has it inside
  the allowed arc percent (and, with rule 2, inside the secondary flight-time
  limit); with manual fire your main target is never restricted.
  Pulse weapons under Auto Fire are handled by Auto Fire.
- The optional engine patches (one bank per target, log file) are described
  in "Engine patches" below. The module works without them (several banks may
  then shoot the same target, and there is no log file).
Settings: scripts\Custom\Spaceframe\Modules\SecondaryTarget\Config.py
- ToggleKey (J), StartEnabled (1), Weapons (7), Interval (0.2 s),
  MaxCandidates (4), SecondaryRange (100), SecondaryTorpedoRange (30 km),
  Debug (0). Read once when a battle starts. With Debug = 1 (and the "fileio"
  patch) the module writes its trace to Spaceframe_debug.log in the game folder.

Engine patches (stbc.exe, optional)
-----------------------------------
Managed with "python tools/exe_patch.py status|apply|revert|verify" (needs
Python with capstone, pefile and keystone). Each patch is hash-checked, works
only on the build it checks for and keeps a backup stbc.exe.orig-<hash>. Close
the game first. Use --patch NAME to pick one; "revert --all" undoes every
patch; "status" lists both.
- onebank (default when no name is given): one weapon bank per target. The game
  itself only knows "one bank at a time"; with the patch, banks that reach
  different targets fire together but two banks never share the same target.
  Affects every ship of the game, AI included.
- fileio: lets Python scripts open files. The game blocks it ("Securelevel
  prevents file IO"); this patch is what allows Spaceframe_debug.log (Debug =
  1). Apply with "python tools/exe_patch.py apply --patch fileio", undo with
  "revert --patch fileio". SECURITY: while it is applied, ANY script of the
  game or of other mods can read and write files; apply it only if you trust
  everything you installed, and revert it when you no longer need the log.

Which ship name to use
----------------------
Use the ship's FILE NAME, without the extension, with upper and lower case
exactly the same (same name as scripts\Custom\Bedrock\Ships\<Name>.py and
scripts\ships\<Name>.py).
    Right:  "AkiraCVS"   (file AkiraCVS.py)
    Wrong:  "Akira CVS"  (name shown in the game)
    Wrong:  "Akira"      (enables the regular Akira, not the CVS variant)
Each variant needs its own entry. The in-game name does not always match the
file name: the "Peregrine FT" in the menu is the file Fighter.py.

Diagnostics
-----------
Start the game with the "Test Mode" shortcut, enter a Quick Battle, open the
console (~ key) and type, one line at a time:
    import Custom.Spaceframe.Spaceframe
    Custom.Spaceframe.Spaceframe.Diag()
It shows the core state, every module (with its version), every ship with its file name and,
for MV Shields, the charge of each facing.

Writing a module
----------------
Create scripts\Custom\Spaceframe\Modules\<Name>\ with an empty __init__.py and
<Name>.py. All functions are optional:
    Start(pCore)             - at mission start (pCore = the Spaceframe core)
    Stop()                   - at mission end
    Tick(lShips)             - on every timer cycle, with the live ships
    WeaponHit(pShip, pEvent) - when a weapon hits a ship
    Diag()                   - extra lines for the diagnostics command
Core helpers: pCore.GetShipTech(pShip, sTech, pDefault),
pCore.GetShipFileName(pShip), pCore.GetShipsInPlay(), pCore.GetInterval(),
pCore.GetModule(sName), pCore.Log(sModule, sText). A module's ships are set
in Ships.py under its name.
Python 1.5.2 rules: no "+=", no list comprehensions, no True/False, no
"continue" inside a "try" block.

Uninstalling
------------
Delete scripts\Custom\Spaceframe and restore QuickBattle.py from the .mvbak
(or delete the two blocks marked "Spaceframe").

Limitations
-----------
- Quick Battle only (no campaign, no multiplayer).
- Close the Config.py files in your text editor after editing them: an
  editor left open may later save an old copy over the file.


===============================================================================
2. [ES] ESPANOL
===============================================================================

Que es
------
Spaceframe es un nucleo pequeno que carga modulos de juego y les ofrece
servicios compartidos: un temporizador, un manejador de impactos de arma,
identificacion de naves, registro de mensajes y aislamiento de errores. Los
modulos no tocan los archivos del juego, y un modulo que falla se desactiva
solo, mientras los demas siguen funcionando. Un modulo que falla en una nave
no detiene a los demas, y solo se desactiva tras 50 ciclos seguidos con
error. Hecho para BC Remastered y
Orion Delta, en Python 1.5.2 puro, sin Foundation, QBautostart ni
Kobayashi Maru.

Archivos
--------
scripts\Custom\Spaceframe\Spaceframe.py   - el nucleo
scripts\Custom\Spaceframe\Config.py       - configuracion del nucleo
scripts\Custom\Spaceframe\Ships.py        - que naves usan que tecnologia
scripts\Custom\Spaceframe\Modules\        - una carpeta por modulo
scripts\QuickBattle\QuickBattle.py        - recibio 2 bloques pequenos (marcados "Spaceframe")
scripts\QuickBattle\QuickBattle.py.mvbak  - copia de seguridad del original

Configuracion del nucleo (scripts\Custom\Spaceframe\Config.py)
--------------------------------------------------------------
Modules             - los modulos se activan automaticamente; ponga 0 para
                      desactivar uno, p. ej. "MVShields": 0
Interval            - tiempo entre ciclos del temporizador (por defecto 0,25 s)
EnableInMultiplayer - 1 = tambien funciona en multijugador (puede desincronizar)
Debug               - 2 = el log (como 1) y ademas avisos cortos en pantalla.
                      1 = escribe Spaceframe_debug.log en la carpeta del juego
                      (necesita el parche opcional "fileio" del motor, vea
                      "Parches del motor"; sin el, un aviso dice que el log no
                      esta disponible). Maximo 20000 lineas por sesion, cada una
                      con la hora del juego. Dejelo en 0 para jugar normal.
En todos los Config.py, los porcentajes se escriben de 0 a 100 (50 = 50%), y
las opciones de activar/desactivar como 1 o 0.

Lista de naves (scripts\Custom\Spaceframe\Ships.py)
----------------------------------------------------
Que tecnologias (nombres de los modulos) usa cada nave, para todas, por
raza, por familia y nave por nave:
      All      = {"AutoFire": Def}
      Races    = {"Federation": {"MVShields": Def}}
      Families = {"Galaxy": {"AblativeArmor": 80}}
      Ships    = {"Defiant": {"AblativeArmor": 100},
                  "Excelsior": {"MVShields": 0}}
Cada nivel reemplaza al anterior (All < Races < Families < plugin Bedrock de
la nave < Ships); 0 desactiva una tecnologia en esa nave. La raza y la
familia vienen del plugin Orion Delta de la nave: Race ("Federation",
"Romulan"...) y SubMenu (la familia, p. ej. "Galaxy" para todas sus
variantes). Las naves sin plugin, o con SubMenu "N/A", no tienen raza ni
familia. El comando de diagnostico muestra la raza y la familia de cada
nave.
Un 0 explicito (nave, raza o familia) desactiva la tecnologia de verdad: una
lista "Ships" vieja en el Config.py de un modulo ya no la vuelve a activar.
Def = el valor por defecto definido en el Config.py del modulo; o un
numero:
- "MVShields": eficiencia, 1 a 100 (por defecto: DefaultEfficiency, 100). Es
  la parte de la diferencia entre las caras que se corrige cada vez; valores
  mas bajos dejan la cara impactada debil por mas tiempo.
- "AblativeArmor": capacidad como porcentaje del casco (por defecto:
  DefaultArmor, 50).
- "AutoFire": Def (la nave puede usar el Auto Fire).
- "SecondaryTarget": Def, o un numero que suma los tipos de arma: 1 phasers,
  2 torpedos, 4 armas de pulso (p. ej. 5 = phasers y pulso). Def = la opcion
  Weapons del modulo.
En Orion Delta una nave tambien puede recibir una tecnologia desde su propio
plugin Bedrock (scripts\Custom\Bedrock\Ships\<Nave>.py, encima de
"###Do Not Change Below###"), p. ej. "MVShields = 80" (-1 alli = valor por
defecto); Ships manda sobre el.

Modulo MV Shields
-----------------
Las 6 caras del escudo de una nave funcionan como un escudo unico. La carga
total se redistribuye entre las caras en cada ciclo del temporizador y
tambien en el momento de cada impacto de arma, en proporcion a la capacidad
maxima de cada cara. La carga total nunca cambia, solo cambia de lugar.
Funciona junto con el Shield Transfer y los Power Macros de Orion.

Configuracion: scripts\Custom\Spaceframe\Modules\MVShields\Config.py
- Mode: cuando se redistribuyen los escudos: 0 = apagado, 1 = solo al
  impacto, 2 = solo en el ciclo, 3 = ambos (por defecto).
- DefaultEfficiency: eficiencia de las naves con Def (100).

Modulo Ablative Armor
---------------------
Cuando el dano atraviesa los escudos, el blindaje lo absorbe antes de que
llegue al casco o a cualquier subsistema. Cuando el blindaje se agota, el
dano pasa normalmente.
- Capacidad: un porcentaje del casco de la nave (por defecto 50%).
- El blindaje es un subsistema real de la nave ("Ablative Armor"). Se
  repara con la tasa de reparacion de la nave, como un subsistema mas dificil
  de reparar que el propio casco de la nave (ArmorComplexity, por defecto
  200%: el doble de dificil, o sea la mitad de la velocidad del casco), mas
  lento cuando el sistema de reparacion esta danado. Espera mientras el
  casco esta danado: primero se repara el casco, despues el blindaje.
  (Todavia no aparece en la lista de reparaciones.)
- Sangrado, como los escudos del juego: con el blindaje al 50% o mas lo
  detiene todo; por debajo, parte de cada golpe pasa al casco y a los
  subsistemas, creciendo en linea recta hasta 50% con el blindaje vacio
  (BleedStart, BleedMax).
- HUD: lo dibuja el modulo Status HUD (abajo).
- Si el juego rechaza el subsistema, el modulo usa un blindaje interno con
  su propia regeneracion (con Debug = 1, un mensaje indica el modo activo).
- Una nave que sale y vuelve conserva su unico subsistema Ablative Armor
  (sin duplicado, mantiene su estado).

Configuracion: scripts\Custom\Spaceframe\Modules\AblativeArmor\Config.py
- DefaultArmor (50), ArmorComplexity (200), BleedStart (50), BleedMax (50),
  SubsystemDamageCost (100), CreateSubsystem (1), Targetable (1).
- Si el juego se cierra cuando una nave blindada entra en la batalla, ponga
  CreateSubsystem = 0.

Modulo Status HUD
-----------------
Agrega una linea de estado a los paneles de naves del HUD tactico, justo
encima de la barra del casco:
- "Hull NN%" a la derecha, para todas las naves.
- Para naves con blindaje ablativo: "Armor NN%" a la izquierda, y una barra
  blanca sobre la barra del casco que muestra el blindaje en tiempo real.
- En el panel del jugador ("Shields") y en el del objetivo ("Target
  Shields"). El panel del jugador crece hacia arriba y los demas paneles de
  su fila crecen con el; el panel del objetivo crece hacia abajo y empuja la
  lista "Targets" hacia abajo si hace falta. Cada panel crece una cantidad
  fija toda la batalla (con o sin blindaje, con o sin objetivo), y vuelve a
  la normalidad al final de la batalla.
Configuracion: scripts\Custom\Spaceframe\Modules\StatusHUD\Config.py
- ShowHull (1), ShowArmor (1), ShowTarget (1), ExpandDisplay (1),
  ExpandRow (1), PlayerLineSpace (130), TargetLineSpace (150),
  HudBarHeight (100).
- Con el modulo Auto Fire encendido: "AUTO" en la esquina superior derecha
  del panel de armas.

Modulo Auto Fire
----------------
Dispara las armas de la nave que usted controla segun reglas de arco y de
tiempo de vuelo, para que pueda concentrarse en maniobrar. Solo para la nave del
jugador, y solo si tiene "AutoFire" en Ships.py.
- Encender y apagar: la tecla L (ToggleKey) o el boton "Auto Fire" del menu
  del oficial tactico. Encendido, "AUTO" aparece en verde en la esquina
  superior derecha del panel de armas (el que tiene la velocidad en el
  titulo).
- Solo dispara a los enemigos de la mision (nunca a naves aliadas o
  neutrales, aunque esten seleccionadas), solo en alerta roja y nunca
  camuflado; no cambia el nivel de alerta. Si usted mantiene una tecla de disparo, toma ese grupo de armas
  hasta soltarla.
- Phasers: disparan con el objetivo dentro de PhaserRange por ciento de su
  alcance de dano maximo, en el arco, y con carga de al menos
  PhaserMinCharge (0 = desactivado en ambos controles).
- Torpedos: el objetivo se predice donde estara cuando llegue el torpedo
  (la misma prediccion de la IA del juego). Un tubo dispara solo cuando ese
  punto esta dentro de una parte de su cono fijo de 30 grados (0 = centro,
  100 = borde) que depende del tiempo de vuelo estimado (distancia /
  velocidad del torpedo): TorpedoArcPercentNear % (90) a ArcFlightTimeNear
  segundos (0.5) o menos, cerrandose a TorpedoArcPercentFar % (70) a
  ArcFlightTimeFar segundos (1.5) o mas, proporcional entre medio. Una vez
  disparando, sigue hasta que el punto se pase TorpedoArcHysteresis puntos
  (0 = apagado). Se guardan TorpedoReserve torpedos.
- TorpedoRule 1 = solo el porcentaje de arco. TorpedoRule 2 (por defecto;
  cualquier otro valor cuenta como 2) agrega un limite de tiempo de vuelo: un
  tubo espera mientras el tiempo de vuelo supere TorpedoFlightTimeLimit
  segundos (1.5) mas el tiempo de guiado del propio torpedo, nunca mas que su
  vida. 0 = sin limite; una velocidad desconocida nunca bloquea.
- Objetivos grandes o lentos (regla 2): un tiro por encima del limite sale
  igual cuando el objetivo no puede apartarse a tiempo. Recibe
  raiz cuadrada de (2 x TargetSizeAllowance% x radio del objetivo / su
  aceleracion actual), en unidades del juego, mas el tiempo de guiado, hasta
  TargetSizeFlightTimeMax segundos (5.0). Un objetivo sin motores de impulso
  o sin aceleracion recibe ese maximo; motores danados alargan el tiempo.
  Nunca acorta un limite, asi que las naves pequenas y agiles conservan los
  limites de arriba. TargetSizeAllowance 100 = el radio del objetivo, mas =
  mas permisivo; 0 en cualquiera de los dos = apagado.
- Spread: el Auto Fire usa el mayor spread de la nave cuando el tiempo de
  vuelo esta entre SpreadFlightTimeMin (2.0) y SpreadFlightTimeMax (5.0; 0 =
  sin tope) y el punto previsto esta dentro de SpreadArcPercent (10) del
  cono; Single en otro caso. Esto solo elige COMO disparar: el limite de
  tiempo de vuelo sigue valiendo, asi que un objetivo limitado por debajo de
  SpreadFlightTimeMin nunca recibe spread. El modo spread es del sistema de
  torpedos: los secundarios disparados en la misma pulsacion que un spread al
  principal tambien salen en spread. Su propio spread vuelve al apagar el
  Auto Fire o al disparar torpedos a mano.
- Armas de pulso (disruptores, canones de pulso), cargadas: las mismas reglas
  de arco y tiempo de vuelo sobre el arco de tiro del arma, con PulseRule,
  PulseArcPercentNear / PulseArcPercentFar, PulseArcHysteresis y
  PulseFlightTimeLimit; los objetivos grandes o lentos tambien reciben el
  limite mayor. El spread no aplica. Con el Secondary Target ENCENDIDO
  tambien elige los objetivos secundarios de las armas libres, y dispara a un
  secundario solo cuando ningun arma tiene tiro al objetivo principal.
- Los objetivos secundarios tienen sus propios valores:
  TorpedoArcPercentNearSecondary / TorpedoArcPercentFarSecondary y
  TorpedoFlightTimeLimitSecondary (1.0), y los mismos ajustes Pulse... Un
  ajuste omitido toma el principal; los tiempos de vuelo del porcentaje de
  arco y la histeresis son compartidos.
- Forma del arco (TorpedoArcShape / PulseArcShape, 1 = por defecto): el
  porcentaje se mide como UN angulo desde el centro del arco (el cono para
  torpedos; una elipse inscrita en los limites propios del arma, tambien
  asimetricos, para pulso). En las esquinas del arco es mas estricto que
  sobre los ejes. 0 = profundidad antigua por caja (cada eje aparte).
- HoldOnWarp = 1: torpedos y armas de pulso esperan mientras el objetivo hace
  un warp dentro del sistema y durante WarpHoldGrace segundos (1.0) despues;
  el disparo manual nunca se retiene. 0 = apagado.
- TapFire = 1: torpedos y armas de pulso se disparan con toques rapidos
  (mas rapido que mantener la tecla); los phasers siempre se mantienen.
- SecondaryTorpedoes = 1: con el Secondary Target ENCENDIDO en la nave
  (torpedos permitidos), los tubos de torpedo que no alcanzan el objetivo
  disparan solos a otros enemigos que si alcanzan, con la misma regla del
  objetivo principal (TorpedoRule) y el TorpedoReserve. Los tubos que alcanzan el objetivo
  principal guardan los torpedos para el. Si ninguno lo alcanza, los tubos
  libres disparan al mejor secundario, con la misma regla de spread.
  0 = apagado.
- SecondaryPhasers = 1: con el Secondary Target ENCENDIDO en la nave
  (phasers permitidos), un grupo de phasers cuyos bancos no alcanzan el
  objetivo principal dispara a un objetivo secundario que un banco listo
  alcanza (el mas cercano primero), y vuelve al principal en cuanto un banco
  lo alcanza. Si un banco alcanza el principal, nada cambia. 0 = apagado.
- TargetMode: 0 = solo su objetivo seleccionado; 1 = su objetivo, y sin
  ninguno (o tras una baja) el enemigo mas cercano pasa a ser su objetivo;
  2 = cada grupo de armas elige su enemigo (phasers el mas cercano que
  alcanzan, torpedos y pulso la mejor nota de
  arco).
Configuracion: scripts\Custom\Spaceframe\Modules\AutoFire\Config.py (cada
opcion esta descrita alli). Se
leen una vez al empezar la batalla: los cambios valen desde la proxima
batalla (Quick Battle), no durante la actual.

Modulo Secondary Target
-----------------------
Con varios enemigos, muchas armas quedan paradas porque no alcanzan el
objetivo que usted selecciono. Este modulo hace que esas armas disparen a
otros enemigos que si alcanzan, mientras su objetivo principal conserva todas
las armas que lo alcanzan. Solo para la nave del jugador, y solo si tiene
"SecondaryTarget" en Ships.py.
- Funciona mientras un grupo de armas dispara al objetivo principal, ya sea
  porque usted mantiene la tecla de disparo o porque el Auto Fire esta
  encendido. Si suelta la tecla, el modulo para con ella: nunca dispara por
  su cuenta y solo dispara a los enemigos de la mision (nunca a naves
  aliadas o neutrales).
- En cada ciclo mira los enemigos mas cercanos (MaxCandidates) que esten
  dentro de SecondaryRange por ciento del alcance de dano maximo del phaser
  (0 = desactivado, sin limite),
  y los agrega despues de su objetivo principal en la lista de objetivos del
  grupo. El juego envia cada arma a un objetivo que alcanza, y el principal,
  por ir primero, conserva las armas que lo alcanzan. Armas de pulso: todas
  cuentan como libres, el juego decide cuales alcanzan el principal.
- Se enciende y apaga con una tecla (ToggleKey, por defecto J) o con el boton
  "Secondary Target" del menu del oficial tactico (como el Auto Fire); el
  boton muestra el estado. StartEnabled = 1 enciende el modulo al empezar cada
  batalla. Apagado, el modulo no hace nada con las armas. Si J ya hace algo en
  el juego, en una nave con la tecnologia la tecla pasa a encender/apagar el
  modulo: cambie ToggleKey en el Config.
- Mientras esta ENCENDIDO, la restriccion de "un disparo a la vez" (single
  fire) de los phasers de la nave queda desactivada. Las armas de pulso
  mantienen su propio ajuste (single sigue single, multi sigue multi) y los
  torpedos no cambian. El valor original se devuelve al APAGAR, al cambiar de
  nave, cuando la nave muere o al perder la tecnologia. Al apagar tambien se
  quitan los objetivos secundarios.
- Weapons (numero de Ships.py o Config): 1 phasers, 2 torpedos, 4 armas de
  pulso.
- Torpedos: los tubos que no alcanzan su objetivo principal (esta fuera de su
  cono fijo de 30 grados) disparan a los otros enemigos que si alcanzan, a
  SecondaryTorpedoRange km o menos (30; 0 = sin limite). El juego lanza un
  torpedo cada 0,5 s por sistema, por turnos: los secundarios esperan su
  turno y el objetivo principal va primero. El single fire de los torpedos se
  deja como lo define la nave.
- Torpedos con disparo manual: mientras mantiene la tecla de disparo, el juego
  solo mantiene el grupo de torpedos disparando en ventanas cortas (un
  lanzamiento por ventana) y lo detiene cuando los tubos de proa se vacian,
  aunque la tecla siga apretada. El modulo vuelve a armar el grupo mientras la
  tecla esta apretada: los tubos que alcanzan su objetivo principal disparan
  alli y los tubos libres lanzan a los objetivos secundarios (p. ej. 7 tubos de
  proa al principal y despues los 7 de popa a un secundario). Limites de
  seguridad: como maximo 20 rearmados o 20 s por pulsacion, solo mientras el
  objetivo principal sea el mismo; cada vez que suelta la tecla se limpia.
- Torpedos con Auto Fire: el propio Auto Fire manda los tubos que no
  alcanzan el objetivo a objetivos secundarios que si alcanzan (vea
  SecondaryTorpedoes en la seccion del Auto Fire); los tubos que alcanzan
  el objetivo principal guardan los torpedos para el.
- Phasers con Auto Fire: mientras un banco alcanza el objetivo principal, este
  modulo anade los secundarios como arriba. Si ningun banco listo alcanza el
  principal, el Auto Fire inicia el grupo en un secundario que un banco listo
  alcanza (vea SecondaryPhasers en la seccion del Auto Fire).
- Con las reglas de arco del Auto Fire (PulseRule / TorpedoRule 1 o 2) un
  secundario solo se agrega si un arma que no alcanza el objetivo principal
  lo tiene dentro del porcentaje de arco permitido (y, con la regla 2, dentro
  del limite secundario de tiempo de vuelo); con disparo manual su objetivo
  principal nunca se restringe. Las armas de pulso bajo Auto Fire las maneja
  el Auto Fire.
- Los parches opcionales del motor (un banco por objetivo, archivo de log) se
  describen en "Parches del motor" mas abajo. El modulo funciona sin ellos
  (varios bancos pueden disparar al mismo objetivo, y no hay archivo de log).
Configuracion: scripts\Custom\Spaceframe\Modules\SecondaryTarget\Config.py
- ToggleKey (J), StartEnabled (1), Weapons (7), Interval (0,2 s),
  MaxCandidates (4), SecondaryRange (100), SecondaryTorpedoRange (30 km),
  Debug (0). Se leen una vez al empezar la batalla. Con Debug = 1 (y el parche
  "fileio") el modulo escribe su traza en Spaceframe_debug.log, en la carpeta
  del juego.

Parches del motor (stbc.exe, opcionales)
----------------------------------------
Se gestionan con "python tools/exe_patch.py status|apply|revert|verify"
(necesita Python con capstone, pefile y keystone). Cada parche comprueba el
hash, sirve solo para la build que verifica y guarda una copia
stbc.exe.orig-<hash>. Cierre el juego antes. Use --patch NOMBRE para elegir
uno; "revert --all" deshace todos; "status" lista ambos.
- onebank (por defecto si no se da nombre): un banco de armas por objetivo. El
  juego solo conoce "un banco a la vez"; con el parche, los bancos que
  alcanzan objetivos distintos disparan juntos, pero dos bancos nunca
  comparten el mismo objetivo. Afecta a todas las naves del juego, tambien las
  de la IA.
- fileio: permite que los scripts Python abran archivos. El juego lo bloquea
  ("Securelevel prevents file IO"); este parche es lo que permite
  Spaceframe_debug.log (Debug = 1). Se aplica con "python tools/exe_patch.py
  apply --patch fileio" y se deshace con "revert --patch fileio". SEGURIDAD:
  mientras este aplicado, CUALQUIER script del juego o de otros mods puede leer
  y escribir archivos; apliquelo solo si confia en todo lo que instalo, y
  deshagalo cuando ya no necesite el log.

Que nombre de nave usar
-----------------------
Use el NOMBRE DEL ARCHIVO de la nave, sin la extension, con mayusculas y
minusculas exactamente iguales (el mismo nombre de
scripts\Custom\Bedrock\Ships\<Nombre>.py y scripts\ships\<Nombre>.py).
    Correcto:   "AkiraCVS"   (archivo AkiraCVS.py)
    Incorrecto: "Akira CVS"  (nombre que aparece en el juego)
    Incorrecto: "Akira"      (activa la Akira comun, no la variante CVS)
Cada variante necesita su propia entrada. El nombre del juego no siempre
coincide con el del archivo: la "Peregrine FT" del menu es el archivo
Fighter.py.

Diagnostico
-----------
Abra el juego con el acceso directo "Test Mode", entre en una Quick Battle,
abra la consola (tecla ~) y escriba, una linea a la vez:
    import Custom.Spaceframe.Spaceframe
    Custom.Spaceframe.Spaceframe.Diag()
Muestra el estado del nucleo, cada modulo (con su version), cada nave con su nombre de archivo
y, para MV Shields, la carga de cada cara.

Crear un modulo
---------------
Cree scripts\Custom\Spaceframe\Modules\<Nombre>\ con un __init__.py vacio y
<Nombre>.py. Todas las funciones son opcionales:
    Start(pCore)             - al inicio de la mision (pCore = el nucleo)
    Stop()                   - al final de la mision
    Tick(lShips)             - en cada ciclo, con las naves vivas
    WeaponHit(pShip, pEvent) - cuando un arma impacta una nave
    Diag()                   - lineas extra para el comando de diagnostico
Ayudas del nucleo: pCore.GetShipTech(pShip, sTecnologia, pDefecto),
pCore.GetShipFileName(pShip), pCore.GetShipsInPlay(), pCore.GetInterval(),
pCore.GetModule(sModulo), pCore.Log(sModulo, sTexto). Las naves de un modulo
se definen en Ships.py con su nombre.
Reglas de Python 1.5.2: sin "+=", sin list comprehensions, sin True/False,
sin "continue" dentro de un bloque "try".

Desinstalar
-----------
Borre scripts\Custom\Spaceframe y restaure QuickBattle.py desde el .mvbak
(o borre los dos bloques marcados "Spaceframe").

Limitaciones
------------
- Solo Quick Battle (ni campana ni multijugador).
- Cierre los archivos Config.py en su editor de texto despues de editarlos:
  un editor que queda abierto puede guardar mas tarde una copia vieja encima.


===============================================================================
3. [PT] PORTUGUES
===============================================================================

O que e
-------
O Spaceframe e um nucleo pequeno que carrega modulos de jogo e oferece a eles
servicos compartilhados: um timer, um handler de impacto de arma,
identificacao de naves, log e isolamento de erros. Os modulos nao mexem nos
arquivos do jogo, e um modulo que falha e desligado sozinho, enquanto os
outros continuam rodando. Um modulo que falha em uma nave nao para os
outros, e so e desligado depois de 50 ciclos seguidos com erro. Feito para o
BC Remastered e o Orion Delta, em
Python 1.5.2 puro, sem Foundation, QBautostart nem Kobayashi Maru.

Arquivos
--------
scripts\Custom\Spaceframe\Spaceframe.py   - o nucleo
scripts\Custom\Spaceframe\Config.py       - configuracao do nucleo
scripts\Custom\Spaceframe\Ships.py        - quais naves usam quais tecnologias
scripts\Custom\Spaceframe\Modules\        - uma pasta por modulo
scripts\QuickBattle\QuickBattle.py        - recebeu 2 blocos pequenos (marcados "Spaceframe")
scripts\QuickBattle\QuickBattle.py.mvbak  - backup do original

Configuracao do nucleo (scripts\Custom\Spaceframe\Config.py)
------------------------------------------------------------
Modules             - os modulos sao ligados automaticamente; coloque 0 para
                      desligar um, ex. "MVShields": 0
Interval            - tempo entre os ciclos do timer (padrao 0,25 s)
EnableInMultiplayer - 1 = funciona tambem no multiplayer (pode dessincronizar)
Debug               - 2 = o log (como 1) e tambem avisos curtos na tela.
                      1 = grava Spaceframe_debug.log na pasta do jogo (precisa do
                      patch opcional "fileio" do motor, veja "Patches do
                      motor"; sem ele, um aviso diz que o log nao esta
                      disponivel). Maximo 20000 linhas por sessao, cada uma com
                      a hora do jogo. Deixe em 0 para jogar normal.
Em todos os Config.py, porcentagens sao escritas de 0 a 100 (50 = 50%), e
as opcoes de ligar/desligar como 1 ou 0.

Lista de naves (scripts\Custom\Spaceframe\Ships.py)
----------------------------------------------------
Quais tecnologias (nomes dos modulos) cada nave usa, para todas, por raca,
por familia e nave por nave:
      All      = {"AutoFire": Def}
      Races    = {"Federation": {"MVShields": Def}}
      Families = {"Galaxy": {"AblativeArmor": 80}}
      Ships    = {"Defiant": {"AblativeArmor": 100},
                  "Excelsior": {"MVShields": 0}}
Cada nivel substitui o anterior (All < Races < Families < plugin Bedrock da
nave < Ships); 0 desliga uma tecnologia naquela nave. A raca e a familia vem
do plugin Orion Delta da nave: Race ("Federation", "Romulan"...) e SubMenu
(a familia, ex. "Galaxy" para todas as variantes). Naves sem plugin, ou com
SubMenu "N/A", nao tem raca nem familia. O comando de diagnostico mostra a
raca e a familia de cada nave.
Um 0 explicito (nave, raca ou familia) desliga a tecnologia de verdade: uma
lista "Ships" antiga no Config.py de um modulo nao a liga mais.
Def = o valor padrao definido no Config.py do modulo; ou um numero:
- "MVShields": eficiencia, 1 a 100 (padrao: DefaultEfficiency, 100). E a
  parte da diferenca entre as faces corrigida a cada vez; valores menores
  deixam a face atingida fraca por mais tempo.
- "AblativeArmor": capacidade como porcentagem do casco (padrao:
  DefaultArmor, 50).
- "AutoFire": Def (a nave pode usar o Auto Fire).
- "SecondaryTarget": Def, ou um numero que soma os tipos de arma: 1 phasers,
  2 torpedos, 4 armas de pulso (ex. 5 = phasers e pulso). Def = a opcao
  Weapons do modulo.
No Orion Delta uma nave tambem pode receber uma tecnologia pelo proprio
plugin Bedrock (scripts\Custom\Bedrock\Ships\<Nave>.py, acima de
"###Do Not Change Below###"), ex. "MVShields = 80" (-1 ali = valor padrao).
O Ships vale sobre ele.

Modulo MV Shields
-----------------
As 6 faces do escudo de uma nave funcionam como um escudo unico. A carga
total e redistribuida entre as faces a cada ciclo do timer e tambem na hora
de cada impacto de arma, proporcional a capacidade maxima de cada face. A
carga total nunca muda, so troca de lugar. Funciona junto com o Shield
Transfer e os Power Macros do Orion.

Configuracao: scripts\Custom\Spaceframe\Modules\MVShields\Config.py
- Mode: quando os escudos sao redistribuidos: 0 = desligado, 1 = so no
  impacto, 2 = so no ciclo, 3 = os dois (padrao).
- DefaultEfficiency: eficiencia das naves com Def (100).

Modulo Ablative Armor
---------------------
Quando o dano passa pelos escudos, a blindagem absorve antes que ele chegue
ao casco ou a qualquer subsistema. Quando a blindagem acaba, o dano passa
normalmente.
- Capacidade: uma porcentagem do casco da nave (padrao 50%).
- A blindagem e um subsistema real da nave ("Ablative Armor"). Ela e
  reparada com a taxa de reparo da nave, como um subsistema mais dificil de
  reparar que o proprio casco da nave (ArmorComplexity, padrao 200%: o dobro
  de dificil, ou seja metade da velocidade do casco), mais devagar quando o
  sistema de reparo esta danificado. Ela espera enquanto o casco estiver
  danificado: primeiro o casco e reparado, depois a blindagem. (Ainda nao
  aparece na lista de reparos.)
- Vazamento (bleed-through), como os escudos do jogo: com a blindagem em 50%
  ou mais ela segura tudo; abaixo disso, parte de cada golpe passa para o
  casco e os subsistemas, crescendo em linha reta ate 50% com a blindagem
  vazia (BleedStart, BleedMax).
- HUD: desenhado pelo modulo Status HUD (abaixo).
- Se o jogo recusar o subsistema, o modulo usa uma blindagem interna com
  regeneracao propria (com Debug = 1, uma mensagem mostra o modo ativo).
- Uma nave que sai e volta mantem seu unico subsistema Ablative Armor
  (sem duplicata, mantem a condicao).

Configuracao: scripts\Custom\Spaceframe\Modules\AblativeArmor\Config.py
- DefaultArmor (50), ArmorComplexity (200), BleedStart (50), BleedMax (50),
  SubsystemDamageCost (100), CreateSubsystem (1), Targetable (1).
- Se o jogo fechar quando uma nave blindada entrar na batalha, coloque
  CreateSubsystem = 0.

Modulo Status HUD
-----------------
Adiciona uma linha de status aos paineis de nave do HUD tatico, logo acima
da barra do casco:
- "Hull NN%" a direita, para todas as naves.
- Para naves com blindagem ablativa: "Armor NN%" a esquerda, e uma barra
  branca sobre a barra do casco mostrando a blindagem em tempo real.
- No painel do jogador ("Shields") e no do alvo ("Target Shields"). O painel
  do jogador cresce para cima e os outros paineis da fileira crescem junto;
  o painel do alvo cresce para baixo e empurra a lista "Targets" para baixo
  se precisar. Cada painel cresce um valor fixo a batalha toda (com ou sem
  blindagem, com ou sem alvo), e volta ao normal no fim da batalha.
Configuracao: scripts\Custom\Spaceframe\Modules\StatusHUD\Config.py
- ShowHull (1), ShowArmor (1), ShowTarget (1), ExpandDisplay (1),
  ExpandRow (1), PlayerLineSpace (130), TargetLineSpace (150),
  HudBarHeight (100).
- Com o modulo Auto Fire ligado: "AUTO" no canto superior direito do painel
  de armas.

Modulo Auto Fire
----------------
Dispara as armas da nave que voce controla por regras de arco e tempo de
voo, para voce se concentrar em manobrar. So para a nave do jogador, e so se ela
tiver "AutoFire" no Ships.py.
- Ligar e desligar: a tecla L (ToggleKey) ou o botao "Auto Fire" no menu do
  oficial tatico. Ligado, "AUTO" aparece em verde no canto superior direito
  do painel de armas (o que tem a velocidade no titulo).
- So dispara nos inimigos da missao (nunca em naves aliadas ou neutras,
  mesmo selecionadas), so em alerta vermelho e nunca camuflado; nao muda o
  nivel de alerta. Segurar uma tecla de disparo assume aquele grupo de armas ate
  voce soltar.
- Phasers: disparam com o alvo dentro de PhaserRange por cento do alcance de
  dano maximo, no arco, e com carga de pelo menos PhaserMinCharge
  (0 = desligado em ambos os controles).
- Torpedos: o alvo e previsto onde estara quando o torpedo chegar (a mesma
  previsao da IA do jogo). Um tubo so dispara quando esse ponto esta dentro
  de uma parte do cone fixo de 30 graus dele (0 = centro, 100 = borda) que
  depende do tempo de voo estimado (distancia / velocidade do torpedo):
  TorpedoArcPercentNear % (90) com ArcFlightTimeNear segundos (0.5) ou menos,
  fechando para TorpedoArcPercentFar % (70) com ArcFlightTimeFar segundos
  (1.5) ou mais, proporcional no meio. Depois de comecar a disparar, continua
  ate o ponto passar TorpedoArcHysteresis pontos (0 = desligado). Ficam
  guardados TorpedoReserve torpedos.
- TorpedoRule 1 = so a porcentagem do arco. TorpedoRule 2 (padrao; qualquer
  outro valor conta como 2) acrescenta um limite de tempo de voo: um tubo
  espera enquanto o tempo de voo passar de TorpedoFlightTimeLimit segundos
  (1.5) mais o tempo de guiamento do proprio torpedo, nunca mais que a vida
  dele. 0 = sem limite; uma velocidade desconhecida nunca bloqueia.
- Alvos grandes ou lentos (regra 2): um tiro acima do limite sai mesmo assim
  quando o alvo nao consegue sair da frente a tempo. Ele ganha
  raiz quadrada de (2 x TargetSizeAllowance% x raio do alvo / aceleracao
  atual dele), em unidades do jogo, mais o tempo de guiamento, ate
  TargetSizeFlightTimeMax segundos (5.0). Um alvo sem motores de impulso ou
  sem aceleracao ganha esse maximo; motores danificados aumentam o tempo.
  Nunca encurta um limite, entao naves pequenas e ageis mantem os limites
  acima. TargetSizeAllowance 100 = o raio do alvo, mais = mais permissivo;
  0 em qualquer um dos dois = desligado.
- Spread: o Auto Fire usa o maior spread da nave quando o tempo de voo fica
  entre SpreadFlightTimeMin (2.0) e SpreadFlightTimeMax (5.0; 0 = sem teto) e
  o ponto previsto esta dentro de SpreadArcPercent (10) do cone; Single nos
  outros casos. Isso so escolhe COMO disparar: o limite de tempo de voo
  continua valendo, entao um alvo limitado abaixo de SpreadFlightTimeMin
  nunca recebe spread. O modo spread e do sistema de torpedos: os secundarios
  disparados no mesmo acionamento de um spread no principal tambem saem em
  spread. O seu spread volta ao desligar o Auto Fire ou ao disparar torpedos
  na mao.
- Armas de pulso (disruptores, canhoes de pulso), carregadas: as mesmas
  regras de arco e tempo de voo sobre o arco de tiro da arma, com PulseRule,
  PulseArcPercentNear / PulseArcPercentFar, PulseArcHysteresis e
  PulseFlightTimeLimit; alvos grandes ou lentos tambem ganham o limite maior.
  Spread nao se aplica. Com o Secondary Target LIGADO tambem escolhe os alvos
  secundarios das armas livres, e atira em um secundario sozinho quando
  nenhuma arma tem tiro no alvo principal.
- Os alvos secundarios tem os proprios valores:
  TorpedoArcPercentNearSecondary / TorpedoArcPercentFarSecondary e
  TorpedoFlightTimeLimitSecondary (1.0), e os mesmos ajustes Pulse... Um
  ajuste omitido usa o principal; os tempos de voo da porcentagem do arco e a
  histerese sao compartilhados.
- Formato do arco (TorpedoArcShape / PulseArcShape, 1 = padrao): o porcentual
  e medido como UM angulo a partir do centro do arco (o cone para torpedos;
  uma elipse inscrita nos limites da propria arma, tambem assimetricos, para
  pulso). Nos cantos do arco e mais estrito que sobre os eixos. 0 = a
  profundidade antiga por caixa (cada eixo separado).
- HoldOnWarp = 1: torpedos e armas de pulso esperam enquanto o alvo faz um
  warp dentro do sistema e por WarpHoldGrace segundos (1.0) depois; o disparo
  manual nunca e segurado. 0 = desligado.
- TapFire = 1: torpedos e armas de pulso sao disparados com toques rapidos
  (mais rapido que segurar a tecla); os phasers sao sempre segurados.
- SecondaryTorpedoes = 1: com o Secondary Target LIGADO na nave (torpedos
  permitidos), os tubos de torpedo que nao alcancam o alvo disparam, por
  conta propria, contra outros inimigos que alcancam, com a mesma regra do
  alvo principal (TorpedoRule) e o TorpedoReserve. Os tubos que alcancam o alvo principal
  guardam os torpedos para ele. Se nenhum tubo o alcanca, os tubos livres
  atiram no melhor secundario, com a mesma regra de spread. 0 = desligado.
- SecondaryPhasers = 1: com o Secondary Target LIGADO na nave (phasers
  permitidos), um grupo de phasers cujos bancos nao alcancam o alvo principal
  atira em um alvo secundario que um banco pronto alcanca (o mais proximo
  primeiro), e volta ao principal assim que um banco o alcanca. Se um banco
  alcanca o principal, nada muda. 0 = desligado.
- TargetMode: 0 = so o alvo que voce selecionou; 1 = o seu alvo, e sem
  nenhum (ou depois de um abate) o inimigo mais proximo vira o seu alvo;
  2 = cada grupo de armas escolhe o proprio inimigo (phasers o mais
  proximo que alcancam, torpedos e pulso a melhor nota de arco).
Configuracao: scripts\Custom\Spaceframe\Modules\AutoFire\Config.py (cada
opcao esta descrita la). Sao lidas
uma vez ao comecar a batalha: as mudancas valem a partir da proxima batalha
(Quick Battle), nao durante a atual.

Modulo Secondary Target
-----------------------
Com varios inimigos, muitas armas ficam paradas porque nao alcancam o alvo
que voce selecionou. Este modulo faz essas armas atirarem em outros inimigos
que elas alcancam, enquanto o seu alvo principal continua com todas as armas
que o alcancam. So para a nave do jogador, e so se ela tiver
"SecondaryTarget" no Ships.py.
- Funciona enquanto um grupo de armas atira no alvo principal, seja porque
  voce segura a tecla de disparo, seja porque o Auto Fire esta ligado. Soltou
  a tecla, o modulo para junto: nunca dispara sozinho e so atira nos inimigos
  da missao (nunca em naves aliadas ou neutras).
- A cada ciclo olha os inimigos mais proximos (MaxCandidates) que estejam
  dentro de SecondaryRange por cento do alcance de dano maximo do phaser
  (0 = desligado, sem limite), e
  os coloca depois do alvo principal na lista de alvos do grupo. O jogo manda
  cada arma para um alvo que ela alcanca, e o principal, por ser o primeiro,
  fica com as armas que o alcancam. Armas de pulso: todas contam como livres,
  o jogo decide quais alcancam o principal.
- Liga e desliga com uma tecla (ToggleKey, padrao J) ou com o botao "Secondary
  Target" no menu do oficial tatico (como o Auto Fire); o botao mostra o
  estado. StartEnabled = 1 liga o modulo no inicio de cada batalha. Desligado,
  o modulo nao faz nada nas armas. Se J ja faz algo no jogo, em uma nave com a
  tecnologia a tecla passa a ligar/desligar o modulo: troque ToggleKey no Config.
- Enquanto esta LIGADO, a restricao de "um tiro de cada vez" (single fire) dos
  phasers da nave fica desativada. As armas de pulso mantem o proprio ajuste
  (single continua single, multi continua multi) e os torpedos nao mudam. O valor original volta ao DESLIGAR, ao trocar de nave, quando a
  nave morre ou ao perder a tecnologia. Ao desligar, os alvos secundarios
  tambem sao retirados.
- Weapons (numero do Ships.py ou Config): 1 phasers, 2 torpedos, 4 armas de
  pulso.
- Torpedos: os tubos que nao alcancam o alvo principal (ele esta fora do cone
  fixo de 30 graus deles) atiram nos outros inimigos que alcancam, a
  SecondaryTorpedoRange km ou menos (30; 0 = sem limite). O jogo lanca um
  torpedo a cada 0,5 s por sistema, em revezamento: os secundarios esperam a
  vez e o alvo principal vai primeiro. O single fire dos torpedos fica como a
  nave define.
- Torpedos com disparo manual: enquanto voce segura a tecla de disparo, o jogo
  so mantem o grupo de torpedos atirando em janelas curtas (um lancamento por
  janela) e o para quando os tubos de proa esvaziam, mesmo com a tecla
  segurada. O modulo rearma o grupo enquanto a tecla esta segurada: os tubos
  que alcancam o alvo principal atiram nele e os tubos livres lancam nos alvos
  secundarios (ex.: 7 tubos de proa no principal, depois os 7 de popa em um
  secundario). Limites de seguranca: no maximo 20 rearmes ou 20 s por
  pressionamento, so enquanto o alvo principal for o mesmo; toda vez que solta
  a tecla isso e limpo.
- Torpedos com Auto Fire: o proprio Auto Fire manda os tubos que nao
  alcancam o alvo para alvos secundarios que eles alcancam (veja
  SecondaryTorpedoes na secao do Auto Fire); os tubos que alcancam o alvo
  principal guardam os torpedos para ele.
- Phasers com Auto Fire: enquanto um banco alcanca o alvo principal, este
  modulo adiciona os secundarios como acima. Se nenhum banco pronto alcanca o
  principal, o Auto Fire inicia o grupo em um secundario que um banco pronto
  alcanca (veja SecondaryPhasers na secao do Auto Fire).
- Com as regras de arco do Auto Fire (PulseRule / TorpedoRule 1 ou 2) um
  secundario so e adicionado se uma arma que nao alcanca o alvo principal o
  tem dentro da porcentagem de arco permitida (e, com a regra 2, dentro do
  limite secundario de tempo de voo); com disparo manual o seu alvo principal
  nunca e restringido. As armas de pulso sob Auto Fire sao tratadas pelo
  Auto Fire.
- Os patches opcionais do motor (um banco por alvo, arquivo de log) estao
  descritos em "Patches do motor" abaixo. O modulo funciona sem eles (varios
  bancos podem atirar no mesmo alvo, e nao ha arquivo de log).
Configuracao: scripts\Custom\Spaceframe\Modules\SecondaryTarget\Config.py
- ToggleKey (J), StartEnabled (1), Weapons (7), Interval (0,2 s),
  MaxCandidates (4), SecondaryRange (100), SecondaryTorpedoRange (30 km),
  Debug (0). Sao lidas uma vez ao comecar a batalha. Com Debug = 1 (e o patch
  "fileio") o modulo grava seu rastro em Spaceframe_debug.log, na pasta do
  jogo.

Patches do motor (stbc.exe, opcionais)
--------------------------------------
Sao gerenciados com "python tools/exe_patch.py status|apply|revert|verify"
(precisa de Python com capstone, pefile e keystone). Cada patch confere o
hash, vale so para a build que verifica e guarda uma copia
stbc.exe.orig-<hash>. Feche o jogo antes. Use --patch NOME para escolher um;
"revert --all" desfaz todos; "status" lista os dois.
- onebank (padrao se nenhum nome for dado): um banco de armas por alvo. O jogo
  so conhece "um banco por vez"; com o patch, bancos que alcancam alvos
  diferentes atiram juntos, mas dois bancos nunca dividem o mesmo alvo. Afeta
  todas as naves do jogo, inclusive as da IA.
- fileio: permite que scripts Python abram arquivos. O jogo bloqueia isso
  ("Securelevel prevents file IO"); este patch e o que permite o
  Spaceframe_debug.log (Debug = 1). Aplique com "python tools/exe_patch.py
  apply --patch fileio" e desfaca com "revert --patch fileio". SEGURANCA:
  enquanto estiver aplicado, QUALQUER script do jogo ou de outros mods pode ler
  e gravar arquivos; aplique so se confia em tudo o que instalou, e desfaca
  quando nao precisar mais do log.

Qual nome de nave usar
----------------------
Use o NOME DO ARQUIVO da nave, sem a extensao, com maiusculas e minusculas
exatamente iguais (o mesmo nome de scripts\Custom\Bedrock\Ships\<Nome>.py e
scripts\ships\<Nome>.py).
    Certo:   "AkiraCVS"   (arquivo AkiraCVS.py)
    Errado:  "Akira CVS"  (nome que aparece no jogo)
    Errado:  "Akira"      (liga a Akira comum, nao a variante CVS)
Cada variante precisa de uma entrada propria. O nome do jogo nem sempre bate
com o do arquivo: a "Peregrine FT" do menu e o arquivo Fighter.py.

Diagnostico
-----------
Abra o jogo pelo atalho "Test Mode", entre num Quick Battle, abra o console
(tecla ~) e digite, uma linha de cada vez:
    import Custom.Spaceframe.Spaceframe
    Custom.Spaceframe.Spaceframe.Diag()
Mostra o estado do nucleo, cada modulo (com a sua versao), cada nave com o nome do arquivo e,
para o MV Shields, a carga de cada face.

Criar um modulo
---------------
Crie scripts\Custom\Spaceframe\Modules\<Nome>\ com um __init__.py vazio e
<Nome>.py. Todas as funcoes sao opcionais:
    Start(pCore)             - no inicio da missao (pCore = o nucleo)
    Stop()                   - no fim da missao
    Tick(lShips)             - a cada ciclo, com as naves vivas
    WeaponHit(pShip, pEvent) - quando uma arma atinge uma nave
    Diag()                   - linhas extras para o comando de diagnostico
Ajudas do nucleo: pCore.GetShipTech(pShip, sTecnologia, pPadrao),
pCore.GetShipFileName(pShip), pCore.GetShipsInPlay(), pCore.GetInterval(),
pCore.GetModule(sModulo), pCore.Log(sModulo, sTexto). As naves de um modulo
sao definidas no Ships.py com o nome dele.
Regras do Python 1.5.2: sem "+=", sem list comprehensions, sem True/False,
sem "continue" dentro de um bloco "try".

Desinstalar
-----------
Apague scripts\Custom\Spaceframe e restaure QuickBattle.py a partir do .mvbak
(ou apague os dois blocos marcados "Spaceframe").

Limitacoes
----------
- So Quick Battle (nao campanha, nao multiplayer).
- Feche os arquivos Config.py no editor de texto depois de editar: um editor
  que fica aberto pode salvar mais tarde uma copia antiga por cima.
