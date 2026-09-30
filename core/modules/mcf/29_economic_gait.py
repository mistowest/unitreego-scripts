"""
Unitree Go2 — MCF / EconomicGait
API ID observado na sua instalação: 1063

Este arquivo é standalone: não depende de common.py.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from core.go2_connection import create_connection  # noqa: E402
from unitree_webrtc_connect import (
    RTC_TOPIC,
    SPORT_CMD_MCF,
)

COMMAND = 'EconomicGait'
API_ID_EXPECTED = 1063


async def main():
    conn = create_connection()

    try:
        print("Conectando ao Go2...")
        await conn.connect()

        api_id = SPORT_CMD_MCF[COMMAND]
        print(f"Executando {COMMAND} (API {api_id})...")

        payload = {"api_id": api_id}

        response = await asyncio.wait_for(
            conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"],
                payload,
            ),
            timeout=5.0,
        )

        print("Resposta:", response)
        await asyncio.sleep(2)

    finally:
        print("Desconectando...")
        try:
            await asyncio.wait_for(conn.disconnect(), timeout=5.0)
        except Exception as exc:
            print("Aviso ao desconectar:", exc)


if __name__ == "__main__":
    asyncio.run(main())
