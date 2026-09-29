# Unitree Go2 — Python Examples v2

Versão reajustada: **todos os exemplos são standalone**.

Não existe `common.py` e nenhum exemplo importa um módulo auxiliar local.
Cada `.py` importa `unitree_webrtc_connect` diretamente.

## Quantidade

- SPORT_CMD: 49 exemplos
- SPORT_CMD_MCF: 43 exemplos
- Movimento: 7 exemplos
- Diagnóstico: 1

## 1. Ative seu venv

```bash
source /caminho/do/projeto/.venv/bin/activate
```

## 2. Confirme a instalação

```bash
python 00_check_install.py
```

Esperado, entre outras linhas:

```text
unitree_webrtc_connect: OK
Hello: 1016
BackFlip MCF: 2043
```

## 3. Conecte no AP do Go2

Exemplo:

```bash
nmcli dev wifi connect 'Go2_32814'
```

## 4. Hello

O arquivo correto neste pacote é:

```bash
python sport/16_hello.py
```

## 5. Sit / StandUp / Dance

```bash
python sport/09_sit.py
python sport/04_stand_up.py
python sport/22_dance1.py
```

## 6. Movimento

```bash
python movement/forward.py
python movement/backward.py
python movement/left.py
python movement/right.py
python movement/rotate_left.py
python movement/rotate_right.py
python movement/stop.py
```

Os exemplos de movimento enviam `Move` a 20 Hz por 2 segundos e tentam `StopMove`
no `finally`, inclusive quando ocorre uma exceção.

## 7. MCF

```bash
python mcf/27_static_walk.py
python mcf/28_trot_run.py
python mcf/29_economic_gait.py
python mcf/33_free_walk.py
```

O BackFlip MCF está em:

```bash
python mcf/31_back_flip.py
```

Esse exemplo exige digitar `EXECUTAR` antes de enviar a ação.

## Observação sobre parâmetros

As tabelas que você forneceu confirmam os nomes e IDs, mas não o payload de todos
os comandos. Portanto, este pacote não inventa parâmetros.

Comandos com payload não confirmado, como `TrajectoryFollow`, `Trigger`, `Content`,
`Pose`, `SetAutoRecovery` e `SwitchAvoidMode`, possuem arquivos que mostram o ID
e informam que nenhuma ação foi enviada.

`Move`, `Euler`, `BodyHeight`, `FootRaiseHeight` e `SpeedLevel` usam a estrutura
de parâmetros já utilizada no seu código/projeto.

## Segurança

Flips, saltos, handstand, bound, pounce e ações semelhantes exigem confirmação
manual no terminal e devem ser testados com bastante espaço livre.
