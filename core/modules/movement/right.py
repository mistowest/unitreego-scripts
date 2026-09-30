"""
Unitree Go2 — SPORT / Move
API ID observado na sua instalação: 1008

Este arquivo é standalone: não depende de common.py.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from core.go2_connection import create_connection  # noqa: E402
from unitree_webrtc_connect import (
    RTC_TOPIC,
    SPORT_CMD,
)

COMMAND = 'Move'
API_ID_EXPECTED = 1008


async def main():
    conn = create_connection()

    try:
        print("Conectando ao Go2...")
        await conn.connect()

        loop = asyncio.get_running_loop()
        end = loop.time() + 2.0

        print("Movendo por 2.0 segundos...")

        while loop.time() < end:
            payload = {
                "api_id": SPORT_CMD["Move"],
                "parameter": {
                    "x": 0.0,
                    "y": -0.25,
                    "z": 0.0,
                },
            }

            await asyncio.wait_for(
                conn.datachannel.pub_sub.publish_request_new(
                    RTC_TOPIC["SPORT_MOD"],
                    payload,
                ),
                timeout=2.0,
            )
            await asyncio.sleep(0.05)

    finally:
        print("STOP...")
        try:
            await asyncio.wait_for(
                conn.datachannel.pub_sub.publish_request_new(
                    RTC_TOPIC["SPORT_MOD"],
                    {"api_id": SPORT_CMD["StopMove"]},
                ),
                timeout=2.0,
            )
        except Exception as exc:
            print("Aviso StopMove:", exc)

        print("Desconectando...")
        try:
            await asyncio.wait_for(conn.disconnect(), timeout=5.0)
        except Exception as exc:
            print("Aviso ao desconectar:", exc)


if __name__ == "__main__":
    asyncio.run(main())
