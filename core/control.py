 import asyncio
import contextlib

from evdev import InputDevice, ecodes, list_devices

from unitree_webrtc_connect import (
    UnitreeWebRTCConnection,
    WebRTCConnectionMethod,
    RTC_TOPIC,
    SPORT_CMD,
    SPORT_CMD_MCF,
)


# ============================================================
# CONFIGURAÇÃO
# ============================================================

GAMEPAD_NAME = "Microsoft X-Box 360 pad"

CONTROL_INTERVAL = 0.05       # 20 Hz
GAMEPAD_SCAN_INTERVAL = 1.0   # procura Xbox a cada 1 segundo
DEADZONE = 0.14


# ============================================================
# VELOCIDADE NORMAL
# ============================================================

NORMAL_FORWARD = 0.75
NORMAL_BACKWARD = 0.50
NORMAL_SIDE = 0.50
NORMAL_YAW = 1.00


# ============================================================
# TURBO - LT
# ============================================================

TURBO_FORWARD = 1.30
TURBO_BACKWARD = 0.75
TURBO_SIDE = 0.80
TURBO_YAW = 1.50


# ============================================================
# TRIGGERS
#
# Seu Xbox informou:
#
# ABS_Z  = 0..255
# ABS_RZ = 0..255
#
# normalize_axis() transforma isso aproximadamente em -1..+1.
# ============================================================

TRIGGER_PRESS = 0.60
TRIGGER_RELEASE = -0.50


# ============================================================
# BACKFLIP
# ============================================================

BACKFLIP_HOLD_SECONDS = 3.0
BACKFLIP_STABILIZE_SECONDS = 0.50


# ============================================================
# ESTADO GLOBAL
# ============================================================

running = True

gamepad_connected = False

turbo_enabled = False

rt_pressed = False
lidar_rotation = True

backflip_task = None


axis = {
    "lx": 0.0,
    "ly": 0.0,
    "rx": 0.0,
    "lt": -1.0,
    "rt": -1.0,
}


# Impede Move enquanto ações especiais são executadas.
action_lock = asyncio.Lock()


# ============================================================
# RESET
# ============================================================

def reset_movement():
    axis["lx"] = 0.0
    axis["ly"] = 0.0
    axis["rx"] = 0.0


def reset_controls():
    global turbo_enabled
    global rt_pressed

    reset_movement()

    axis["lt"] = -1.0
    axis["rt"] = -1.0

    turbo_enabled = False
    rt_pressed = False


# ============================================================
# EIXOS
# ============================================================

def normalize_axis(value, minimum, maximum):
    """
    Converte o intervalo físico do controle para -1..+1.

    Seus sticks chegam praticamente ao limite completo:

        -32768 .. +32767

    Portanto não precisamos de saturação artificial.
    """

    center = (maximum + minimum) / 2.0
    radius = (maximum - minimum) / 2.0

    if radius == 0:
        return 0.0

    normalized = (value - center) / radius

    return max(
        -1.0,
        min(1.0, normalized),
    )


def apply_deadzone(value):
    """
    Remove drift do analógico e reescala o restante
    novamente para 0..1.

    Isso significa que mesmo com DEADZONE=0.14,
    o final físico do stick continua correspondendo a 100%.
    """

    if abs(value) < DEADZONE:
        return 0.0

    sign = 1.0 if value > 0 else -1.0

    adjusted = (
        (abs(value) - DEADZONE)
        / (1.0 - DEADZONE)
    )

    return sign * adjusted


# ============================================================
# LOCALIZAR GAMEPAD
# ============================================================

def find_gamepad_once():
    """
    Procura o Xbox atualmente conectado.

    Não depende de event12/event13/etc.

    Depois de uma reconexão, o Linux pode mudar:
        event12 -> event13 -> event15 ...
    """

    try:
        devices = list_devices()
    except OSError:
        return None

    for path in devices:

        try:
            dev = InputDevice(path)

            if GAMEPAD_NAME.lower() in dev.name.lower():
                return dev

            dev.close()

        except (PermissionError, OSError):
            continue

    return None


async def wait_for_gamepad():
    """
    Aguarda indefinidamente um Xbox aparecer.
    """

    print()
    print("⏳ Aguardando controle Xbox...")
    print("   Ligue ou conecte o controle.")
    print()

    while running:

        gamepad = find_gamepad_once()

        if gamepad is not None:
            return gamepad

        await asyncio.sleep(
            GAMEPAD_SCAN_INTERVAL
        )

    return None


# ============================================================
# SPORT API
# ============================================================

async def publish_sport(
    conn,
    api_id,
    parameter=None,
):
    payload = {
        "api_id": api_id,
    }

    if parameter is not None:
        payload["parameter"] = parameter

    return await conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["SPORT_MOD"],
        payload,
    )


async def sport(
    conn,
    command,
    parameter=None,
):
    if command not in SPORT_CMD:
        raise RuntimeError(
            f"SPORT_CMD '{command}' não disponível."
        )

    return await publish_sport(
        conn,
        SPORT_CMD[command],
        parameter,
    )


async def sport_mcf(
    conn,
    command,
    parameter=None,
):
    if command not in SPORT_CMD_MCF:
        raise RuntimeError(
            f"SPORT_CMD_MCF '{command}' não disponível."
        )

    api_id = SPORT_CMD_MCF[command]

    response = await publish_sport(
        conn,
        api_id,
        parameter,
    )

    print(
        f"🔵 MCF {command} "
        f"[API {api_id}]"
    )
    print(
        f"   Resposta: {response}"
    )

    return response


# ============================================================
# MOVIMENTO
# ============================================================

async def move(
    conn,
    x,
    y,
    yaw,
):
    await sport(
        conn,
        "Move",
        {
            "x": float(x),
            "y": float(y),
            "z": float(yaw),
        },
    )


async def stop(conn):
    if conn is None:
        return

    try:
        await sport(
            conn,
            "StopMove",
        )

    except Exception as exc:
        print(
            f"⚠️ StopMove: {exc}"
        )


# ============================================================
# CANCELAR BACKFLIP
# ============================================================

async def cancel_backflip():
    global backflip_task

    task = backflip_task

    if task is None:
        return

    # Evita tentar aguardar a própria task.
    if task is asyncio.current_task():
        backflip_task = None
        return

    if not task.done():

        task.cancel()

        with contextlib.suppress(
            asyncio.CancelledError
        ):
            await task

    backflip_task = None


# ============================================================
# FAIL-SAFE DO CONTROLE
# ============================================================

async def controller_safe_stop(conn):
    """
    Chamado quando o Xbox desaparece.

    A ordem é proposital:

        1. gamepad_connected=False
        2. zera sticks
        3. cancela ação armada
        4. envia StopMove

    Dessa forma movement_loop() deixa de enviar Move antes
    mesmo do primeiro await.
    """

    global gamepad_connected

    gamepad_connected = False

    reset_controls()

    await cancel_backflip()

    await stop(conn)


# ============================================================
# AÇÕES NORMAIS
# ============================================================

async def normal_action(
    conn,
    label,
    command,
):
    if not gamepad_connected:
        return

    async with action_lock:

        # O controle pode ter sido removido enquanto
        # esperávamos pelo lock.
        if not gamepad_connected:
            return

        reset_movement()

        await stop(conn)

        await asyncio.sleep(0.15)

        if not gamepad_connected:
            return

        print()
        print(label)

        try:
            response = await sport(
                conn,
                command,
            )

            print(
                f"   SPORT {command} "
                f"[API {SPORT_CMD[command]}]"
            )

            print(
                f"   Resposta: {response}"
            )

        except Exception as exc:
            print(
                f"❌ {command}: {exc}"
            )


async def hello(conn):
    await normal_action(
        conn,
        "🐾 HELLO",
        "Hello",
    )


async def dance(conn):
    await normal_action(
        conn,
        "💃 DANCE1",
        "Dance1",
    )


async def sit(conn):
    await normal_action(
        conn,
        "🐕 SIT",
        "Sit",
    )


async def heart(conn):
    await normal_action(
        conn,
        "❤️ FINGER HEART",
        "FingerHeart",
    )


# ============================================================
# MCF MODES
# ============================================================

async def set_mcf_mode(
    conn,
    command,
    label,
):
    if not gamepad_connected:
        return

    async with action_lock:

        if not gamepad_connected:
            return

        reset_movement()

        await stop(conn)

        await asyncio.sleep(0.20)

        if not gamepad_connected:
            return

        print()
        print(
            f"🐕 MCF → {label}"
        )

        try:
            await sport_mcf(
                conn,
                command,
            )

        except Exception as exc:
            print(
                f"❌ MCF {command}: {exc}"
            )


# ============================================================
# BACKFLIP MCF
# ============================================================

async def backflip_countdown(conn):
    """
    B precisa permanecer pressionado durante 3 segundos.

    Se:
      - B for solto
      - Xbox desconectar
      - BACK for pressionado
      - programa encerrar

    a task é cancelada.
    """

    global backflip_task

    try:
        print()
        print("⚠️ BACKFLIP ARMADO")
        print("   Continue segurando B...")
        print()

        for remaining in (3, 2, 1):

            if not gamepad_connected:
                return

            print(
                f"   🤸 {remaining}..."
            )

            await asyncio.sleep(1.0)

        if not gamepad_connected:
            return

        async with action_lock:

            if not gamepad_connected:
                return

            reset_movement()

            print()
            print(
                "🛑 Preparando BackFlip..."
            )

            await stop(conn)

            await asyncio.sleep(
                BACKFLIP_STABILIZE_SECONDS
            )

            if not gamepad_connected:
                return

            print()
            print("🤸 BACKFLIP!")
            print(
                "   MCF API: "
                f"{SPORT_CMD_MCF['BackFlip']}"
            )

            response = await sport_mcf(
                conn,
                "BackFlip",
            )

            print()
            print(
                "📨 Resposta completa:"
            )
            print(response)

    except asyncio.CancelledError:
        print()
        print(
            "❎ BACKFLIP CANCELADO"
        )
        raise

    except Exception as exc:
        print()
        print(
            f"❌ BACKFLIP FALHOU: {exc}"
        )

    finally:
        # Só limpa se ainda formos a task registrada.
        if backflip_task is asyncio.current_task():
            backflip_task = None


# ============================================================
# LIDAR
# ============================================================

async def toggle_lidar():
    global lidar_rotation

    lidar_rotation = not lidar_rotation

    print()

    if lidar_rotation:
        print(
            "🟢 LIDAR → ON"
        )
    else:
        print(
            "🔴 LIDAR → OFF"
        )

    print(
        "⚠️ Toggle registrado, mas o motor físico "
        "ainda não está integrado."
    )
    print()


# ============================================================
# PERFIL DE VELOCIDADE
# ============================================================

def speed_profile():
    if turbo_enabled:
        return (
            TURBO_FORWARD,
            TURBO_BACKWARD,
            TURBO_SIDE,
            TURBO_YAW,
        )

    return (
        NORMAL_FORWARD,
        NORMAL_BACKWARD,
        NORMAL_SIDE,
        NORMAL_YAW,
    )


# ============================================================
# LOOP DE MOVIMENTO
# ============================================================

async def movement_loop(conn):
    """
    Este loop permanece vivo mesmo sem Xbox.

    Sem controle:
        Move é proibido.

    Com controle:
        envia movimento a 20 Hz.
    """

    was_moving = False

    while running:

        # ====================================================
        # SEM CONTROLE = MOVIMENTO PROIBIDO
        # ====================================================

        if not gamepad_connected:

            if was_moving:

                await stop(conn)
                was_moving = False

            await asyncio.sleep(
                CONTROL_INTERVAL
            )

            continue

        # ====================================================
        # AÇÃO ESPECIAL
        # ====================================================

        if action_lock.locked():

            if was_moving:

                await stop(conn)
                was_moving = False

            await asyncio.sleep(
                CONTROL_INTERVAL
            )

            continue

        # ====================================================
        # VELOCIDADE
        # ====================================================

        (
            max_forward,
            max_backward,
            max_side,
            max_yaw,
        ) = speed_profile()

        forward_input = -apply_deadzone(
            axis["ly"]
        )

        lateral_input = -apply_deadzone(
            axis["lx"]
        )

        yaw_input = -apply_deadzone(
            axis["rx"]
        )

        # Frente / ré têm limites independentes.
        if forward_input >= 0:

            vx = (
                forward_input
                * max_forward
            )

        else:

            vx = (
                forward_input
                * max_backward
            )

        vy = (
            lateral_input
            * max_side
        )

        yaw = (
            yaw_input
            * max_yaw
        )

        moving = (
            abs(vx) > 0.01
            or abs(vy) > 0.01
            or abs(yaw) > 0.01
        )

        try:

            # Pode ter desconectado durante os cálculos.
            if not gamepad_connected:

                reset_movement()

                if was_moving:
                    await stop(conn)
                    was_moving = False

                continue

            if moving:

                await move(
                    conn,
                    vx,
                    vy,
                    yaw,
                )

                was_moving = True

            elif was_moving:

                await stop(conn)

                was_moving = False

        except Exception as exc:

            print(
                f"⚠️ Movimento: {exc}"
            )

            reset_movement()

            try:
                await stop(conn)
            except Exception:
                pass

            was_moving = False

        await asyncio.sleep(
            CONTROL_INTERVAL
        )

    # Garantia adicional ao sair do loop.
    if was_moving:
        await stop(conn)


# ============================================================
# CONFIGURAÇÃO DOS EIXOS DO GAMEPAD
# ============================================================

def get_gamepad_axes(gamepad):
    abs_info = {}

    analog_axes = (
        ecodes.ABS_X,
        ecodes.ABS_Y,
        ecodes.ABS_RX,
        ecodes.ABS_Z,
        ecodes.ABS_RZ,
    )

    for code in analog_axes:

        try:

            info = gamepad.absinfo(
                code
            )

            if info is not None:
                abs_info[code] = info

        except (OSError, KeyError):
            pass

    return abs_info


def print_gamepad_axes(abs_info):
    print(
        "🎮 Eixos detectados:"
    )

    for code, info in abs_info.items():

        print(
            f"   {ecodes.ABS.get(code, code)} "
            f"{info.min} → {info.max}"
        )

    print()


# ============================================================
# LOOP DO GAMEPAD
# ============================================================

async def gamepad_loop(
    gamepad,
    conn,
):
    global turbo_enabled
    global rt_pressed
    global backflip_task

    abs_info = get_gamepad_axes(
        gamepad
    )

    print_gamepad_axes(
        abs_info
    )

    async for event in gamepad.async_read_loop():

        if not running:
            return

        # Se o manager marcou o controle como desconectado,
        # nenhum evento restante deve ser processado.
        if not gamepad_connected:
            return

        # ====================================================
        # ANALÓGICOS / D-PAD
        # ====================================================

        if event.type == ecodes.EV_ABS:

            # ------------------------------------------------
            # D-PAD VERTICAL
            # ------------------------------------------------

            if event.code == ecodes.ABS_HAT0Y:

                if event.value == -1:

                    await set_mcf_mode(
                        conn,
                        "TrotRun",
                        "TROT RUN 🏃",
                    )

                elif event.value == 1:

                    await set_mcf_mode(
                        conn,
                        "StaticWalk",
                        "STATIC WALK 🚶",
                    )

                continue

            # ------------------------------------------------
            # D-PAD HORIZONTAL
            # ------------------------------------------------

            if event.code == ecodes.ABS_HAT0X:

                if event.value == -1:

                    await set_mcf_mode(
                        conn,
                        "EconomicGait",
                        "ECONOMIC GAIT 🔋",
                    )

                elif event.value == 1:

                    await set_mcf_mode(
                        conn,
                        "FreeWalk",
                        "FREE WALK 🐕",
                    )

                continue

            # ------------------------------------------------
            # EIXO DESCONHECIDO
            # ------------------------------------------------

            if event.code not in abs_info:
                continue

            info = abs_info[
                event.code
            ]

            value = normalize_axis(
                event.value,
                info.min,
                info.max,
            )

            # ------------------------------------------------
            # LEFT X
            # ------------------------------------------------

            if event.code == ecodes.ABS_X:

                axis["lx"] = value

            # ------------------------------------------------
            # LEFT Y
            # ------------------------------------------------

            elif event.code == ecodes.ABS_Y:

                axis["ly"] = value

            # ------------------------------------------------
            # RIGHT X
            # ------------------------------------------------

            elif event.code == ecodes.ABS_RX:

                axis["rx"] = value

            # ------------------------------------------------
            # LT → TURBO
            # ------------------------------------------------

            elif event.code == ecodes.ABS_Z:

                axis["lt"] = value

                if (
                    value > TRIGGER_PRESS
                    and not turbo_enabled
                ):

                    turbo_enabled = True

                    print()
                    print(
                        "🏎️ TURBO ON"
                    )
                    print()

                elif (
                    value < TRIGGER_RELEASE
                    and turbo_enabled
                ):

                    turbo_enabled = False

                    print()
                    print(
                        "🚶 TURBO OFF"
                    )
                    print()

            # ------------------------------------------------
            # RT → LIDAR
            # ------------------------------------------------

            elif event.code == ecodes.ABS_RZ:

                axis["rt"] = value

                pressed = (
                    value > TRIGGER_PRESS
                )

                if (
                    pressed
                    and not rt_pressed
                ):

                    rt_pressed = True

                    await toggle_lidar()

                elif (
                    value < TRIGGER_RELEASE
                ):

                    rt_pressed = False

        # ====================================================
        # BOTÕES
        # ====================================================

        elif event.type == ecodes.EV_KEY:

            # ------------------------------------------------
            # B → BACKFLIP HOLD 3s
            # ------------------------------------------------

            if event.code == ecodes.BTN_EAST:

                # PRESS
                if event.value == 1:

                    if (
                        backflip_task is None
                        or backflip_task.done()
                    ):

                        backflip_task = (
                            asyncio.create_task(
                                backflip_countdown(
                                    conn
                                )
                            )
                        )

                # RELEASE
                elif event.value == 0:

                    if (
                        backflip_task is not None
                        and not backflip_task.done()
                    ):

                        await cancel_backflip()

                continue

            # Os demais botões só interessam no PRESS.
            if event.value != 1:
                continue

            # ------------------------------------------------
            # X → HELLO
            # ------------------------------------------------

            if event.code == ecodes.BTN_WEST:

                await hello(conn)

            # ------------------------------------------------
            # Y → DANCE
            # ------------------------------------------------

            elif event.code == ecodes.BTN_NORTH:

                await dance(conn)

            # ------------------------------------------------
            # A → SIT
            # ------------------------------------------------

            elif event.code == ecodes.BTN_SOUTH:

                await sit(conn)

            # ------------------------------------------------
            # RB → HEART
            # ------------------------------------------------

            elif event.code == ecodes.BTN_TR:

                await heart(conn)

            # ------------------------------------------------
            # BACK → EMERGENCY STOP
            # ------------------------------------------------

            elif event.code == ecodes.BTN_SELECT:

                print()
                print(
                    "🚨 EMERGENCY STOP"
                )
                print()

                await cancel_backflip()

                reset_controls()

                await stop(conn)

            # ------------------------------------------------
            # START
            # ------------------------------------------------

            elif event.code == ecodes.BTN_START:

                print(
                    "ℹ️ START sem função."
                )


# ============================================================
# GERENCIADOR HOT-PLUG
# ============================================================

async def gamepad_manager(conn):
    """
    Gerencia o Xbox durante toda a vida do programa.

    Pode fazer:

        Xbox ON
          ↓
        controla
          ↓
        Xbox OFF
          ↓
        StopMove
          ↓
        espera
          ↓
        Xbox ON novamente
          ↓
        reconecta automaticamente

    O /dev/input/eventXX pode mudar livremente.
    """

    global gamepad_connected

    while running:

        gamepad = None

        try:

            # =================================================
            # ESPERA CONTROLE
            # =================================================

            gamepad = await wait_for_gamepad()

            if gamepad is None:
                return

            # =================================================
            # ESTADO SEGURO ANTES DE LIBERAR
            # =================================================

            gamepad_connected = False

            reset_controls()

            await cancel_backflip()

            await stop(conn)

            print()
            print(
                "=========================================="
            )
            print(
                "          🎮 XBOX CONECTADO"
            )
            print(
                "=========================================="
            )
            print(
                f"Nome:   {gamepad.name}"
            )
            print(
                f"Device: {gamepad.path}"
            )
            print()

            # Só libera movimento depois de tudo zerado.
            gamepad_connected = True

            print(
                "🛡️ Controle liberado."
            )
            print()

            # =================================================
            # CONTROLE ATIVO
            # =================================================

            await gamepad_loop(
                gamepad,
                conn,
            )

            # Se o loop terminou sem exceção, trate igualmente
            # como perda do controle.
            print()
            print(
                "⚠️ Leitura do Xbox terminou."
            )

        except asyncio.CancelledError:
            raise

        except OSError as exc:

            print()
            print(
                "=========================================="
            )
            print(
                "         🎮 XBOX DESCONECTADO"
            )
            print(
                "=========================================="
            )
            print(
                f"Motivo: {exc}"
            )
            print()

        except Exception as exc:

            print()
            print(
                "⚠️ Erro no controle:"
            )
            print(
                f"   {type(exc).__name__}: {exc}"
            )
            print()

        finally:

            # IMPORTANTE:
            # bloqueia Move ANTES de qualquer await.
            gamepad_connected = False

            reset_controls()

            await cancel_backflip()

            try:

                await stop(conn)

                print(
                    "🛑 StopMove enviado."
                )

            except Exception as exc:

                print(
                    "⚠️ Falha no StopMove "
                    f"após desconexão: {exc}"
                )

            if gamepad is not None:

                try:
                    gamepad.close()
                except Exception:
                    pass

        if running:

            print()
            print(
                "⏳ Aguardando reconexão do Xbox..."
            )
            print()

            await asyncio.sleep(
                GAMEPAD_SCAN_INTERVAL
            )


# ============================================================
# SHUTDOWN
# ============================================================

async def shutdown(conn):
    global running
    global gamepad_connected

    if not running:
        return

    # Desabilita tudo imediatamente.
    running = False
    gamepad_connected = False

    reset_controls()

    print()
    print(
        "🛑 Encerrando controle..."
    )

    await cancel_backflip()

    # ========================================================
    # PARA ROBÔ
    # ========================================================

    if conn is not None:

        try:

            await asyncio.wait_for(
                stop(conn),
                timeout=2.0,
            )

        except Exception:
            pass

    # ========================================================
    # WEBRTC
    # ========================================================

    if conn is not None:

        print(
            "🔌 Fechando WebRTC..."
        )

        try:

            await asyncio.wait_for(
                conn.disconnect(),
                timeout=5.0,
            )

        except asyncio.TimeoutError:

            print(
                "⚠️ Timeout fechando WebRTC."
            )

        except Exception as exc:

            print(
                f"⚠️ WebRTC shutdown: {exc}"
            )

    print(
        "✅ Finalizado."
    )


# ============================================================
# INTERFACE
# ============================================================

def print_controls():
    print()
    print(
        "=========================================="
    )
    print(
        "            🟢 GO2 CONECTADO"
    )
    print(
        "=========================================="
    )
    print()
    print(
        "LEFT STICK       Movimento"
    )
    print(
        "RIGHT STICK      Rotação"
    )
    print()
    print(
        "LT               🏎️ Turbo"
    )
    print(
        "RT               📡 LiDAR toggle"
    )
    print()
    print(
        "X                🐾 Hello"
    )
    print(
        "Y                💃 Dance1"
    )
    print(
        "A                🐕 Sit"
    )
    print(
        "RB               ❤️ FingerHeart"
    )
    print()
    print(
        "B (3 segundos)   🤸 BackFlip MCF"
    )
    print()
    print(
        "D-PAD ↑          🏃 TrotRun"
    )
    print(
        "D-PAD ↓          🚶 StaticWalk"
    )
    print(
        "D-PAD ←          🔋 EconomicGait"
    )
    print(
        "D-PAD →          🐕 FreeWalk"
    )
    print()
    print(
        "BACK             🚨 Emergency Stop"
    )
    print(
        "START            sem função"
    )
    print()
    print(
        "Xbox OFF         🛑 Stop + aguarda"
    )
    print(
        "Xbox ON          🎮 reconecta sozinho"
    )
    print(
        "CTRL+C           encerra"
    )
    print()
    print(
        "=========================================="
    )
    print()


# ============================================================
# MAIN
# ============================================================

async def main():
    global running

    conn = None

    running = True

    reset_controls()

    print()
    print(
        "=========================================="
    )
    print(
        "       UNITREE GO2 — XBOX CONTROL"
    )
    print(
        "=========================================="
    )
    print()

    try:

        # ====================================================
        # CONECTA AO GO2
        #
        # O Xbox NÃO precisa estar ligado neste momento.
        # ====================================================

        print(
            "🤖 Conectando ao Go2..."
        )
        print(
            "   LocalAP → 192.168.12.1"
        )
        print()

        conn = UnitreeWebRTCConnection(
            WebRTCConnectionMethod.LocalAP
        )

        await conn.connect()

        reset_controls()

        await stop(conn)

        print_controls()

        # ====================================================
        # TAREFAS PERMANENTES
        # ====================================================

        movement_task = asyncio.create_task(
            movement_loop(conn),
            name="movement-loop",
        )

        gamepad_task = asyncio.create_task(
            gamepad_manager(conn),
            name="gamepad-manager",
        )

        try:

            await asyncio.gather(
                movement_task,
                gamepad_task,
            )

        finally:

            for task in (
                movement_task,
                gamepad_task,
            ):

                if not task.done():
                    task.cancel()

            await asyncio.gather(
                movement_task,
                gamepad_task,
                return_exceptions=True,
            )

    except asyncio.CancelledError:
        raise

    except Exception as exc:

        print()
        print(
            "❌ ERRO PRINCIPAL:"
        )
        print(
            f"   {type(exc).__name__}: {exc}"
        )

    finally:

        await shutdown(
            conn
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        print(
            "\n👋 Controle encerrado."
        )
