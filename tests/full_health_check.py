import asyncio
import time
from collections import defaultdict

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.go2_connection import create_connection  # noqa: E402
from unitree_webrtc_connect import (
    RTC_TOPIC,
)


# ============================================================
# CONFIGURAÇÃO
# ============================================================

MONITOR_SECONDS = 30

TOPICS = {
    "LOW_STATE": RTC_TOPIC["LOW_STATE"],
    "SPORT_STATE": RTC_TOPIC["LF_SPORT_MOD_STATE"],
    "LIDAR": RTC_TOPIC["ULIDAR_STATE"],
    "ODOMETRY": RTC_TOPIC["ROBOTODOM"],
}


# ============================================================
# CORES
# ============================================================

RESET = "\033[0m"
BOLD = "\033[1m"

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
GRAY = "\033[90m"


def ok(text):
    return f"{GREEN}✓ {text}{RESET}"


def warning(text):
    return f"{YELLOW}⚠ {text}{RESET}"


def error(text):
    return f"{RED}✗ {text}{RESET}"


def info(text):
    return f"{CYAN}• {text}{RESET}"


# ============================================================
# MONITOR
# ============================================================

class Monitor:
    def __init__(self):
        self.latest = {}
        self.count = defaultdict(int)
        self.first_time = {}
        self.last_time = {}

    def callback(self, name):
        def handler(message):
            now = time.monotonic()

            self.latest[name] = message
            self.count[name] += 1

            if name not in self.first_time:
                self.first_time[name] = now

            self.last_time[name] = now

        return handler

    def rate(self, name):
        count = self.count[name]

        if count < 2:
            return 0.0

        start = self.first_time.get(name)
        end = self.last_time.get(name)

        if start is None or end is None:
            return 0.0

        elapsed = end - start

        if elapsed <= 0:
            return 0.0

        return (count - 1) / elapsed

    def data(self, name):
        message = self.latest.get(name)

        if not message:
            return {}

        return message.get("data", {})


# ============================================================
# UTILIDADES
# ============================================================

def section(title):
    print()
    print(f"{BOLD}{CYAN}{title}{RESET}")
    print("─" * 60)


def value_line(label, value, status="ok"):
    label = f"{label:<32}"

    if status == "ok":
        icon = f"{GREEN}✓{RESET}"
    elif status == "warning":
        icon = f"{YELLOW}⚠{RESET}"
    elif status == "error":
        icon = f"{RED}✗{RESET}"
    else:
        icon = f"{GRAY}•{RESET}"

    print(f"  {icon} {label} {value}")


def safe_number(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ============================================================
# BATERIA
# ============================================================

def show_battery(low_state, alerts):
    section("BATERIA")

    bms = low_state.get("bms_state", {})

    if not bms:
        value_line(
            "BMS",
            "dados não recebidos",
            "warning",
        )

        alerts.append("Dados da bateria não disponíveis")
        return

    soc = safe_number(bms.get("soc"))
    current = safe_number(bms.get("current"))

    bq_ntc = bms.get("bq_ntc", [])
    mcu_ntc = bms.get("mcu_ntc", [])

    cycle = bms.get("cycle", "?")

    voltage = safe_number(
        low_state.get("power_v")
    )

    temperatures = []

    for temp in bq_ntc + mcu_ntc:
        if isinstance(temp, (int, float)):
            temperatures.append(temp)

    # Carga
    if soc <= 10:
        status = "error"
        alerts.append(
            f"Bateria criticamente baixa: {soc:.0f}%"
        )

    elif soc <= 20:
        status = "warning"
        alerts.append(
            f"Bateria baixa: {soc:.0f}%"
        )

    else:
        status = "ok"

    value_line(
        "Carga",
        f"{soc:.0f}%",
        status,
    )

    value_line(
        "Tensão",
        f"{voltage:.2f} V",
        "ok",
    )

    value_line(
        "Corrente",
        f"{current:.0f}",
        "ok",
    )

    value_line(
        "Ciclos da bateria",
        str(cycle),
        "ok",
    )

    if temperatures:
        minimum = min(temperatures)
        maximum = max(temperatures)

        if maximum >= 60:
            status = "error"

            alerts.append(
                f"Temperatura alta no BMS: {maximum} °C"
            )

        elif maximum >= 50:
            status = "warning"

            alerts.append(
                f"BMS aquecido: {maximum} °C"
            )

        else:
            status = "ok"

        value_line(
            "Temperaturas BMS",
            f"{minimum}–{maximum} °C",
            status,
        )


# ============================================================
# MOTORES
# ============================================================

def show_motors(low_state, alerts):
    section("MOTORES")

    motors = low_state.get(
        "motor_state",
        []
    )

    # Seu Go2 apresentou 20 posições,
    # mas os 12 primeiros são os motores das pernas.
    active_motors = motors[:12]

    if not active_motors:
        value_line(
            "Motores",
            "dados não recebidos",
            "error",
        )

        alerts.append(
            "Estado dos motores não disponível"
        )

        return

    temperatures = []

    for index, motor in enumerate(
        active_motors,
        start=1,
    ):
        temperature = safe_number(
            motor.get("temperature")
        )

        lost = motor.get("lost", 0)
        q = safe_number(
            motor.get("q")
        )

        temperatures.append(
            temperature
        )

        if temperature >= 80:
            status = "error"

            alerts.append(
                f"Motor {index:02d} muito quente: "
                f"{temperature:.0f} °C"
            )

        elif temperature >= 65:
            status = "warning"

            alerts.append(
                f"Motor {index:02d} aquecido: "
                f"{temperature:.0f} °C"
            )

        else:
            status = "ok"

        value_line(
            f"Motor {index:02d}",
            (
                f"{temperature:5.0f} °C   "
                f"q={q:7.3f}   "
                f"lost={lost}"
            ),
            status,
        )

    if temperatures:
        print()

        maximum = max(temperatures)
        average = (
            sum(temperatures)
            / len(temperatures)
        )

        value_line(
            "Temperatura máxima",
            f"{maximum:.0f} °C",
            (
                "error"
                if maximum >= 80
                else
                "warning"
                if maximum >= 65
                else
                "ok"
            ),
        )

        value_line(
            "Temperatura média",
            f"{average:.1f} °C",
            "ok",
        )


# ============================================================
# IMU
# ============================================================

def show_imu(sport_state, alerts):
    section("IMU")

    imu = sport_state.get(
        "imu_state",
        {}
    )

    if not imu:
        value_line(
            "IMU",
            "dados não recebidos",
            "warning",
        )

        return

    gyro = imu.get(
        "gyroscope",
        []
    )

    accel = imu.get(
        "accelerometer",
        []
    )

    rpy = imu.get(
        "rpy",
        []
    )

    temperature = safe_number(
        imu.get("temperature")
    )

    value_line(
        "Giroscópio",
        str(gyro),
        "ok",
    )

    value_line(
        "Acelerômetro",
        str(accel),
        "ok",
    )

    value_line(
        "Roll / Pitch / Yaw",
        str(rpy),
        "ok",
    )

    # Apenas sinalizamos a leitura alta.
    # Não afirmamos falha automaticamente.
    if temperature >= 80:
        status = "warning"

        alerts.append(
            f"IMU reportando {temperature:.0f} °C"
        )

    else:
        status = "ok"

    value_line(
        "Temperatura IMU",
        f"{temperature:.0f} °C",
        status,
    )


# ============================================================
# SPORT
# ============================================================

def show_sport(sport_state, alerts):
    section("ESTADO DO ROBÔ")

    if not sport_state:
        value_line(
            "Sport State",
            "não recebido",
            "warning",
        )

        return

    error_code = sport_state.get(
        "error_code",
        0
    )

    mode = sport_state.get(
        "mode",
        "?"
    )

    gait = sport_state.get(
        "gait_type",
        "?"
    )

    height = safe_number(
        sport_state.get(
            "body_height"
        )
    )

    velocity = sport_state.get(
        "velocity",
        []
    )

    if error_code == 0:
        status = "ok"
    else:
        # Não interpretamos o significado
        # sem documentação específica.
        status = "warning"

        alerts.append(
            f"Sport State reportou error_code={error_code}"
        )

    value_line(
        "Error code",
        str(error_code),
        status,
    )

    value_line(
        "Mode",
        str(mode),
        "ok",
    )

    value_line(
        "Gait",
        str(gait),
        "ok",
    )

    value_line(
        "Altura do corpo",
        f"{height:.3f} m",
        "ok",
    )

    value_line(
        "Velocidade",
        str(velocity),
        "ok",
    )


# ============================================================
# LIDAR
# ============================================================

def show_lidar(lidar, alerts):
    section("LIDAR")

    if not lidar:
        value_line(
            "LiDAR",
            "dados não recebidos",
            "warning",
        )

        alerts.append(
            "LiDAR não está enviando estado"
        )

        return

    error_state = lidar.get(
        "error_state",
        None
    )

    dirty = safe_number(
        lidar.get(
            "dirty_percentage"
        )
    )

    cloud_frequency = safe_number(
        lidar.get(
            "cloud_frequency"
        )
    )

    packet_loss = safe_number(
        lidar.get(
            "cloud_packet_loss_rate"
        )
    )

    imu_frequency = safe_number(
        lidar.get(
            "imu_frequency"
        )
    )

    imu_loss = safe_number(
        lidar.get(
            "imu_packet_loss_rate"
        )
    )

    firmware = lidar.get(
        "firmware_version",
        "?",
    )

    software = lidar.get(
        "software_version",
        "?",
    )

    if error_state == 0:
        value_line(
            "Estado",
            "SEM ERROS",
            "ok",
        )

    else:
        value_line(
            "Estado",
            f"error_state={error_state}",
            "error",
        )

        alerts.append(
            f"LiDAR error_state={error_state}"
        )

    if dirty > 20:
        dirty_status = "warning"

        alerts.append(
            f"LiDAR reporta {dirty:.1f}% de sujeira"
        )
    else:
        dirty_status = "ok"

    value_line(
        "Sujeira",
        f"{dirty:.1f}%",
        dirty_status,
    )

    value_line(
        "Cloud frequency",
        f"{cloud_frequency:.2f} Hz",
        "ok",
    )

    if packet_loss >= 10:
        loss_status = "error"

        alerts.append(
            f"Perda de pacotes LiDAR: "
            f"{packet_loss:.2f}%"
        )

    elif packet_loss >= 2:
        loss_status = "warning"

        alerts.append(
            f"Pequena perda de pacotes LiDAR: "
            f"{packet_loss:.2f}%"
        )

    else:
        loss_status = "ok"

    value_line(
        "Perda cloud",
        f"{packet_loss:.2f}%",
        loss_status,
    )

    value_line(
        "IMU LiDAR",
        f"{imu_frequency:.2f} Hz",
        "ok",
    )

    value_line(
        "Perda IMU",
        f"{imu_loss:.2f}%",
        (
            "warning"
            if imu_loss > 0
            else "ok"
        ),
    )

    value_line(
        "Firmware",
        str(firmware),
        "ok",
    )

    value_line(
        "Software",
        str(software),
        "ok",
    )


# ============================================================
# TELEMETRIA
# ============================================================

def show_topics(monitor, alerts):
    section("TELEMETRIA")

    for name in TOPICS:
        count = monitor.count[name]
        rate = monitor.rate(name)

        if count == 0:
            value_line(
                name,
                "SEM DADOS",
                "warning",
            )

            alerts.append(
                f"{name} não recebeu dados"
            )

        else:
            value_line(
                name,
                (
                    f"{rate:.2f} Hz "
                    f"({count} mensagens)"
                ),
                "ok",
            )


# ============================================================
# RESULTADO
# ============================================================

def show_result(alerts):
    print()
    print("=" * 60)

    if not alerts:
        print(
            f"{GREEN}{BOLD}"
            "✓ RESULTADO: NENHUMA ANOMALIA DETECTADA"
            f"{RESET}"
        )

    else:
        print(
            f"{YELLOW}{BOLD}"
            f"⚠ RESULTADO: {len(alerts)} ITEM(NS) "
            "PARA VERIFICAR"
            f"{RESET}"
        )

        print()

        for item in alerts:
            print(
                f"  {YELLOW}•{RESET} {item}"
            )

    print("=" * 60)


# ============================================================
# MAIN
# ============================================================

async def main():
    monitor = Monitor()
    alerts = []

    conn = create_connection()

    subscribed = []

    print()
    print(
        f"{BOLD}{CYAN}"
        "UNITREE GO2 - HEALTH CHECK"
        f"{RESET}"
    )

    print("=" * 60)

    print()
    print(
        "Nenhum comando de movimento será enviado."
    )

    print()

    try:
        print(
            f"{CYAN}Conectando ao Go2...{RESET}"
        )

        await conn.connect()

        print(
            ok("WebRTC conectado")
        )

        # ----------------------------------------
        # SUBSCRIBE
        # ----------------------------------------

        for name, topic in TOPICS.items():
            try:
                conn.datachannel.pub_sub.subscribe(
                    topic,
                    monitor.callback(name),
                )

                subscribed.append(
                    topic
                )

            except Exception as exc:
                print(
                    warning(
                        f"Não foi possível assinar "
                        f"{name}: {exc}"
                    )
                )

        # ----------------------------------------
        # COLETA
        # ----------------------------------------

        print()
        print(
            f"Coletando telemetria por "
            f"{MONITOR_SECONDS} segundos..."
        )

        print()

        start = time.monotonic()

        while True:
            elapsed = (
                time.monotonic()
                - start
            )

            if elapsed >= MONITOR_SECONDS:
                break

            remaining = max(
                0,
                int(
                    MONITOR_SECONDS
                    - elapsed
                )
            )

            total = sum(
                monitor.count.values()
            )

            print(
                f"\r"
                f"{CYAN}●{RESET} "
                f"{remaining:02d}s restantes | "
                f"{total} mensagens",
                end="",
                flush=True,
            )

            await asyncio.sleep(1)

        print()
        print()

        # ----------------------------------------
        # DADOS
        # ----------------------------------------

        low_state = monitor.data(
            "LOW_STATE"
        )

        sport_state = monitor.data(
            "SPORT_STATE"
        )

        lidar = monitor.data(
            "LIDAR"
        )

        # ----------------------------------------
        # DASHBOARD
        # ----------------------------------------

        print("=" * 60)
        print(
            f"{BOLD}RESULTADO DO DIAGNÓSTICO{RESET}"
        )
        print("=" * 60)

        show_battery(
            low_state,
            alerts,
        )

        show_motors(
            low_state,
            alerts,
        )

        show_imu(
            sport_state,
            alerts,
        )

        show_sport(
            sport_state,
            alerts,
        )

        show_lidar(
            lidar,
            alerts,
        )

        show_topics(
            monitor,
            alerts,
        )

        show_result(
            alerts
        )

    finally:

        for topic in subscribed:
            try:
                conn.datachannel.pub_sub.unsubscribe(
                    topic
                )
            except Exception:
                pass

        await asyncio.sleep(0.3)

        try:
            await asyncio.wait_for(
                conn.disconnect(),
                timeout=5,
            )
        except Exception:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        print(
            "\nDiagnóstico interrompido."
        )

    except Exception as exc:
        print()
        print(
            f"{RED}✗ ERRO: {exc}{RESET}"
        )
