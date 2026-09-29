"""
Unitree Go2 — MCF / SetAutoRecovery
API ID observado na sua instalação: 2054

Este arquivo é standalone: não depende de common.py.
"""
import asyncio

from unitree_webrtc_connect import (
    UnitreeWebRTCConnection,
    WebRTCConnectionMethod,
    RTC_TOPIC,
    SPORT_CMD_MCF,
)

COMMAND = 'SetAutoRecovery'
API_ID_EXPECTED = 2054


async def main():
    # A tabela confirma o comando e o ID, mas não informa o formato do
    # parâmetro. Para não enviar um payload inventado, este exemplo apenas
    # valida que o comando existe na biblioteca instalada.
    api_id = SPORT_CMD_MCF[COMMAND]
    print(f"{COMMAND} está disponível.")
    print(f"API ID da biblioteca: {api_id}")
    print("API ID esperado neste pacote:", API_ID_EXPECTED)
    print("Nenhuma ação foi enviada ao robô porque o payload precisa ser confirmado.")


if __name__ == "__main__":
    asyncio.run(main())
