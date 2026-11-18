# Spaceframe - Modulo Secondary Target: especificacao de design

Data: 2026-11-18
Status: aguardando aprovacao do usuario
Base: Spaceframe core v0.6, AutoFire v0.4, Status HUD v0.12
Experimento que sustenta este design: `secondary-target-experiment-spec.md` (sonda STProbe, rodada em jogo pelo usuario em 2026-11-18).

## 1. Intencao

No jogo, todas as armas da nave do jogador atiram no mesmo alvo: o alvo selecionado. Com varios inimigos, muitas armas ficam paradas porque nao alcancam esse alvo, enquanto poderiam estar atirando em outro que esta ao alcance delas.

O Secondary Target faz essas armas ociosas atirarem sozinhas em alvos secundarios, escolhidos dinamicamente, sem tirar o foco do alvo principal. O alvo principal continua sendo o que o jogador escolheu e continua recebendo todas as armas que conseguem acerta-lo.

Sucesso, para o usuario:
- Com 2+ inimigos, armas que nao alcancam o alvo principal atiram em outros inimigos ao alcance delas, sem o jogador fazer nada alem do que ja faz (segurar a tecla de disparo, ou ligar o AutoFire).
- O alvo principal nunca recebe menos fogo do que receberia sem o modulo.
- E configuravel por nave: cada nave usa phasers, torpedos, pulso ou uma combinacao.

## 2. Objetivos, nao-objetivos, anti-objetivos

Objetivos
- Cada grupo de armas (primario, secundario, terciario) funciona de forma independente, e cada arma escolhe o alvo a que consegue chegar.
- Varios alvos secundarios ao mesmo tempo, sem limite de alvos por regra: o que limita e ter condicao de tiro. Duas armas podem escolher o mesmo alvo se ele for a melhor opcao.
- Funciona com disparo manual e com o AutoFire.
- Configuravel por nave (Ships.py) quanto aos tipos de arma.

Nao-objetivos
- Escolher o subsistema do alvo secundario (mira no centro do casco).
- Manobrar a nave, multiplayer, naves de outros jogadores.
- Controle por arma individual (abordagem B, descartada, ver secao 4).

Anti-objetivos (seria falha mesmo que "funcione")
- Atirar em aliado ou neutro (so inimigos da missao, como o AutoFire).
- Tirar fogo do alvo principal.
- Gastar torpedo em alvo secundario ruim (torpedo e municao limitada).
- Deixar a nave com uma regra de arma alterada depois que o modulo para.
- Travar o jogo no fim da batalha.

## 3. Regras de comportamento (decididas pelo usuario)

1. Cada grupo e cada arma e independente e escolhe seus alvos automaticamente; podem escolher o mesmo alvo.
2. Sem limite de alvos; depende apenas de a arma ter solucao de tiro.
3. As armas disparam tanto com acionamento manual como com o AutoFire.
4. Disparo manual: o modulo completa so as armas livres. Com a tecla de disparo de um grupo pressionada, as armas que tem condicao de tiro no alvo principal atiram nele, como no jogo; as que nao tem atiram sozinhas em alvos secundarios. Sem tecla pressionada e sem AutoFire, nada dispara.
5. Cone de exclusao: arma que alcanca o alvo principal (tem condicao de tiro nele) fica reservada a ele e nao e usada para secundarios. Definicao escolhida pelo usuario: "a arma alcanca o principal", nao "a arma tem boa nota nele".
6. Por nave (Ships.py): quais tipos de arma usam alvos secundarios.

## 4. O que a investigacao mostrou

Confirmado em jogo (sonda STProbe, 2026-11-18)
- Nao existe alvo por arma: `Weapon.Fire(0.0, 1)` nao dispara (ret 0); `Weapon.FireDumb(0.0, 1)` dispara em linha reta sem alvo; `Weapon.StopFiring()` / `SetFiring(0)` seguram a arma por 0,25 s a 2 s e o motor a reativa enquanto o alvo esta na lista do sistema.
- Cada sistema de armas tem uma lista de alvos. Com dois alvos na lista (`StartFiring(A)`, `StartFiring(B)`), o motor manda cada arma para um alvo que ela alcanca (um banco que so alcanca B atirou em B).
- Ordem da lista: armas que alcancam varios alvos listados atiram no primeiro listado (uma amostra; o teste saiu INCONCLUSIVE por geometria).
- Restricao "um disparo por vez" (`single=1`, vem do hardpoint): com ela, so um alvo recebe fogo por vez (`simul:0`). `pSystem.GetProperty().SetSingleFire(0)` em tempo de execucao a remove (`simul:1`, `onA:2 onB:6`), a propriedade lida volta a `p1` ao restaurar com `SetSingleFire(1)`. `SetGroupFireMode(1 ou 2)` nao ajuda. Os tres grupos da nave testada tinham `single=1`.
- Disparo manual: apertar a tecla mantem na lista os alvos ja colocados; soltar a tecla chama `StopFiring()` e esvazia a lista inteira. `StartFiring(B)` sozinho recoloca.
- Torpedo: no evento `ET_TORPEDO_ENTERED_SET`, `Torpedo_Cast(pEvent.GetDestination())` e `SetTarget(idB)` + `SetTargetOffset(vZero)` fazem um torpedo lancado em A ir para B (visto em jogo). `GetParentID()` identifica o nosso.
- Pulso: com A e B na lista, as 6 armas se dividiram (4 em A, 2 em B). `PulseWeapon.CanHitTarget` aceita `(ponto, vetor)`; com a nave como argumento da TypeError.
- Escrever arquivo de log nao funciona (`Securelevel prevents file IO`).

Nao confirmado (entra como verificacao antes de implementar, secao 9)
- Lista de alvos no sistema de torpedos (MULTI_TORP nao rodou).
- `SetSingleFire(0)` nos sistemas de torpedo e de pulso.
- Disparo manual (tecla segura) com o single-fire liberado: B recebeu fogo? Tres rodadas do MANUAL_PROP0 deram `onB:0` com B na lista e ao alcance (`B alone: onB:2 a 3`), mas nas duas ultimas A tambem ficou em `onA:0`, entao a sonda nao decide. Risco aberto da fase 1: se o jogo so atira no alvo principal enquanto a tecla esta pressionada, o modulo precisa de outro caminho no disparo manual (por exemplo reafirmar `StartFiring(secundario)` + `SetForceUpdate(1)` depois do evento da tecla). Verificar em jogo com o proprio modulo (Tarefa 5), com a opcao Debug mostrando quais alvos recebem fogo.
- Se a propriedade single-fire e compartilhada entre naves da mesma classe e se volta ao normal na batalha seguinte.
- Assinatura util de alcance para torpedo (`TorpedoTube.CanHit`) e significado do 2o argumento do pulso.
- Escolha entre varios alvos secundarios quando duas armas livres alcancam B e C.

## 5. Abordagens consideradas

A. Lista de alvos do sistema conduzida pelo modulo (phaser e pulso) + redirecionamento no lancamento (torpedo). Escolhida pelo usuario. O modulo mantem a lista `[principal, secundario1, ...]` de cada sistema que esta disparando; o motor distribui as armas por alcance e a ordem da lista faz as armas que alcancam o principal ficarem nele. Custo: o motor escolhe qual arma vai em qual alvo, entao a independencia por arma e parcial; so funciona com `SetSingleFire(0)` e restaurar depois.

B. Controle por arma, arma a arma (`Weapon.Fire`/`StopFiring`/`SetFiring`). Descartada: `Fire` nao dispara, o motor reativa a arma em 0,25 s a 2 s, brigar com ele a cada ciclo cintila os feixes.

C. Hibrido: A como base e controle por arma onde A falhar. Evolucao futura, so se um caso real mostrar que a distribuicao do motor nao serve.

Evolucao possivel dentro de A para torpedos: disparar o tubo com `FireDumb` e redirecionar o torpedo no lancamento (`SetTarget`) para o alvo de melhor nota, dando controle por tubo. Verificar antes (secao 9).

## 6. Estrutura

```
scripts\Custom\Spaceframe\Modules\SecondaryTarget\
    __init__.py
    SecondaryTarget.py   ciclo, lista de alvos, torpedos, integracao com o nucleo
    Config.py            configuracoes
```

- Modulo Spaceframe como os outros (Start, Stop, Tick, timer proprio criado so com a tecnologia habilitada).
- Reaproveita `AutoFire\Solution.py` (nota de solucao de tiro e cone) para escolher alvo de torpedo; nao altera AutoFire. O AutoFire inicia o grupo no alvo principal e o Secondary Target completa a lista; os dois nao se chamam.
- O modulo le o estado do AutoFire so se precisar (via nucleo, `GetModule`); o AutoFire nao e alterado, exceto a correcao separada do bug de alcance do pulso (`AutoFire.py:633`, 1 argumento).
- Ships.py: `"SecondaryTarget": N` com N = soma de bits dos tipos de arma permitidos: 1 phaser, 2 torpedo, 4 pulso (7 = todos); `Def` = padrao do modulo (Config `Weapons`); `0` = desligado. Decisao do design (o usuario pediu "por nave"; a codificacao e escolha minha, na convencao numerica do projeto).

## 7. Ciclo (a cada Interval)

1. Pre-condicoes: nave do jogador viva, com a tecnologia, nao camuflada, alerta vermelho. Falhou: nada e feito.
2. Para cada grupo cujo tipo esta habilitado: so atua se o grupo esta disparando no alvo principal (`IsFiring()`), seja pela tecla do jogador ou pelo AutoFire. Grupo parado: nada.
3. Candidatos: inimigos da missao (grupo de inimigos, vivos, nao camuflados), exceto o principal, dentro do alcance de alguma arma do grupo, limitados aos `MaxCandidates` mais proximos (custo).
4. Armas livres: as do grupo que nao alcancam o principal (alcance pelas chamadas ja confirmadas: phaser `CanHit(ponto)`, pulso `CanHitTarget(ponto, vetor)`). Um secundario so entra se ha arma livre que o alcance.
5. Montar a lista do sistema: principal primeiro (ja la, vindo do jogo ou do AutoFire), depois cada secundario faltando (`if not IsInTargetList(t): StartFiring(t, ponto zero)`), e `StopFiringAtTarget(t)` dos que deixaram de ser candidatos.
6. Torpedos: ver secao 8.
7. `SetSingleFire(0)` no sistema, uma vez, ao assumir o grupo; restaurar ao desligar, quando o modulo para com a nave viva, e quando o jogador troca de nave. Registrar o valor original por ID da nave.
8. Soltar a tecla esvazia a lista no jogo; no ciclo seguinte, se o grupo esta disparando de novo, o modulo recoloca os secundarios.

## 8. Torpedos

Primeira versao: tentar a lista de alvos do sistema de torpedos como nos phasers (depende de MULTI_TORP e de `SetSingleFire(0)` no sistema, secao 9). Reserva e reforco: no evento `ET_TORPEDO_ENTERED_SET` (torpedo da nossa nave), redirecionar com `SetTarget` para o alvo secundario de melhor nota (`Solution.Score`) quando o tubo que atirou nao alcancava o principal; nota minima por alvo secundario (`SecondaryTorpedoMinSolution`) e `TorpedoReserve` do AutoFire respeitados, para nao gastar municao com alvo ruim.

## 9. Verificacoes antes de implementar (nova rodada da sonda)

1. MULTI_TORP (lista de alvos em torpedos).
2. SINGLEFIRE em torpedo e em pulso; MANUAL e ORDER com o single-fire liberado.
3. Se `SetSingleFire` de uma nave afeta outra nave da mesma classe e se na batalha seguinte o valor volta ao original sem restaurar.
4. Alcance de torpedo (`TorpedoTube.CanHit` com ponto) e o 2o argumento de `CanHitTarget` do pulso.
5. Escolha entre dois secundarios por armas que alcancam ambos (3 inimigos).
6. FireDumb + SetTarget em torpedo (so se a primeira versao precisar do controle por tubo).
Resultados confirmados entram em `docs/api/learned.md`.

## 10. Configuracao (Modules\SecondaryTarget\Config.py)

Padrao do projeto: porcentagens 0-100, liga/desliga 1 ou 0, `Def = -1` = padrao do modulo.

| Opcao | Padrao | Funcao |
|---|---|---|
| Weapons | 7 | Tipos de arma usados quando o Ships.py diz Def (1 phaser, 2 torpedo, 4 pulso) |
| Interval | 0.2 | Segundos entre ciclos |
| MaxCandidates | 4 | Quantos inimigos mais proximos sao avaliados por ciclo |
| SecondaryRange | 100 | % da distancia de dano maximo do phaser para aceitar um secundario |
| SecondaryTorpedoMinSolution | 70 | Nota minima para torpedo em alvo secundario |
| Debug | 0 | 1 = mensagens na tela e no console do modo de teste |

Os valores sao ajustados em jogo, como o AutoFire.

## 11. Risco e ciclo de vida

- Fim de batalha: `Stop()` so remove handlers e timers; nao toca em nave (as naves estao sendo destruidas; ver `learned.md`).
- O `SetSingleFire(0)` e a unica alteracao persistente: sempre restaurar, por ID, com a nave viva; se a propriedade for compartilhada por classe, o risco sobe e a verificacao 3 vira bloqueante.
- Cada chamada ao motor protegida por try/except; erro em um grupo para so aquele grupo.
- Custo desprezivel com a tecnologia desligada; ligada, no maximo `MaxCandidates` x armas por ciclo.
- Python 1.5.2 e testes de mock em `Spaceframe/tests/` como os demais modulos.

## 12. Decisoes tomadas apos a revisao do documento (marcadas como escolha minha, a confirmar)

- Porta de entrada: as verificacoes 1 a 3 da secao 9 sao obrigatorias antes de qualquer codigo (rodada da sonda feita pelo usuario). Se a verificacao 3 mostrar que `SetSingleFire` e compartilhado pela classe, o plano de reserva e aplicar `SetSingleFire(0)` somente enquanto o grupo esta disparando e restaurar assim que ele para, e nao usar o modulo em classes em que o inimigo da mesma classe esteja presente se isso nao for seguro.
- Escopo da primeira versao: phasers e pulso primeiro (fase 1); torpedos na fase 2, depois das verificacoes 1, 2, 4 e 6. Os torpedos nao bloqueiam a fase 1.
- Ordem: usuario roda as verificacoes primeiro; so entao o plano e a implementacao.
- Re-adicionar apos soltar a tecla: o modulo escuta os mesmos eventos de tecla de disparo que o AutoFire e recoloca os secundarios na hora; o `Interval` e so a rede de seguranca (uma falha de ate um `Interval` e aceitavel).
- Regra 5 (arma que "alcanca o principal"): e o teste de condicao de tiro da arma (`CanHit` / arco), o mesmo que o motor usa para distribuir as armas; `SecondaryRange` so serve para decidir quais inimigos viram candidatos a secundario. Se os dois testes discordarem em jogo, a ordem da lista (principal primeiro) continua mantendo o principal prioritario, e a divergencia e registrada.
- Restaurar o single-fire: sempre restaurar o valor original lido (nunca forcar 1), inclusive em naves cujo valor original ja era 0.

## 13. O que fica para quem constroi

- Detalhes do calculo de alcance por tipo de arma e a escolha entre secundarios empatados (secao 4, nao confirmado).
- Mensagem/indicacao no Status HUD (opcional, fora do escopo da primeira versao).
- Testes de mock e README trilingue (EN/ES/PT) do modulo.
