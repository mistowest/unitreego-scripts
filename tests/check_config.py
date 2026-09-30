"""
Valida a configuração da conexão SEM conectar ao robô e SEM imprimir a chave.

    python tests/check_config.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.go2_connection import (  # noqa: E402
    ENV_FILE,
    Go2ConfigError,
    create_connection,
    get_aes_key,
)

print("Arquivo .env:", "encontrado" if ENV_FILE.is_file() else "NÃO encontrado")

try:
    key = get_aes_key(required=False)
    if key:
        print(f"UNITREE_AES_KEY: OK ({len(key)} chars hex, valor oculto)")
    else:
        print("UNITREE_AES_KEY: não definida (ok só com UNITREE_REQUIRE_AES=0)")
    conn = create_connection()
    print("Conexão criada:", type(conn).__name__, "| método:", conn.connectionMethod.name)
except Go2ConfigError as exc:
    print("ERRO DE CONFIGURAÇÃO:\n" + str(exc))
    sys.exit(1)
