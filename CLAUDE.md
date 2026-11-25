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
- `python tools/check.py [--only PATTERN]` - lint15 + all mock tests in parallel (~4 s), always
  ends with two summary lines (no `| tail`). `--only` is for the inner loop; the full run must be
  green before any install.
- `python tools/deploy.py status|install|pull|backup [Mod]` - install refuses to overwrite files
  the user edited in the game (often `Ships.py`, `Config.py`): `pull`, merge, then install.
  `edited` is real (game copy matches neither the last install nor HEAD): never `--force`
  without diffing the game copy first and telling the user.
- `python tools/deploy.py debug [0|1|2]` - show/set `Debug` in the GAME copy of Config.py only.
  The Debug line is ignored by status/edited, install keeps the game's level, the repo stays 0.
- `python tools/gamelog.py [summary | show --module M --grep RE --from T --to T | sessions | rotate]`
  - the game log, last session by default, repeats collapsed. Never cat/grep the raw
  `Spaceframe_debug.log` (MBs): start with `summary`, then narrow with `show`.
- `python tools/vanilla_calls.py REGEX [--files] [--max N]` - every call in the game's .pyc
  (cached dis15 output, ~0.6 s). Use it before running dis15 on a directory.
- `python tools/build_api_index.py` - regenerate `docs/api/App-index.txt`.
- `python tools/dbwin_capture.py [--match TEXT] [--out PATH]` - captures only the engine's own
  TGTrace/OutputDebugString output into logs/stbc_debug.log. It does NOT capture the Python logs
  (`App.CPyDebug().Print` is a no-op in stbc.exe).
- Game log: with `Debug` >= 1 (`deploy.py debug 1`) and the `fileio` exe patch applied, the game
  writes `Spaceframe_debug.log` in the game folder. Ask the user to run the test, then read it
  with `gamelog.py` (never ask the user to copy banners).
- `python tools/dis15.py <file.pyc|dir> [--func Name] [--calls-only]` - disassemble game `.pyc`
  (Python 1.5); `--calls-only` prints `path:func:line: call` to grep real vanilla call patterns.
- `python tools/exe_probe.py <wrap|dis|xref|vt|vtof|str|names|field> ...` - read-only static probe of
  `stbc.exe` (capstone+pefile, SWIG wrappers name the functions). Facts: `docs/api/exe-weapons.md`.
  Exe work goes to `bc-reverser`. The exe is never overwritten without a hash-checked backup and
  the user's explicit OK; patches are for the user's install only, not committed binaries.
- `python tools/exe_patch.py status|verify|apply|revert|upgrade|selftest [--exe PATH] [--patch NAME]
  [--all]` - two independent engine patches: `onebank` (default; "one bank per target" for phaser
  systems, cave v2) and `fileio` (lets scripts use `open`, so the game log works; every script can
  then write files). `--patch NAME` picks one, `revert --all` undoes both, `status` lists both
  (hash-checked, backup `stbc.exe.orig-<sha8>`; `selftest` runs on temp copies only). It changes
  `stbc.exe` itself and every ship of the game: `apply`/`revert`/`upgrade` only with the user's
  explicit OK and the game closed.

## Workflow (main agent = coordinator)
Read what a decision needs (Grep with `-n`/context, `Read` with offset/limit; a whole module only when
the change depends on it). Wide searches go to `bc-scout`, engine questions to `bc-reverser`.
One session per feature: when a feature closes (or after ~2 compactions), write the state in the mod's
`docs/*-progress.md` and suggest a new session that starts from the ledger.
1. Lookups: one-liners (a name in `App-index.txt`, a fact in `learned.md`, a line in the repo)
   -> Grep yourself. Wide searches in the game install (vanilla/Bedrock usage of a call,
   ship label -> file name, several files to compare) -> `bc-scout`. Questions about what the
   engine itself does (stbc.exe functions, struct fields, patch feasibility) -> `bc-reverser`.
2. Code: a change inside one module whose code you have read -> do it yourself, then `check.py`.
   Multi-module features, core lifecycle changes or long mechanical edits -> `bc-implementer` with a
   precise spec (files, behavior, config names, tests) or the path of a `bc-architect` spec file.
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
  text or simple fixes - spec those yourself. A spec covers the next testable slice, not the whole
  feature; revise it after the in-game test.
- RESCUE: bc-implementer returned STUCK; bc-auditor FAILed twice on the same problem or said
  `ESCALATE`; a bug survived 2 in-game test cycles; a CTD with no clear cause.
- Send a dossier, not the history: goal, agreed behavior, what failed, attempts, check.py output,
  `stbc.RPT` tail, the user's in-game observation, files:lines, `git log -3 --oneline`.
- Results: FIXED -> bc-auditor, then install as usual. SPEC -> bc-implementer with the spec path.
  NEEDS USER / UNRESOLVED -> bring the question or the next experiment to the user.
  Do not re-escalate the same problem without new evidence (a new log, RPT or in-game observation);
  learned candidates enter `learned.md` only after the
  user confirms them in game.

## Conventions
Config: percentages 0-100, switches 1/0, `Interval` in seconds, `Def = -1` = module default.
Debug output only through the core `Log()` when `Debug` >= 1 (it writes `Spaceframe_debug.log`;
`App.CPyDebug().Print` prints nothing). Switch it with `deploy.py debug N`, never by editing
Config.py; the repo copy stays `Debug = 0`.
README (EN/ES/PT): while a feature is iterating, user-facing settings are documented in the
Config.py comments; the README gets one docs pass (all three languages) when the feature closes,
before its commit. Do not send README edits with every small change.
Large modules: keep a module file under ~1500 lines; split helpers into sibling files of the
module folder (like `AutoFire/Solution.py`) instead of growing one file.
Commit only when the user asks.
