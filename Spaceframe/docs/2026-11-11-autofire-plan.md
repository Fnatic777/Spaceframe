# Auto Fire - Plano de implementacao

> Para quem executar: use superpowers:subagent-driven-development (recomendado)
> ou superpowers:executing-plans, tarefa por tarefa. Passos com `- [ ]`.
> Siga tambem a skill do projeto `spaceframe-bc-mod-dev` (Python 1.5, CRLF,
> instalacao segura, testes, backup).

**Objetivo:** modulo AutoFire do Spaceframe que dispara phasers, torpedos e
armas de pulso da nave do jogador por regras de solucao de tiro, ligado por
tecla L e por botao no menu tatico.

**Arquitetura:** `Solution.py` calcula a nota de tiro (0-100) sem interface;
`AutoFire.py` liga/desliga, roda um timer proprio so quando ligado e dispara
por grupo com `StartFiring`/`StopFiring`, como o disparo manual do jogo. O
Status HUD mostra o estado lendo o modulo pelo nucleo.

**Tecnologia:** Python 1.5.2 do jogo (API `App`), testes em Python 3 com mocks.

**Especificacao:** `Spaceframe Docs\2026-11-11-autofire-design.md`

## Restricoes globais

- Python 1.5.2: sem `+=`, comprehensions, lambda, kwargs, True/False,
  metodos de string, `in` em dict, `continue` dentro de `try`; `global` no topo.
- Arquivos CRLF, so ASCII; comentarios em ingles; README em EN/ES/PT.
- Config: porcentagens de 0 a 100, liga/desliga 1 ou 0, `FireInterval` em segundos.
- Padroes de config: ToggleKey "L", StartEnabled 0, FireInterval 0.1,
  TargetMode 0, PhaserRange 100, PhaserMinCharge 50, TorpedoMinSolution 70,
  SpreadMinSolution 85, PulseMinSolution 70, TorpedoReserve 0.
- So a nave do jogador; multiplayer desligado (regra do nucleo).
- O Auto Fire nunca muda o nivel de alerta.
- Disparo manual tem prioridade por grupo.

## Arquivos

| Arquivo | Responsabilidade |
|---|---|
| `scripts\Custom\Spaceframe\Modules\AutoFire\__init__.py` | Pacote |
| `...\AutoFire\Config.py` | Configuracoes (tabela acima) |
| `...\AutoFire\Solution.py` | Nota de solucao de tiro, sem interface |
| `...\AutoFire\AutoFire.py` | Estado, tecla, botao, timer, ciclo de disparo |
| `...\Modules\StatusHUD\StatusHUD.py` | Mostrar "AUTO FIRE" (modificar) |
| `scripts\Custom\Spaceframe\Ships.py` | `"AutoFire": Def` nas naves (usuario decide quais) |
| `scripts\Custom\Spaceframe\Config.py` | `"AutoFire": 1` em Modules |
| `Spaceframe - README.txt` | Secao do modulo (EN/ES/PT) |
| `Spaceframe Dev\tests\` (no PC) | Mocks e testes Python 3, guardados no PC para nao se perderem |

"Commit" neste projeto = instalar no PC (mtime guard, `cmp` depois) e o
usuario testar no jogo. Nao ha git.

## Foco de revisao

Situacoes que a especificacao implica mas que nenhum teste de tarefa cobriria
sozinho; cada uma tem teste na tarefa dona:

1. Alvo destruido no meio do ciclo: todas as armas param na hora (Tarefa 2).
2. Nave sem grupo de torpedos ou de pulso (`GetWeaponSystemGroup` devolve
   None): o ciclo segue com os outros grupos sem erro (Tarefa 2).
3. Tecla L numa nave sem a tecnologia: nada muda, nenhuma arma dispara
   (Tarefa 1).
4. Reiniciar a batalha com o Auto Fire ligado: nao duplica o botao nem a
   tecla, comeca desligado, spread do jogador restaurado (Tarefas 1 e 4).
5. Jogador troca de nave ou morre com o Auto Fire ligado: o timer para e nao
   dispara pela nave antiga (Tarefa 1).

---

### Tarefa 1: Base - estado, tecla L, botao, aviso no HUD

**Arquivos:** criar `AutoFire\__init__.py`, `Config.py`, `AutoFire.py`;
modificar `StatusHUD.py`, `Config.py` do nucleo; testes
`Spaceframe Dev\tests\test_autofire_base.py` e mocks `tests\mock_app.py`.

**Interfaces produzidas:**
- `AutoFire.Start(pCore)`, `AutoFire.Stop()`, `AutoFire.Tick(lShips)` (contrato do nucleo).
- `AutoFire.IsEnabled() -> int` (1 se ligado e a nave do jogador tem a tecnologia).
- `AutoFire.SetEnabled(iOn)` e `AutoFire.Toggle()`.
- `AutoFire.OnToggleKey(pObject, pEvent)` e `AutoFire.OnMenuButton(pObject, pEvent)` (handlers).
- `AutoFire.g_dManual` = `{WG_PRIMARY: 0, WG_SECONDARY: 0, WG_TERTIARY: 0}`, atualizado por
  handlers de `App.ET_INPUT_FIRE_PRIMARY/SECONDARY/TERTIARY` (`pEvent.GetBool()`).
- `AutoFire.Probe()` (so com Debug = 1): registra no console se `CanHit`,
  `IsInArc`, `CanHitTarget`, `Fire`, `SetFiringChainMode`, `GetPredictedPosition`
  existem nas armas da nave do jogador.

Decisoes fixas:
- Tecla: `App.g_kKeyboardBinding.BindKey(108, App.TGKeyboardEvent.KS_KEYDOWN,
  eToggle, App.KeyboardBinding.GET_EVENT, 0.0)` com `eToggle = App.Game_GetNextEventType()`
  criado uma vez por sessao (guardado no modulo); handler por
  `App.g_kEventManager.AddBroadcastPythonFuncHandler(eToggle, pMission, ...)`.
  `ToggleKey` convertido para o codigo ASCII minusculo.
- Botao: `BridgeUtils.CreateBridgeMenuButton(App.TGString("Auto Fire"), eButton, 0,
  pTacticalMenu)` com `pTacticalMenu = App.TacticalControlWindow_GetTacticalControlWindow().GetTacticalMenu()`;
  `SetChosen` reflete o estado; se `TGString` falhar, `App.STButton_Create` com texto simples.
  Na `Stop()` o botao e removido do menu.
- Estado comeca em `StartEnabled`; `IsEnabled()` volta 0 se a nave do jogador
  mudou ou nao tem a tecnologia (`g_pCore.GetShipTech(pShip, "AutoFire")`).
- StatusHUD: se `g_pCore.GetModule("AutoFire")` existe e `IsEnabled()`, mostra
  "AUTO FIRE" no painel do jogador, a esquerda da linha de status, sem mudar a
  altura do painel; redesenho so na mudanca de estado (mesma regra do `Redraw`).

- [ ] **Passo 1: Escrever os testes que falham** em `test_autofire_base.py`:
  - `test_starts_disabled`: apos `Start`, `IsEnabled() == 0`.
  - `test_toggle_on_off`: nave com tecnologia; `Toggle()` -> 1; `Toggle()` -> 0.
  - `test_toggle_without_tech`: nave sem `"AutoFire"` no Ships; `Toggle()` -> `IsEnabled() == 0`.
  - `test_player_ship_changed`: ligado; mock troca a nave do jogador -> `IsEnabled() == 0`.
  - `test_restart_no_duplicates`: `Start`, `Stop`, `Start` -> uma so ligacao de tecla e um so botao no menu mock; estado 0.
  - `test_manual_flags`: evento mock `ET_INPUT_FIRE_SECONDARY` com bool 1 -> `g_dManual[WG_SECONDARY] == 1`; com 0 -> 0.
  - `test_hud_label`: ligado -> texto "AUTO FIRE" visivel no painel mock; desligado -> escondido; altura do painel igual nos dois casos.
- [ ] **Passo 2: Rodar e ver falhar** - `python3 -B tests/test_autofire_base.py` -> erros de modulo ausente.
- [ ] **Passo 3: Implementar** `Config.py`, `AutoFire.py` (estado, tecla, botao, handlers, `Probe`) e a mudanca no `StatusHUD.py`.
- [ ] **Passo 4: Rodar os testes** -> todos passam; varredura Python 1.5 e pyflakes limpos.
- [ ] **Passo 5: Instalar e testar no jogo** - usuario: L liga/desliga, botao aparece e acompanha, "AUTO FIRE" aparece; com Debug = 1, mandar print do resultado do `Probe`. Ajustar as tarefas seguintes se alguma funcao nao existir.

### Tarefa 2: Ciclo de disparo e phasers

**Arquivos:** modificar `AutoFire.py`; teste `test_autofire_phasers.py`.

**Interfaces:**
- Consome: `IsEnabled`, `g_dManual` (Tarefa 1).
- Produz: `AutoFire.GetTarget(pShip) -> ShipClass ou None` (modo 0 nesta tarefa:
  `App.ShipClass_Cast(pShip.GetTarget())`, vivo); `AutoFire.FireCycle()`;
  `AutoFire.PhaserReady(pBank, pTarget) -> int`;
  `AutoFire.FireGroup(pShip, eGroup, pTarget, bFire)` (StartFiring com
  `pShip.GetTargetOffsetTG()` + `SetForceUpdate(1)`, ou StopFiring;
  guarda em `g_dFiring[eGroup]` o que o modulo mandou disparar).
- Timer proprio: `App.PythonMethodProcess` com `FireInterval`, criado ao ligar e
  destruido ao desligar (mesma forma do `Runner` do nucleo).
- Pre-condicoes do ciclo: nave viva, nao camuflada, alerta vermelho
  (`pShip.GetAlertLevel() == App.ShipClass.RED_ALERT`), alvo valido; senao para
  tudo que o modulo disparou.
- Phaser pronto: `pBank.CanHit(pTarget)` e distancia <=
  `pBank.GetMaxDamageDistance() * PhaserRange / 100` e
  `pBank.GetChargePercentage() >= PhaserMinCharge / 100`. Grupo dispara se algum banco estiver pronto.

- [ ] **Passo 1: Testes que falham** em `test_autofire_phasers.py`:
  - `test_phaser_fires_in_range`: alvo a 0,8 x distancia maxima, carga 0,6, CanHit 1 -> `StartFiring` chamado no grupo primario.
  - `test_phaser_out_of_range`: 1,2 x distancia maxima -> `StopFiring`.
  - `test_phaser_low_charge`: carga 0,4 -> nao dispara.
  - `test_manual_priority`: `g_dManual[WG_PRIMARY] = 1` -> nem Start nem Stop no grupo primario.
  - `test_cloaked`: nave camuflada -> nada dispara.
  - `test_not_red_alert`: alerta amarelo -> nada dispara; grupos que o modulo disparava recebem `StopFiring`.
  - `test_target_destroyed`: alvo morre entre ciclos -> `StopFiring` em todos os grupos disparados pelo modulo.
  - `test_missing_group`: `GetWeaponSystemGroup(WG_SECONDARY)` None -> ciclo continua sem erro, primario dispara.
  - `test_disable_stops_all`: desligar -> `StopFiring` em tudo que o modulo disparou; timer destruido.
- [ ] **Passo 2: Rodar e ver falhar.**
- [ ] **Passo 3: Implementar** `GetTarget`, `FireCycle`, `PhaserReady`, `FireGroup`, timer.
- [ ] **Passo 4: Rodar** -> passam; varredura Python 1.5 limpa.
- [ ] **Passo 5: Instalar e testar no jogo** - phasers disparam sozinhos dentro do alcance, param fora; segurar a tecla de phaser assume o controle; mandar print.

### Tarefa 3: Nota de solucao de tiro e torpedos

**Arquivos:** criar `Solution.py`; modificar `AutoFire.py`; teste `test_solution.py`, `test_autofire_torps.py`.

**Interfaces produzidas (Solution.py):**
- `Solution.GetProjectileInfo(pWeapon, pSystem) -> (fSpeed, fGuidance, fTurn, fLifetime)`:
  torpedo pelo script da municao atual (`pSystem.GetCurrentAmmoType().GetTorpedoScript()`,
  funcoes `GetLaunchSpeed`, `GetGuidanceLifetime`, `GetMaxAngularAccel`, `GetLifetime`
  se existir, senao vida sem limite); pulso por `pWeapon.GetLaunchSpeed()`, orientacao 0.
- `Solution.Score(pShip, pTarget, vOffset, pWeapon, vDirection, tInfo) -> float` (0 a 100).
- `Solution.PredictPosition(pTarget, vOffset, fTime) -> TGPoint3` (usa
  `GetPredictedPosition`; sem ela, posicao atual).

Algoritmo da nota (passos 1-8 da especificacao, secao 7), com estas escolhas:
- erro esperado = `sqrt(max(0, desvio - correcao)^2 + manobra^2)`;
- correcao = `fSpeed * 0.5 * fTurn * min(fGuidance, t)^2`, limitada a `distancia * 0.5`;
- manobra usa a aceleracao maxima dos motores de impulso do alvo
  (`GetImpulseEngineSubsystem().GetProperty().GetMaxAccel()`); sem ela, 0;
- raio do alvo = `pTarget.GetRadius()`; com subsistema escolhido, raio do subsistema se existir.

**Torpedos em AutoFire.py:**
- `AutoFire.BestTorpedoScore(pShip, pSystem, pTarget) -> float`: maior nota
  entre tubos com `IsTubeReady`/`GetNumReady() > 0` e `IsInArc`.
- Dispara se nota >= TorpedoMinSolution e municao da municao atual > TorpedoReserve.

- [ ] **Passo 1: Testes que falham:**
  - `test_score_aligned_still`: alvo parado a 10 km, tubo apontado, raio 1 -> nota >= 95.
  - `test_score_out_of_arc`: `IsInArc` 0 -> 0.
  - `test_score_far_maneuvering`: 30 km, aceleracao alta -> nota < 70.
  - `test_score_guidance_helps`: mesmo cenario com 8 graus de erro: orientacao 3 s > orientacao 0.
  - `test_score_beyond_lifetime`: tempo de voo > vida -> 0.
  - `test_score_no_prediction`: sem `GetPredictedPosition` -> usa posicao atual, sem erro.
  - `test_torps_fire_above_min` / `test_torps_hold_below_min`: notas 75 e 65 com minimo 70.
  - `test_torps_reserve`: municao 3, reserva 3 -> nao dispara.
- [ ] **Passo 2: Rodar e ver falhar.**
- [ ] **Passo 3: Implementar** `Solution.py` e a parte de torpedos.
- [ ] **Passo 4: Rodar** -> passam; varredura limpa.
- [ ] **Passo 5: Instalar e calibrar no jogo** - com Debug = 1, cada disparo registra a nota; usuario relata acertos/erros; ajustar as constantes da correcao/manobra se as notas nao acompanharem os acertos. Verificar se tubos mal alinhados disparam junto (se sim, trocar para `TorpedoTube.Fire` por tubo nesta tarefa).

### Tarefa 4: Spread automatico

**Arquivos:** modificar `AutoFire.py`; teste `test_autofire_spread.py`.

**Interfaces:**
- Consome: `BestTorpedoScore` (Tarefa 3).
- Produz: `AutoFire.SetSpread(pSystem, iMode)`; `g_iPlayerSpread` (modo do jogador
  guardado ao ligar, via `GetFiringChainMode()`, restaurado ao desligar, ao segurar a
  tecla manual de torpedo e no `Stop`).
- Maior spread = `GetNumFiringChains() - 1`; Single = 0.

- [ ] **Passo 1: Testes que falham:**
  - `test_spread_high_score`: nota 90, 3 cadeias -> modo 2.
  - `test_single_mid_score`: nota 75 -> modo 0.
  - `test_spread_only_single`: 1 cadeia -> sempre 0.
  - `test_restore_on_disable`: jogador tinha modo 1; liga, spread vira 2; desliga -> 1.
  - `test_restore_on_manual`: tecla de torpedo segurada -> modo do jogador.
  - `test_restore_on_restart`: `Stop` com spread alterado -> modo do jogador.
- [ ] **Passo 2: Rodar e ver falhar.**
- [ ] **Passo 3: Implementar.**
- [ ] **Passo 4: Rodar** -> passam.
- [ ] **Passo 5: Instalar e testar no jogo** - spread troca sozinho de perto/longe; conferir se o texto "Spread" do painel acompanha (anotar se nao).

### Tarefa 5: Armas de pulso

**Arquivos:** modificar `AutoFire.py`; teste `test_autofire_pulse.py`.

**Interfaces:** consome `Solution.Score` com `GetProjectileInfo` de pulso (orientacao 0).
`AutoFire.BestPulseScore(pShip, pSystem, pTarget) -> float`: maior nota entre armas
com `IsInArc` e carga >= `GetMinFiringCharge()`.

- [ ] **Passo 1: Testes que falham:** `test_pulse_fires_above_min`, `test_pulse_hold_below_min`,
  `test_pulse_no_charge` (carga abaixo do minimo da arma -> nao dispara), `test_pulse_manual_priority`.
- [ ] **Passo 2: Rodar e ver falhar.**
- [ ] **Passo 3: Implementar.**
- [ ] **Passo 4: Rodar** -> passam.
- [ ] **Passo 5: Instalar e testar no jogo** com nave de disruptores.

### Tarefa 6: Modos de alvo 1 e 2

**Arquivos:** modificar `AutoFire.py`; teste `test_autofire_targets.py`.

**Interfaces:**
- `AutoFire.GetEnemies(pShip) -> lista`: inimigos da missao
  (`MissionLib.GetEnemyGroup()`), vivos, dentro do maior alcance das armas da nave.
- Modo 1: `GetTarget` devolve o alvo do jogador; sem ele, o inimigo mais proximo.
- Modo 2: para cada grupo, o inimigo com melhor nota (phasers: o mais proximo
  dentro do alcance); `StartFiring` com esse alvo e deslocamento zero.

- [ ] **Passo 1: Testes que falham:** `test_mode0_no_target_no_fire`, `test_mode1_nearest_enemy`,
  `test_mode1_ignores_friendly`, `test_mode2_best_per_group`, `test_mode2_out_of_range_ignored`.
- [ ] **Passo 2: Rodar e ver falhar.**
- [ ] **Passo 3: Implementar.**
- [ ] **Passo 4: Rodar** -> passam.
- [ ] **Passo 5: Instalar e testar no jogo** com varios inimigos.

### Tarefa 7: Documentacao e backup

- [ ] **Passo 1:** secao "Auto Fire module" no README (EN/ES/PT): o que faz, tecla e
  botao, regras por arma, opcoes com padroes; versao do modulo no topo.
- [ ] **Passo 2:** `"AutoFire": 1` no `Config.py` do nucleo (se ainda nao) e conferir o
  `Ships.py` com o usuario (quais naves recebem a tecnologia).
- [ ] **Passo 3:** instalar, conferir com `cmp`.
- [ ] **Passo 4:** backup completo (skill do projeto) com data.
