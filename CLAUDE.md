# Star Trek Bridge Commander mods

Talk to the user in Portuguese. Code comments in English; READMEs trilingual (EN/ES/PT).

## Environment
- Game: `D:\GOG Games\Star Trek Bridge Commander` = BC Remastered + Orion Delta (Bedrock).
  NO Foundation / FoundationTech / KM / QBautostart: never assume or add them.
- This repo is the source of truth. One folder per mod (`Spaceframe/`): `scripts/` mirrors the
  game's `scripts/`, `tests/` (py3 mocks), `docs/`, `patches/`, `README.txt`.
- Spaceframe = the user's module framework: core `Spaceframe.py`, `Config.py`, `Ships.py`
  (techs by All < Races < Families < Bedrock plugin < Ships), `Modules/<Name>/`.
  New gameplay features are Spaceframe modules, not edits to vanilla files.
- Vanilla files: change only inside `# <Mod> - start/end` blocks, original kept as `.mvbak`,
  blocks documented in `<Mod>/patches/`.

## Python 1.5.2 (game interpreter) - hard rules for `*/scripts/**`
No `+=`, comprehensions, `x if c else y`, `True/False/bool/dict()/zip/enumerate/sorted/set`,
keyword args in calls (use `apply`), `import a as b`, string methods (use `string` module),
`k in dict` (use `has_key`), `try/except/finally` together, `except X as e`, f-strings/`.format`,
nested scopes (inner def/lambda cannot see outer locals), `continue` inside `try` (whole module
fails to load). `global` at the top of the function. Write `print (x)` so py3 can parse it.
Files: CRLF, ASCII only, tab indentation.
`python tools/lint15.py` enforces this - its verdict beats memory.

## Commands (repo root)
- `python tools/check.py` - lint15 + all mock tests. Must be green before any install.
- `python tools/deploy.py status|install|pull|backup [Mod]` - install refuses to overwrite files
  the user edited in the game (often `Ships.py`, `Config.py`): `pull`, merge, then install.
  `edited` is real (game copy matches neither the last install nor HEAD): never `--force`
  without diffing the game copy first and telling the user.
- `python tools/build_api_index.py` - regenerate `docs/api/App-index.txt`.
- `python tools/dis15.py <file.pyc|dir> [--func Name] [--calls-only]` - disassemble game `.pyc`
  (Python 1.5); `--calls-only` prints `path:func:line: call` to grep real vanilla call patterns.
- `python tools/exe_probe.py <wrap|dis|xref|vt|vtof|str|names|field> ...` - read-only static probe of
  `stbc.exe` (capstone+pefile, SWIG wrappers name the functions). Facts: `docs/api/exe-weapons.md`.
  Exe work goes to `bc-reverser`. The exe is never overwritten without a hash-checked backup and
  the user's explicit OK; patches are for the user's install only, not committed binaries.
- `python tools/exe_patch.py status|verify|apply|revert|upgrade|selftest [--exe PATH]` - the engine patch
  "one bank per target" for phaser systems (hash-checked, backup `stbc.exe.orig-<sha8>`, cave v2;
  `selftest` runs on temp copies only). It changes `stbc.exe` itself and every ship of the game:
  `apply`/`revert`/`upgrade` only with the user's explicit OK and the game closed.

## Workflow (main agent = coordinator, keep your context small)
1. Lookups: one-liners (a name in `App-index.txt`, a fact in `learned.md`, a line in the repo)
   -> Grep yourself. Wide searches in the game install (vanilla/Bedrock usage of a call,
   ship label -> file name, several files to compare) -> `bc-scout`. Questions about what the
   engine itself does (stbc.exe functions, struct fields, patch feasibility) -> `bc-reverser`.
2. Code -> `bc-implementer` with a precise spec (files, behavior, config names, tests), or the
   path of a `bc-architect` spec file. Trivial config/text edits: do them yourself, then run `check.py`.
3. Every game-code change -> `bc-auditor` before install. Crash reports -> `bc-auditor` too.
4. `deploy.py install`, tell the user whether to restart the game (`.py` code: restart;
   `Ships.py`/`Config.py`: next Quick Battle). Then WAIT for the user's in-game test.
   Never say something works in game without the user confirming it; say what was only simulated.
5. Confirmed engine facts -> one line in `docs/api/learned.md`. Design decisions for a feature ->
   that mod's `docs/*-progress.md` ledger ("Ruling: ... - cost if wrong: ...").
6. Backup on request: `deploy.py backup` (copies the INSTALLED files, user configs included).

## Escalation to bc-architect (opus, expensive: one call per problem)
- DESIGN before implementing: a new module, a change to the core lifecycle (Start/Stop, timers,
  hit handler), a new vanilla hook, or a feature resting on unconfirmed API. Not for config,
  text or simple fixes - spec those yourself.
- RESCUE: bc-implementer returned STUCK; bc-auditor FAILed twice on the same problem or said
  `ESCALATE`; a bug survived 2 in-game test cycles; a CTD with no clear cause.
- Send a dossier, not the history: goal, agreed behavior, what failed, attempts, check.py output,
  `stbc.RPT` tail, the user's in-game observation, files:lines, `git log -3 --oneline`.
- Results: FIXED -> bc-auditor, then install as usual. SPEC -> bc-implementer with the spec path.
  NEEDS USER / UNRESOLVED -> bring the question or the next experiment to the user.
  Never escalate the same problem twice; learned candidates enter `learned.md` only after the
  user confirms them in game.

## Conventions
Config: percentages 0-100, switches 1/0, `Interval` in seconds, `Def = -1` = module default.
Debug output only via `App.CPyDebug().Print` when `Debug = 1` (user dislikes the console: prefer
visible in-game checks). Commit only when the user asks.
