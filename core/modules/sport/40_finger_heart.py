"""
Unitree Go2 — SPORT / FingerHeart
API ID observado na sua instalação: 1036

Este arquivo é standalone: não depende de common.py.
"""
import asyncio

from unitree_webrtc_connect import (
    UnitreeWebRTCConnection,
    WebRTCConnectionMethod,
    RTC_TOPIC,
    SPORT_CMD,
)

COMMAND = 'FingerHeart'
API_ID_EXPECTED = 1036


async def main():
    pass

    conn = UnitreeWebRTCConnection(WebRTCConnectionMethod.LocalAP)

    try:
        print("Conectando ao Go2...")
        await conn.connect()

        api_id = SPORT_CMD[COMMAND]
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
