# Unitree Go2 — Python Examples v3

**Compatibilidade:** Python 3.9+

Versão padronizada: **todos os exemplos criam a conexão pelo mesmo módulo**,
`core/go2_connection.py`, que injeta a **AES key** do robô (obrigatória no Go2
com firmware >= 1.1.15). Não há chave nem IP gravados nos scripts.

## Quantidade

- SPORT_CMD: 49 exemplos
- SPORT_CMD_MCF: 43 exemplos
- Movimento: 7 exemplos
- Diagnóstico: `tests/check_install.py`, `tests/check_config.py`, `tests/full_health_check.py`
- Controle por gamepad Xbox: `core/control.py`

## 0. Configuração (uma vez)

O Go2 com firmware **>= 1.1.15** exige uma **AES key** por robô (32 caracteres
hex). Ela vem da Unitree Cloud, da conta em que o robô está vinculado no app.
Sem ela a conexão falha com `AesKeyRequiredError`.

### 0.1 Prepare o `.env`

```bash
cp .env.example .env
```

O `.env` já está no `.gitignore`: **nunca** faça commit dele.

### 0.2 Descubra o serial (SN) e a chave

Com o venv ativo (passo 1) e internet (não precisa estar no Wi-Fi do robô).
Deixe de fora o `--password`: o comando pede a senha sem mostrá-la e ela não
fica no histórico do shell.

```bash
unitree-fetch-aes-key --email 'SEU_EMAIL' --region global --device-type Go2
```

Sem `--sn`, ele lista todos os robôs da conta (SN, alias, online e chave).
Se sua conta for da China, use `--region cn`.

Se você já tem um `accessToken`, pode usá-lo no lugar do e-mail:

```bash
unitree-fetch-aes-key --token 'SEU_ACCESS_TOKEN' --region global --device-type Go2
```

### 0.3 Grave a chave direto no `.env` (sem exibir na tela)

Com o SN do seu Go2 (ex.: `B42D4000XXXXXXXX`), `--quiet` devolve só a chave:

```bash
AES_KEY=$(unitree-fetch-aes-key --email 'SEU_EMAIL' --region global \
  --device-type Go2 --sn 'SEU_SERIAL' --quiet) \
&& sed -i "s|^UNITREE_AES_KEY=.*|UNITREE_AES_KEY=${AES_KEY}|" .env \
&& unset AES_KEY
```

Alternativa manual: copie a chave da tabela e cole em `UNITREE_AES_KEY=` no `.env`.

Se aparecer `dev.key is empty`, o firmware do robô é anterior à 1.1.15 e
não usa chave: coloque `UNITREE_REQUIRE_AES=0` no `.env`.

### 0.4 Valide (sem conectar ao robô e sem imprimir a chave)

```bash
python tests/check_config.py
```

### 0.5 Conecte de fato

Entre no Wi-Fi do Go2 (passo 3) e rode o exemplo mais simples:

```bash
python core/modules/sport/16_hello.py
```

Saída esperada: `Conectando ao Go2...` seguido da resposta do comando e
`Desconectando...`. Todos os outros scripts se conectam do mesmo jeito, via
`create_connection()`.

### 0.6 Outras opções

Variáveis exportadas no terminal têm prioridade sobre o `.env`.
Opções extras: `UNITREE_METHOD` (LocalAP/LocalSTA/Remote), `UNITREE_IP`,
`UNITREE_SN`, `UNITREE_REGION`, `UNITREE_DEVICE`, `UNITREE_REQUIRE_AES`.

> Não cole senha, token ou AES key em chats, issues ou commits. Se a chave
> vazar, trate-a como comprometida.

## 1. Ative seu venv e instale as dependências

```bash
source /caminho/do/projeto/.venv/bin/activate
pip install -r requirements.txt
```

## 2. Confirme a instalação

```bash
python tests/check_install.py
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

Este é o mesmo exemplo do passo 0.5. O arquivo correto neste pacote é:

```bash
python core/modules/sport/16_hello.py
```

## 5. Sit / StandUp / Dance

```bash
python core/modules/sport/09_sit.py
python core/modules/sport/04_stand_up.py
python core/modules/sport/22_dance1.py
```

## 6. Movimento

```bash
python core/modules/movement/forward.py
python core/modules/movement/backward.py
python core/modules/movement/left.py
python core/modules/movement/right.py
python core/modules/movement/rotate_left.py
python core/modules/movement/rotate_right.py
python core/modules/movement/stop.py
```

Os exemplos de movimento enviam `Move` a 20 Hz por 2 segundos e tentam `StopMove`
no `finally`, inclusive quando ocorre uma exceção.

## 7. MCF

```bash
python core/modules/mcf/27_static_walk.py
python core/modules/mcf/28_trot_run.py
python core/modules/mcf/29_economic_gait.py
python core/modules/mcf/33_free_walk.py
```

O BackFlip MCF está em:

```bash
python core/modules/mcf/31_back_flip.py
```

Esse exemplo exige digitar `EXECUTAR` antes de enviar a ação.

## 8. Controle por gamepad e health check

```bash
python core/control.py             # requer gamepad Xbox 360 e o pacote evdev
python tests/full_health_check.py  # monitora os tópicos do robô por 30 s
```

Ambos usam `create_connection()` e, portanto, também precisam do `.env`.

## Erros comuns

| Erro | Causa / solução |
|------|-----------------|
| `UNITREE_AES_KEY não definida` | Falta criar/preencher o `.env` (passo 0). |
| `UNITREE_AES_KEY inválida` | A chave deve ter exatamente 32 caracteres hexadecimais. |
| `AesKeyRequiredError` / chave rejeitada | Chave ausente ou de outro robô. Busque de novo com `unitree-fetch-aes-key`. |
| `ModuleNotFoundError: core` | Rode o script a partir da estrutura original do projeto (não mova o arquivo de pasta). |
| Timeout ao conectar | Confirme que está no Wi-Fi do Go2 (AP) e que o app Unitree não está conectado ao robô. |

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

## Estrutura

```text
core/
  go2_connection.py   # create_connection(): único ponto de conexão + AES key
  control.py          # controle por gamepad
  modules/
    sport/  mcf/  movement/   # exemplos (rodar da raiz do projeto)
tests/
  check_install.py  check_config.py  full_health_check.py
.env.example
```

Novo exemplo? Copie qualquer script existente: o topo já traz o bootstrap
(`sys.path` + `from core.go2_connection import create_connection`) e use
`conn = create_connection()`.
