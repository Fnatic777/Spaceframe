# Spaceframe - Modulo Auto Fire: especificacao de design

Data: 2026-11-11
Status: aguardando revisao
Base: Spaceframe v0.4 (MV Shields v0.6, Ablative Armor v1.5, Status HUD v0.11)

## 1. Objetivo

O "Target At Will" do oficial tatico e ineficiente: dispara devagar (sobretudo
torpedos) e manobra mal. O Auto Fire e uma tecnologia que, ligada, dispara as
armas da nave do jogador sozinha, com regras de tiro eficientes, deixando o
jogador livre para manobrar e posicionar a nave.

Criterios de sucesso:
- Os torpedos saem quando ha boa chance de acerto, sem a demora do oficial tatico.
- Os phasers disparam sempre que estao no alcance de dano total, com carga suficiente.
- O jogador continua no controle: escolhe o alvo, manobra, e pode disparar
  manualmente a qualquer momento.
- Custo desprezivel com o Auto Fire desligado.

Fora do escopo: manobrar a nave, escolher subsistemas sozinho (alem do que o
jogador escolheu), multiplayer.

## 2. O que a investigacao mostrou (base tecnica)

Fontes: scripts do jogo instalado e lista de funcoes do executavel original
levantada pelo projeto bc_dauntless.

- Disparo manual do jogo (TacticalInterfaceHandlers.FireWeapons): pega o grupo
  `pShip.GetWeaponSystemGroup(App.ShipClass.WG_PRIMARY | WG_SECONDARY |
  WG_TERTIARY)`, chama `StartFiring(alvo, pShip.GetTargetOffsetTG())` e
  `SetForceUpdate(1)`; ao soltar, `StopFiring()`. *Lido no bytecode do jogo.*
- Funcoes por arma no executavel original: PhaserBank `CanHit`,
  `GetMaxDamageDistance`, `GetChargePercentage`; TorpedoTube `CanHit`,
  `IsInArc`, `IsTubeReady`/`GetNumReady`, `Fire`; PulseWeapon `CanHitTarget`,
  `IsInArc`, `GetLaunchSpeed`, carga. *Lista de metodos do executavel
  (bc_dauntless); assinaturas nao confirmadas.*
- O "Target At Will" (AI/Preprocessors.py, FireScript) roda a cada 0,2 s mas
  avalia um sistema de armas por rodada, com duas rodadas extras (visibilidade e
  subsistema): cada sistema e avaliado ~1 vez por segundo. Para torpedos preve a
  posicao do alvo pelo tempo de voo (`GetPredictedPosition`) e so dispara se o
  alvo previsto estiver a menos de 10 (ou 50) graus de um tubo. *Lido no codigo.*
- O indicador de barras do reticulo e desenhado dentro do executavel; nao ha
  funcao de "lock" ou "chance de acerto" acessivel por script. *Lista de metodos.*
- Projeteis do Orion Delta: Photon1 velocidade 100, orientacao 0,1 s,
  curva 10; Disruptor1 velocidade 150, sem orientacao, vida 10 s. *Lido no
  bytecode.* Os torpedos sao quase "burros": a mira prevista decide o acerto.
- Spread = cadeia de disparo do sistema de torpedos
  (`TorpedoSystem.SetFiringChainMode`), definida na hardpoint de cada nave
  (Galaxy/Sovereign: Single, Dual, Quad). Segundo o bc_dauntless, no jogo
  original o spread nao abre em leque: lanca mais torpedos de uma vez no mesmo
  alvo. *Conclusao do bc_dauntless, nao verificada.*
- Dano do phaser cai com a distancia alem do alcance de dano maximo (medicao do
  bc_dauntless: em 30 km ~1/3 do dano a 10 km).
- Teclas: o `KeyboardBinding.py` e gerado pelo jogo. Letras livres: L, O, K.

## 3. Decisoes

| Tema | Decisao |
|---|---|
| Para quem | So a nave que o jogador controla, quando a tecnologia esta habilitada no Ships.py |
| Ligar/desligar | Tecla L (configuravel) e botao "Auto Fire" no menu do oficial tatico; os dois controlam o mesmo estado |
| Estado inicial | Desligado a cada batalha (configuravel) |
| Aviso | "AUTO FIRE" no painel do jogador, desenhado pelo Status HUD |
| Alvo | Modo 0 (padrao): so o alvo selecionado (e o subsistema escolhido). Modo 1: seu alvo ou o inimigo mais proximo. Modo 2: cada sistema escolhe o inimigo com melhor solucao |
| Disparo manual | Tem prioridade: enquanto a tecla de disparo de um grupo esta pressionada, o Auto Fire nao mexe nele |
| Phasers | Disparam se algum banco pode atingir o alvo, dentro de PhaserRange (% da distancia de dano maximo) e com carga >= PhaserMinCharge |
| Torpedos | Todo tubo pronto com boa solucao dispara (opcao A); TorpedoReserve guarda municao |
| Spread | Automatico pela nota: >= SpreadMinSolution usa o maior spread; entre os minimos usa Single; ao desligar volta a escolha do jogador |
| Pulso | Mesma nota dos torpedos, sem correcao em voo, mais a carga |
| Alerta | O Auto Fire nao muda o nivel de alerta; fora do alerta vermelho fica parado |

## 4. Estrutura

```
scripts\Custom\Spaceframe\Modules\AutoFire\
    __init__.py
    AutoFire.py    ligar/desligar, ciclo de disparo, integracao com o nucleo
    Solution.py    calculo da nota de solucao de tiro (sem interface)
    Config.py      configuracoes
```

- `Solution.py` nao conhece interface nem ciclo: recebe nave, alvo, arma e
  devolve a nota (0-100). Pode ser testado sozinho.
- `AutoFire.py` usa o nucleo como os outros modulos (Start, Stop, Tick) e tem
  um timer proprio, criado so com o Auto Fire ligado e a nave habilitada.
- Ships.py: `"AutoFire": Def` habilita, `0` desabilita (liga/desliga, sem
  intensidade).
- Status HUD: le o estado do Auto Fire pelo nucleo (`GetModule("AutoFire")`)
  e mostra o aviso; o Auto Fire nao desenha nada.

## 5. Configuracao (Modules\AutoFire\Config.py)

Padrao do projeto: porcentagens de 0 a 100, liga/desliga 1 ou 0.

| Opcao | Padrao | Funcao |
|---|---|---|
| ToggleKey | "L" | Tecla de liga/desliga |
| StartEnabled | 0 | Comecar a batalha ligado |
| FireInterval | 0.1 | Segundos entre ciclos de disparo |
| TargetMode | 0 | 0 = seu alvo; 1 = seu alvo ou inimigo mais proximo; 2 = melhor solucao por sistema |
| PhaserRange | 100 | % da distancia de dano maximo do phaser |
| PhaserMinCharge | 50 | % minima de carga do banco |
| TorpedoMinSolution | 70 | Nota minima para disparar torpedo |
| SpreadMinSolution | 85 | Nota minima para usar spread |
| PulseMinSolution | 70 | Nota minima para armas de pulso |
| TorpedoReserve | 0 | Torpedos guardados: nao dispara abaixo disso |

## 6. Ciclo de disparo (a cada FireInterval)

1. Pre-condicoes: Auto Fire ligado; nave do jogador viva e habilitada; nao
   camuflada; alerta vermelho. Se alguma falhar, nada e disparado (as armas
   que o Auto Fire tinha mandado disparar param).
2. Alvo conforme TargetMode. Modos 1 e 2 usam a lista de inimigos da missao e
   so consideram inimigos dentro do alcance de alguma arma.
3. Para cada grupo (primario, secundario, terciario), separadamente e com
   protecao contra erro:
   - se o jogador segura a tecla de disparo do grupo: nao mexe (o modulo
     acompanha os mesmos eventos de tecla que o jogo usa);
   - phasers: algum banco com `CanHit`, dentro de PhaserRange e com carga >=
     PhaserMinCharge -> StartFiring; senao StopFiring;
   - torpedos: melhor nota entre os tubos prontos e no arco; respeita
     TorpedoReserve; >= SpreadMinSolution -> maior cadeia disponivel;
     >= TorpedoMinSolution -> Single; StartFiring; senao StopFiring;
   - pulso: mesma nota (sem correcao), carga; StartFiring ou StopFiring.
   - o disparo usa o mesmo comando do disparo manual (StartFiring com alvo e
     subsistema escolhido).
4. Ao desligar, ao morrer, ao perder o alvo ou no fim da batalha: StopFiring em
   tudo que o Auto Fire disparou, spread volta a escolha do jogador, timer para.

Limitacao a confirmar: o jogo dispara por grupo. Se tubos mal alinhados
dispararem junto, o modulo passa a disparar tubo a tubo (`TorpedoTube.Fire`).

## 7. Nota de solucao de tiro (Solution.py)

Para um tubo de torpedo ou arma de pulso contra o alvo (ou subsistema):

1. Tempo de voo `t = distancia / velocidade do projetil`, recalculado uma vez
   com a posicao prevista.
2. Posicao prevista: `GetPredictedPosition` do jogo daqui a `t`, mais o
   deslocamento do subsistema escolhido.
3. Erro de mira: angulo entre a direcao do tubo e a posicao prevista. Fora do
   arco (`IsInArc`) -> nota 0.
4. Desvio da mira: `distancia * seno(angulo)`.
5. Manobra do alvo: `1/2 * aceleracao maxima do alvo * t^2`.
6. Correcao do projetil: quanto ele consegue desviar durante a orientacao
   (pela velocidade de curva e duracao da orientacao).
7. Erro esperado: desvio da mira menos a correcao (minimo 0), combinado com a
   manobra do alvo.
8. Nota: `100 * (1 - erro esperado / raio do alvo)`, limitada a 0-100. Se o
   tempo de voo passar da vida do projetil -> 0.

A forma de combinar os erros e o peso da manobra sao constantes a calibrar nos
testes.

## 8. Tratamento de erros

- Cada grupo de armas avaliado com protecao propria; erro em um nao afeta os
  outros; mensagem so com Debug = 1.
- Funcao ausente no jogo -> alternativa conservadora (sem previsao: posicao
  atual; sem aceleracao: alvo parado). Nunca mais agressivo.
- Multiplayer: desligado (regra do nucleo).

## 9. Testes

- Simulacao (antes de cada instalacao): nota em cenarios montados (alvo parado
  e alinhado -> alta; fora do arco -> 0; distante e manobrando -> baixa;
  projetil sem correcao); ciclo (tecla segurada, spread, reserva, desligar);
  verificacao de compatibilidade com Python 1.5.
- No jogo, com o jogador, por etapa, com prints. Calibracao: com Debug = 1, o
  console mostra a nota de cada torpedo disparado para comparar com
  acertos e erros.

## 10. Ordem de construcao

Cada etapa testada no jogo antes da proxima:

1. Base: tecla L, botao no menu tatico, aviso no HUD, liga/desliga (sem
   disparar).
2. Phasers.
3. Torpedos: nota, minimo, reserva.
4. Spread automatico.
5. Pulso.
6. Modos de alvo 1 e 2.

## 11. Riscos e pontos em aberto

- Assinaturas das funcoes por arma (`CanHit`, `IsInArc`, `Fire`) nao estao
  confirmadas; a etapa 1 inclui uma verificacao rapida no jogo.
- O texto "Spread: ..." do painel de armas pode nao se atualizar quando o
  modulo troca o modo.
- Registrar a tecla L por script a cada batalha precisa ser confirmado no
  jogo; se nao der, fica so o botao (e a tecla configuravel manualmente).
- A calibracao da nota depende de testes no jogo.
