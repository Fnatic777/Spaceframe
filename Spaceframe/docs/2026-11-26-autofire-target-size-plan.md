# AutoFire Target Size Limit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Estender o limite de tempo de voo do Auto Fire contra alvos grandes ou pouco manobraveis, sem nunca ficar mais rigido que hoje.

**Architecture:** O calculo fica num modulo irmao novo, `TargetSize.py` (mesmo padrao do `WarpHold.py`: configuracoes vivem no `AutoFire.py`, lidas via `AF()`). `FlightBlocked` so o consulta quando o tiro seria bloqueado pelo limite atual.

**Tech Stack:** Python 1.5.2 (jogo); testes mock em Python 3.

**Spec:** `Spaceframe/docs/2026-11-26-autofire-target-size-spec.md`

## Global Constraints

- Regras de Python 1.5.2 do `CLAUDE.md` em `*/scripts/**`; CRLF, ASCII, tabs. `tools/lint15.py` decide.
- `T = raiz(2 * (TargetSizeAllowance / 100) * raio / aceleracao)`;
  `limite = max(limite_atual, min(T, TargetSizeFlightTimeMax)) + guiagem`, nunca acima da vida do projetil.
- Padroes no `Config.py`: `TargetSizeAllowance = 100`, `TargetSizeFlightTimeMax = 5.0`. Ausentes = desligado.
- Inalterados: percentual do arco, spread, retencao em warp, phasers, Rule 1, limite 0.
- Comentarios em ingles. Config do repo mantem `Debug = 0`. Sem README nesta etapa.
- Commit somente quando o usuario pedir (substitui os passos de commit do modelo).
- Base antes das mudancas: lint15 0 erros, 32/32 arquivos de teste.

## Review Focus

- Alvo cujo leitor de motor ou raio falha: limite atual, sem erro no ciclo (Task 1).
- Alvo sem motor mas com raio ilegivel ou <= 0: limite atual, nao o teto (Task 1).
- Teto menor que o limite atual (ex.: `TargetSizeFlightTimeMax = 1.0`): limite atual (Task 1).
- Folga negativa: desligado, sem erro de raiz (Task 1).
- Limite secundario 0 com o principal ligado: secundario continua sem filtro (Task 2).

---

### Task 1: TargetSize.py e leitura dos ajustes

**Files:**
- Create: `Spaceframe/scripts/Custom/Spaceframe/Modules/AutoFire/TargetSize.py`
- Modify: `Spaceframe/scripts/Custom/Spaceframe/Modules/AutoFire/AutoFire.py` (globais perto da linha 99; `LoadConfig`, linha 127)
- Modify: `Spaceframe/tests/test_autofire_base.py:45` (carregar o modulo novo como o `WarpHold`)
- Test: `Spaceframe/tests/test_target_size.py` (novo, mesmo formato de execucao do `test_flight_time.py`)

**Interfaces:**
- Produces: `AutoFire.g_fSizeAllowance` (percentual, 0.0 padrao), `AutoFire.g_fSizeFtMax` (segundos, 0.0 padrao).
- Produces: `TargetSize.Extend(pTarget, fBase)` -> `(fLimit, fRadius, fAccel)`.
  `fLimit >= fBase` sempre. `fRadius` (unidades do jogo) e `None` quando desligado ou ilegivel;
  `fAccel` e `None` quando o alvo nao tem subsistema de impulso. Nunca levanta excecao:
  em erro devolve `(fBase, None, None)`.

- [ ] **Step 1: Escrever os testes que falham**

```python
KM = 1.0 / 0.175

def engines(target, fAccel):
	# fAccel None = no impulse subsystem
	class E:
		def GetCurMaxAccel(self):
			return fAccel
	pEngines = None
	if fAccel is not None:
		pEngines = E()
	target.GetImpulseEngineSubsystem = lambda: pEngines

def make(fKm, fAccel, **kw):
	dCfg = {"TargetSizeAllowance": 100, "TargetSizeFlightTimeMax": 5.0}
	dCfg.update(kw)
	App, AF, core, ship = base.setup(**dCfg)
	target = mock_app.Ship("Bug", 7)
	target.radius = fKm * KM
	engines(target, fAccel)
	return AF, AF.GetTargetSize(), target

def limit(fKm, fAccel, fBase, **kw):
	AF, TS, target = make(fKm, fAccel, **kw)
	return TS.Extend(target, fBase)[0]

def near(a, b):
	return abs(a - b) < 0.001

def test_config_read_and_default_off():
	AF, TS, target = make(2.5, 1.75)
	assert AF.g_fSizeAllowance == 100.0 and AF.g_fSizeFtMax == 5.0
	App, AF, core, ship = base.setup()
	assert AF.g_fSizeAllowance == 0.0 and AF.g_fSizeFtMax == 0.0
	assert AF.GetTargetSize().Extend(target, 1.5) == (1.5, None, None)

def test_spec_examples():
	assert limit(0.11, 6.0, 1.5) == 1.5
	assert limit(0.11, 6.0, 1.0) == 1.0
	assert limit(0.3, 2.5, 1.5) == 1.5
	assert near(limit(0.3, 2.5, 1.0), 1.1711)
	assert near(limit(0.65, 1.75, 1.5), 2.0603)
	assert near(limit(2.5, 1.75, 1.5), 4.0406)

def test_allowance_scales_the_time():
	assert near(limit(0.65, 1.75, 1.5, TargetSizeAllowance=200), 2.9137)

def test_no_engines_or_no_accel_gets_the_cap():
	for fAccel in (None, 0.0, 0.005):
		assert limit(0.3, fAccel, 1.5) == 5.0

def test_cap_applies():
	assert limit(2.5, 0.875, 1.5) == 5.0

def test_cap_below_base_keeps_base():
	assert limit(2.5, 1.75, 1.5, TargetSizeFlightTimeMax=1.0) == 1.5

def test_zero_or_negative_settings_are_off():
	assert limit(2.5, 1.75, 1.5, TargetSizeAllowance=0) == 1.5
	assert limit(2.5, 1.75, 1.5, TargetSizeAllowance=-50) == 1.5
	assert limit(2.5, None, 1.5, TargetSizeFlightTimeMax=0) == 1.5

def test_bad_radius_keeps_base_even_without_engines():
	for fKm in (0.0, -1.0):
		assert limit(fKm, None, 1.5) == 1.5

def test_read_errors_keep_base():
	AF, TS, target = make(2.5, 1.75)
	def boom():
		raise RuntimeError("x")
	target.GetImpulseEngineSubsystem = boom
	assert TS.Extend(target, 1.5) == (1.5, None, None)
	engines(target, 1.75)
	target.GetRadius = boom
	assert TS.Extend(target, 1.5) == (1.5, None, None)

def test_return_carries_radius_and_accel():
	AF, TS, target = make(2.5, 1.75)
	tSize = TS.Extend(target, 1.5)
	assert near(tSize[1], 2.5 * KM) and tSize[2] == 1.75
	engines(target, None)
	assert TS.Extend(target, 1.5)[2] is None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python tools/check.py Spaceframe --only target_size`
Expected: FAIL (`GetTargetSize` / `TargetSize.py` inexistente)

- [ ] **Step 3: Implementar**

`TargetSize.py`: cabecalho no estilo do `WarpHold.py`, `AF()`, constante `MIN_ACCEL = 0.01`,
`Extend` conforme a interface (`pTarget.GetRadius()`, `pTarget.GetImpulseEngineSubsystem()`,
`GetCurMaxAccel()`, `math.sqrt`). No `AutoFire.py`: `GetTargetSize()` ao lado de `GetWarpHold()`;
em `LoadConfig`, `getattr(pConfig, "TargetSizeAllowance", 0)` e
`getattr(pConfig, "TargetSizeFlightTimeMax", 0)`, ambos como float e declarados em `global`.

- [ ] **Step 4: Rodar e ver passar**

Run: `python tools/check.py Spaceframe --only target_size`
Expected: lint15 0 errors; 1/1 arquivo passou

### Task 2: Ligar ao filtro de voo, log e Config.py

**Files:**
- Modify: `AutoFire.py` (`FlightBlocked` 1289, `LogFlightBlock` 1331, chamada em `ArcScore` 1512)
- Modify: `Spaceframe/scripts/Custom/Spaceframe/Modules/AutoFire/Config.py` (depois de `PulseFlightTimeLimitSecondary`)
- Test: `Spaceframe/tests/test_target_size.py`

**Interfaces:**
- Consumes: `GetTargetSize().Extend(pTarget, fBase)` da Task 1.
- Produces: `FlightBlocked(..., bSpread=0, fDepth=None, pTarget=None)`;
  `LogFlightBlock(sKind, bSecondary, fEstimate, fLimit, fDistance, iTarget, bBypass=0, fDepth=None, tSize=None, fLong=0.0)`,
  `bBypass`: 0 bloqueado, 1 passou como spread, 2 passou pelo tamanho (chave de frequencia propria).

- [ ] **Step 1: Escrever os testes que falham**

```python
import test_flight_time as FT
import test_torpedo_arc as TT

SIZE = {"TargetSizeAllowance": 100, "TargetSizeFlightTimeMax": 5.0}

def setup_torp(fKm, fAccel, **kw):
	dCfg = dict(SIZE)
	dCfg.update(kw)
	App, AF, core, ship, target, torps, S = FT.torp(**dCfg)
	target.radius = fKm * KM
	engines(target, fAccel)
	return App, AF, core, ship, target, torps

def blocked(AF, target, fSeconds, bSec=0, fLifetime=0.0):
	# speed 100, guidance 0.1 s
	return AF.FlightBlocked("torpedo", bSec, fSeconds * 100.0, 100.0, 7, 0.1, fLifetime, 0, None, target)

def test_extended_limit_adds_guidance():
	App, AF, core, ship, target, torps = setup_torp(0.65, 1.75, TorpedoFlightTimeLimit=1.5)
	assert blocked(AF, target, 2.15) == 0
	assert blocked(AF, target, 2.18) == 1
	assert AF.FlightBlocked("torpedo", 0, 215.0, 100.0, 7, 0.1, 0.0) == 1	# no target

def test_lifetime_still_caps():
	App, AF, core, ship, target, torps = setup_torp(2.5, 1.75, TorpedoFlightTimeLimit=1.5)
	assert blocked(AF, target, 3.5, 0, 3.0) == 1
	assert blocked(AF, target, 2.9, 0, 3.0) == 0

def test_secondary_uses_its_own_base_and_off_stays_off():
	App, AF, core, ship, target, torps = setup_torp(0.3, 2.5, TorpedoFlightTimeLimit=1.5,
		TorpedoFlightTimeLimitSecondary=1.0)
	assert blocked(AF, target, 1.25, 1) == 0 and blocked(AF, target, 1.30, 1) == 1
	App, AF, core, ship, target, torps = setup_torp(0.11, 6.0, TorpedoFlightTimeLimit=1.5,
		TorpedoFlightTimeLimitSecondary=0)
	assert blocked(AF, target, 9.0, 1) == 0

def test_rule_1_stays_unfiltered():
	App, AF, core, ship, target, torps = setup_torp(0.11, 6.0, TorpedoRule=1, TorpedoFlightTimeLimit=1.5)
	assert blocked(AF, target, 9.0) == 0

def test_score_main_and_secondary_follow_the_target():
	App, AF, core, ship, target, torps = setup_torp(2.5, 1.75, TorpedoFlightTimeLimit=1.5,
		TorpedoFlightTimeLimitSecondary=1.0)
	TT.place(target, 0.1, 50.0)	# 2.86 s: past the spread window
	assert FT.tscore(AF, ship, torps, target) > 0.0
	assert FT.tscore(AF, ship, torps, target, 1) > 0.0
	target.radius = 0.11 * KM
	engines(target, 6.0)
	assert FT.tscore(AF, ship, torps, target) == 0.0
	assert FT.tscore(AF, ship, torps, target, 1) == 0.0

def test_pulse_follows_the_target():
	dCfg = dict(SIZE)
	dCfg["PulseFlightTimeLimit"] = 1.5
	App, AF, core, ship, target, pul, S = FT.pulse(**dCfg)
	target.radius = 2.5 * KM
	engines(target, 1.75)
	FT.TP.place(target, 0.1, 80.0)	# 3.05 s at speed 150
	assert FT.pscore(AF, ship, pul, target) > 0.0
	engines(target, 20.0)
	assert FT.pscore(AF, ship, pul, target) == 0.0

def log_lines(fKm, fAccel, fBase):
	App, AF, core, ship, target, torps = setup_torp(fKm, fAccel, TorpedoFlightTimeLimit=fBase)
	AF.g_bDebug = 1
	App.g_kUtopiaModule.GetGameTime = lambda: 10.0
	TT.place(target, 0.1, 20.0)
	FT.tscore(AF, ship, torps, target)
	FT.tscore(AF, ship, torps, target)
	return [l[1] for l in core.logs if l[1].find("Flight time filter") >= 0]

HEAD = "Flight time filter: torpedo main est 1.1 s > limit "

def test_log_passed_by_size_once():
	assert log_lines(2.5, 1.75, 1.0) == [HEAD + "1.0 s at 20 km, passed by target size (limit 4.0 s, radius 2.50 km, accel 1.75)"]

def test_log_blocked_shows_extended_limit():
	assert log_lines(0.2, 2.5, 0.5) == [HEAD + "1.0 s at 20 km, target radius 0.20 km accel 2.50"]

def test_log_blocked_without_extension():
	assert log_lines(0.11, 6.0, 1.0) == [HEAD + "1.0 s at 20 km, target radius 0.11 km accel 6.00"]

def test_log_no_engines():
	assert log_lines(2.5, None, 1.0)[0].endswith("passed by target size (limit 5.0 s, radius 2.50 km, accel none)")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python tools/check.py Spaceframe --only target_size`
Expected: FAIL (`FlightBlocked` nao aceita o alvo)

- [ ] **Step 3: Implementar**

Em `FlightBlocked`: guardar o limite configurado antes de somar a guiagem; manter a ordem atual
(dentro do limite -> 0; spread -> 0); so entao, com `pTarget != None`, chamar `Extend` dentro de
`try`. Se estender, aplicar guiagem e teto de vida ao novo valor: estimativa dentro dele -> log
`bBypass 2` e 0; fora -> log bloqueado com o limite estendido e 1. Sem raio lido (`tSize[1]`
None), a linha de log fica identica a de hoje. `ArcScore` passa `pTarget`.
No `Config.py`, os dois ajustes com comentario em ingles (formula, 0 = off, nunca abaixo do limite).

- [ ] **Step 4: Rodar o gate completo**

Run: `python tools/check.py`
Expected: lint15 0 errors; todos os arquivos de teste passam (Spaceframe: 33/33)

### Task 3: Revisao, instalacao e teste em jogo

**Files:**
- Modify: `Spaceframe/docs/autofire-progress.md`

- [ ] **Step 1:** Revisao do diff pelo `bc-auditor`. Expected: PASS
- [ ] **Step 2:** `python tools/deploy.py status Spaceframe`, depois `python tools/deploy.py install Spaceframe`.
  Se houver `edited`: `pull`, mesclar, instalar (nunca `--force`). Debug do jogo permanece como esta.
- [ ] **Step 3:** Registrar a linha "Ruling: ... - cost if wrong: ..." no ledger.
- [ ] **Step 4:** Pedir o teste em jogo (reiniciar o jogo): alvo grande/lento a 2-5 s, fighters, e um
  alvo com motor danificado. Depois `python tools/gamelog.py show --grep "Flight time filter"`
  para conferir raio e aceleracao. Fatos confirmados vao para `docs/api/learned.md`.
