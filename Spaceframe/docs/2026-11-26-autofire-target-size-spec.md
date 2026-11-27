# Auto Fire: limite de voo pela capacidade do alvo

Data: 2026-11-26, main em 1fa7374. Status: aprovado pelo usuario em 2026-11-26 (teto padrao 5 s).

## Objetivo e motivo

Contra alvos grandes ou lentos o Auto Fire segura torpedos e pulse viaveis, porque o limite de
tempo de voo (1,5 s + guiagem; secundario 1,0 s) vale igual para qualquer alvo. Contra fighters e
naves ageis o comportamento atual e bom e deve continuar como esta.

Decidido pelo usuario: o criterio e o que o alvo CONSEGUE fazer (tamanho e capacidade de manobra
atual, com dano nos motores), nao o que ele esta fazendo no momento.

## Evidencia (log do jogo, todas as sessoes, so torpedos)

Estimativa: "sumiu perto do horario previsto" = acertou; nao ha confirmacao de impacto.

| Raio do alvo | ate 1,6 s | 1,6 a 2,5 s | mais de 2,5 s |
|---|---|---|---|
| < 0,3 km | 92-95% | 66% | 29% |
| 0,3 a 1 km | 97% | 75% (n=48) | 70% (n=10) |
| >= 2 km | 100% | 100% (n=19) | 100% (n=43) |

## Abordagens

- A (escolhida): limite calculado de raio e aceleracao atual. Automatico, 2 ajustes, reage a dano.
  Menos obvio por nave.
- B: faixas "pequeno/agil" a "grande/lento". Previsivel, mais ajustes, relacao arbitraria.
- C: classe fixa no Ships.py. Controle total, manutencao manual, dano exige regra extra.

## Comportamento

Calculo (unidades do jogo; 1 unidade = 0,175 km):

    T = raiz(2 * (TargetSizeAllowance / 100) * raio / aceleracao)
    limite = max(limite_atual, min(T, TargetSizeFlightTimeMax)) + guiagem
    (depois, como hoje, nunca acima da vida do projetil)

- raio = pTarget.GetRadius(); aceleracao = pTarget.GetImpulseEngineSubsystem().GetCurMaxAccel().
- O limite nunca fica abaixo do atual.
- Alvo sem subsistema de impulso (as duas bases olhadas nao tem), ou aceleracao <= 0,01: usa o teto.
- Erro de leitura, ou raio <= 0: usa o limite atual.
- Limite atual 0 (filtro desligado) e Rule 1: nada muda.
- Vale para torpedos e pulse, alvo principal e secundario, inclusive o filtro de secundarios no
  disparo manual (passa pelo mesmo ArcScore).
- Inalterados: percentual do arco, retencao em warp, phasers. (Spread: alterado depois, em 2026-11-26,
  a pedido do usuario: a janela so escolhe o modo de disparo e o limite do alvo vale tambem para ele;
  ver autofire-progress.md.)

## Ajustes novos (Config.py do AutoFire)

- TargetSizeAllowance = 100: percentual do raio aceito como desvio do alvo. Maior = mais
  permissivo. 0 = desligado.
- TargetSizeFlightTimeMax = 5.0: teto em segundos.
- Ausentes num Config.py antigo = desligado.

## Exemplos com os valores padrao (raios supostos)

| Alvo | raio | aceleracao | principal | secundario |
|---|---|---|---|---|
| Fighter | 0,11 km | 6,0 | 1,6 s (igual) | 1,1 s (igual) |
| Porte Defiant | 0,3 km | 2,5 | 1,6 s (igual) | cerca de 1,3 s |
| Porte Galaxy | 0,65 km | 1,75 | cerca de 2,2 s | cerca de 2,2 s |
| Cubo | 2,5 km | 1,75 | 4,1 s | 4,1 s |
| Base sem motor | - | - | 5,1 s | 5,1 s |

(Torpedos, ja com 0,1 s de guiagem.)

## Escolhas minhas (revisar)

1. So aceleracao linear; o giro fica de fora. Com giro, o porte Galaxy voltaria a 1,6 s.
2. O raio da nave inteira vale mesmo mirando um subsistema: o tiro longo tende a acertar a nave,
   nao necessariamente o subsistema.
3. O secundario usa o mesmo calculo sobre a base de 1,0 s.
4. So o limite de tempo muda nesta etapa; o arco so entra se o teste ainda mostrar disparo segurado.

## Diagnostico (Debug)

As linhas "Flight time filter" passam a mostrar o limite estendido, o raio e a aceleracao, e
marcam "passed by target size" quando o tiro so passou por causa desta regra (mesma limitacao de
frequencia de hoje).

## Riscos e nao confirmado

- GetCurMaxAccel com motor danificado/desativado ou potencia reduzida: nao testado em jogo. Se
  um alvo capaz de manobrar informar 0, recebe o teto; o log mostra o valor.
- O raio e o da esfera envolvente: naves alongadas parecem maiores.
- Alvo grande e distante passa a ser elegivel: no TargetMode 2 e nos secundarios pode ocupar
  armas que ficariam livres para um alvo pequeno que chegue. Mais torpedos gastos de longe.
- Pulse nao tem medicao de acerto no log.

## Implementacao (para quem construir)

- Calculo em arquivo irmao novo, Modules/AutoFire/TargetSize.py (AutoFire.py ja passa de 2000
  linhas). Python 1.5.2.
- FlightBlocked recebe o alvo como parametro opcional no fim (None = sem extensao), preservando os
  testes atuais. Calcular so quando o tiro seria bloqueado.
- Testes mock: tabela de exemplos, nunca abaixo da base, sem motor, erro de leitura, ajuste
  ausente/0, Rule 1, teto, vida do projetil.
- README (EN/ES/PT) so no fechamento da feature.

## Sucesso no teste em jogo

Contra alvo grande/lento, disparos entre 2 e 5 s saem e em geral acertam; contra fighters e naves
ageis nada muda.
