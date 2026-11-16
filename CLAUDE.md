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
- `python tools/build_api_index.py` - regenerate `docs/api/App-index.txt`.

## Workflow (main agent = coordinator, keep your context small)
1. Lookups (API names, vanilla usage, ship file names) -> `bc-scout`. Check
   `docs/api/learned.md` / `App-index.txt` with Grep first if it is a one-liner.
2. Code -> `bc-implementer` with a precise spec (files, behavior, config names, tests).
   Trivial config/text edits: do them yourself, then run `check.py`.
3. Every game-code change -> `bc-auditor` before install. Crash reports -> `bc-auditor` too.
4. `deploy.py install`, tell the user whether to restart the game (`.py` code: restart;
   `Ships.py`/`Config.py`: next Quick Battle). Then WAIT for the user's in-game test.
   Never say something works in game without the user confirming it; say what was only simulated.
5. Confirmed engine facts -> one line in `docs/api/learned.md`. Design decisions for a feature ->
   that mod's `docs/*-progress.md` ledger ("Ruling: ... - cost if wrong: ...").
6. Backup on request: `deploy.py backup` (copies the INSTALLED files, user configs included).

## Conventions
Config: percentages 0-100, switches 1/0, `Interval` in seconds, `Def = -1` = module default.
Debug output only via `App.CPyDebug().Print` when `Debug = 1` (user dislikes the console: prefer
visible in-game checks). Commit only when the user asks.
