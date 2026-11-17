# Spaceframe

**[English](#english) · [Español](#español) · [Português](#português)**

---

## English

Spaceframe is a lightweight module framework for **Star Trek: Bridge Commander** (BC Remastered + Orion Delta / Bedrock). A small core loads gameplay modules and gives them shared services: one timer, one weapon-hit handler, ship identification, logging and error isolation. A module that fails is disabled on its own while the others keep running. It is plain Python 1.5.2, with **no** Foundation, FoundationTech, KM or QBautostart.

### Included modules

| Module | Version | What it does |
|---|---|---|
| MV Shields | 0.7 | The 6 shield facings behave as a single shield: total charge is redistributed between facings every cycle and on every hit. |
| Ablative Armor | 1.6 | An armor subsystem that absorbs damage after the shields and before the hull, repaired with the ship's repair rate. |
| Status HUD | 0.12 | Hull and armor percentages on the player's and the target's panels. |
| Auto Fire | 0.4 | Optional automatic phasers, torpedoes and pulse weapons against the mission's enemies (toggle with `L`). |

Which ships use which technology is set in `Config.py` / `Ships.py` (levels: All < Races < Families < Bedrock plugin < Ships). Write your own module by adding `Modules/<Name>/<Name>.py` with any of `Start`, `Stop`, `Tick`, `WeaponHit`, `Diag`.

### Repository layout

- `Spaceframe/scripts/` mirrors the game's `scripts/` folder.
- `Spaceframe/tests/` off-game tests (Python 3 mocks), `Spaceframe/docs/` design notes, `Spaceframe/patches/` the marked blocks added to vanilla files.
- `tools/` — `check.py` (lint for Python 1.5.2 + tests), `deploy.py` (install/pull/backup into the game), `lint15.py`, `build_api_index.py`.
- `docs/api/` — notes and index of the game's `App` API.

### Install

1. Copy `Spaceframe/scripts/Custom/Spaceframe` into the game's `scripts/Custom/`.
2. Apply the two marked blocks of `Spaceframe/patches/QuickBattle-hooks.txt` to `scripts/QuickBattle/QuickBattle.py` (keep the original as `QuickBattle.py.mvbak`).

Or, from the repo root: `python tools/check.py` then `python tools/deploy.py install Spaceframe`. Full documentation (settings, diagnostics, writing modules, uninstall): [`Spaceframe/README.txt`](Spaceframe/README.txt).

**Limitations:** Quick Battle only (no campaign, no multiplayer).

---

## Español

Spaceframe es un framework ligero de módulos para **Star Trek: Bridge Commander** (BC Remastered + Orion Delta / Bedrock). Un núcleo pequeño carga módulos de juego y les da servicios compartidos: un temporizador, un manejador de impactos de armas, identificación de naves, registro y aislamiento de errores. Un módulo que falla se desactiva solo y los demás siguen funcionando. Es Python 1.5.2 puro, **sin** Foundation, FoundationTech, KM ni QBautostart.

### Módulos incluidos

| Módulo | Versión | Qué hace |
|---|---|---|
| MV Shields | 0.7 | Los 6 lados del escudo actúan como un solo escudo: la carga total se redistribuye entre lados en cada ciclo y en cada impacto. |
| Ablative Armor | 1.6 | Un subsistema de blindaje que absorbe daño después de los escudos y antes del casco, reparado con la tasa de reparación de la nave. |
| Status HUD | 0.12 | Porcentajes de casco y blindaje en los paneles del jugador y del objetivo. |
| Auto Fire | 0.4 | Fásers, torpedos y armas de pulso automáticos contra los enemigos de la misión (se activa con `L`). |

Qué naves usan qué tecnología se define en `Config.py` / `Ships.py` (niveles: All < Races < Families < plugin de Bedrock < Ships). Para crear un módulo propio, agregue `Modules/<Nombre>/<Nombre>.py` con cualquiera de `Start`, `Stop`, `Tick`, `WeaponHit`, `Diag`.

### Estructura del repositorio

- `Spaceframe/scripts/` replica la carpeta `scripts/` del juego.
- `Spaceframe/tests/` pruebas fuera del juego (mocks en Python 3), `Spaceframe/docs/` notas de diseño, `Spaceframe/patches/` los bloques marcados añadidos a archivos originales.
- `tools/` — `check.py` (lint para Python 1.5.2 + pruebas), `deploy.py` (instalar/traer/respaldar en el juego), `lint15.py`, `build_api_index.py`.
- `docs/api/` — notas e índice de la API `App` del juego.

### Instalación

1. Copie `Spaceframe/scripts/Custom/Spaceframe` a `scripts/Custom/` del juego.
2. Aplique los dos bloques marcados de `Spaceframe/patches/QuickBattle-hooks.txt` en `scripts/QuickBattle/QuickBattle.py` (guarde el original como `QuickBattle.py.mvbak`).

O, desde la raíz del repositorio: `python tools/check.py` y luego `python tools/deploy.py install Spaceframe`. Documentación completa (ajustes, diagnóstico, escribir módulos, desinstalar): [`Spaceframe/README.txt`](Spaceframe/README.txt).

**Limitaciones:** solo Quick Battle (sin campaña ni multijugador).

---

## Português

Spaceframe é um framework leve de módulos para **Star Trek: Bridge Commander** (BC Remastered + Orion Delta / Bedrock). Um núcleo pequeno carrega módulos de jogabilidade e oferece serviços compartilhados: um temporizador, um tratador de impactos de armas, identificação de naves, log e isolamento de erros. Um módulo que falha é desativado sozinho e os demais continuam funcionando. É Python 1.5.2 puro, **sem** Foundation, FoundationTech, KM nem QBautostart.

### Módulos incluídos

| Módulo | Versão | O que faz |
|---|---|---|
| MV Shields | 0.7 | Os 6 lados do escudo funcionam como um escudo único: a carga total é redistribuída entre os lados a cada ciclo e a cada impacto. |
| Ablative Armor | 1.6 | Um subsistema de blindagem que absorve dano depois dos escudos e antes do casco, reparado com a taxa de reparo da nave. |
| Status HUD | 0.12 | Porcentagens de casco e blindagem nos painéis do jogador e do alvo. |
| Auto Fire | 0.4 | Phasers, torpedos e armas de pulso automáticos contra os inimigos da missão (liga/desliga com `L`). |

Quais naves usam qual tecnologia é definido em `Config.py` / `Ships.py` (níveis: All < Races < Families < plugin do Bedrock < Ships). Para criar um módulo próprio, adicione `Modules/<Nome>/<Nome>.py` com qualquer uma de `Start`, `Stop`, `Tick`, `WeaponHit`, `Diag`.

### Estrutura do repositório

- `Spaceframe/scripts/` espelha a pasta `scripts/` do jogo.
- `Spaceframe/tests/` testes fora do jogo (mocks em Python 3), `Spaceframe/docs/` notas de design, `Spaceframe/patches/` os blocos marcados adicionados a arquivos originais.
- `tools/` — `check.py` (lint para Python 1.5.2 + testes), `deploy.py` (instalar/puxar/backup no jogo), `lint15.py`, `build_api_index.py`.
- `docs/api/` — notas e índice da API `App` do jogo.

### Instalação

1. Copie `Spaceframe/scripts/Custom/Spaceframe` para `scripts/Custom/` do jogo.
2. Aplique os dois blocos marcados de `Spaceframe/patches/QuickBattle-hooks.txt` em `scripts/QuickBattle/QuickBattle.py` (guarde o original como `QuickBattle.py.mvbak`).

Ou, a partir da raiz do repositório: `python tools/check.py` e depois `python tools/deploy.py install Spaceframe`. Documentação completa (configurações, diagnóstico, escrever módulos, desinstalar): [`Spaceframe/README.txt`](Spaceframe/README.txt).

**Limitações:** apenas Quick Battle (sem campanha nem multiplayer).
