"""
Conexão padrão com o Unitree Go2 — ponto ÚNICO de configuração.

Todos os scripts do projeto criam a conexão por aqui:

    from core.go2_connection import create_connection
    conn = create_connection()

A configuração vem de variáveis de ambiente ou do arquivo `.env`
na raiz do projeto (copie `.env.example` para `.env`).

Variáveis:
    UNITREE_AES_KEY   Chave AES-128 do robô (32 caracteres hex).
                      Obrigatória no Go2 com firmware >= 1.1.15.
    UNITREE_REQUIRE_AES  1 (padrão) | 0  -> use 0 só em firmware < 1.1.15,
                      que não tem chave por dispositivo.
    UNITREE_METHOD    LocalAP (padrão) | LocalSTA | Remote
    UNITREE_IP        IP do robô (opcional; padrão da lib para LocalAP).
    UNITREE_SN        Número de série (opcional; usado no LocalSTA).
    UNITREE_EMAIL / UNITREE_PASSWORD   Só para o método Remote.
    UNITREE_REGION    global (padrão) | cn
    UNITREE_DEVICE    Go2 (padrão) | G1 | R1

Variáveis já exportadas no terminal têm prioridade sobre o `.env`.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from unitree_webrtc_connect import (
    UnitreeWebRTCConnection,
    WebRTCConnectionMethod,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"

_HEX32 = re.compile(r"^[0-9a-fA-F]{32}$")


class Go2ConfigError(RuntimeError):
    """Configuração ausente ou inválida."""


def _load_env_file(path: Path = ENV_FILE) -> None:
    """Carrega KEY=VALUE do .env sem sobrescrever o ambiente atual."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, _, value = line.partition("=")
        value = value.strip().strip("'\"")
        os.environ.setdefault(key.strip(), value)


def get_aes_key(required: bool = True) -> str | None:
    """Lê e valida a chave AES (nunca imprime o valor)."""
    _load_env_file()
    key = (os.environ.get("UNITREE_AES_KEY") or "").strip()

    if not key:
        if required:
            raise Go2ConfigError(
                "UNITREE_AES_KEY não definida.\n"
                "  1) cp .env.example .env\n"
                "  2) preencha UNITREE_AES_KEY no .env\n"
                "  (ou: export UNITREE_AES_KEY='...' no terminal)\n"
                "Para obter a chave: unitree-fetch-aes-key --help"
            )
        return None

    if not _HEX32.match(key):
        raise Go2ConfigError(
            "UNITREE_AES_KEY inválida: esperado 32 caracteres hexadecimais "
            f"(recebido {len(key)} caracteres)."
        )
    return key.lower()


def _get_method() -> WebRTCConnectionMethod:
    name = (os.environ.get("UNITREE_METHOD") or "LocalAP").strip()
    try:
        return getattr(WebRTCConnectionMethod, name)
    except AttributeError:
        valid = ", ".join(m.name for m in WebRTCConnectionMethod)
        raise Go2ConfigError(
            f"UNITREE_METHOD='{name}' inválido. Use: {valid}."
        ) from None


def create_connection() -> UnitreeWebRTCConnection:
    """Cria o UnitreeWebRTCConnection já com AES key e demais opções."""
    _load_env_file()
    method = _get_method()

    require = (os.environ.get("UNITREE_REQUIRE_AES") or "1").strip() != "0"
    kwargs: dict = {"aes_128_key": get_aes_key(required=require)}

    for env, arg in (
        ("UNITREE_IP", "ip"),
        ("UNITREE_SN", "serialNumber"),
        ("UNITREE_EMAIL", "username"),
        ("UNITREE_PASSWORD", "password"),
        ("UNITREE_REGION", "region"),
        ("UNITREE_DEVICE", "device_type"),
    ):
        value = (os.environ.get(env) or "").strip()
        if value:
            kwargs[arg] = value

    return UnitreeWebRTCConnection(method, **kwargs)
