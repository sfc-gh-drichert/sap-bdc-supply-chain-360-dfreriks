"""
Shared Snowflake connection helper for the deploy scripts and tools.

Resolution order:
  1. Environment variables (used by GitHub Actions):
       SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, and one of
       SNOWFLAKE_PRIVATE_KEY (PEM text) or SNOWFLAKE_PRIVATE_KEY_PATH;
       optional SNOWFLAKE_PRIVATE_KEY_PASSPHRASE, SNOWFLAKE_ROLE, SNOWFLAKE_WAREHOUSE.
  2. A named key-pair connection in ~/.snowflake/connections.toml (local use).
"""
import os

import snowflake.connector
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization


def _der(pem: bytes, passphrase: str | None) -> bytes:
    pk = serialization.load_pem_private_key(
        pem, password=passphrase.encode() if passphrase else None, backend=default_backend())
    return pk.private_bytes(serialization.Encoding.DER,
                            serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption())


def connect(conn_name: str | None = None, **kw):
    """Open a connection from env vars, or from connections.toml when conn_name is given."""
    if conn_name is None and os.environ.get("SNOWFLAKE_ACCOUNT"):
        pem = os.environ.get("SNOWFLAKE_PRIVATE_KEY")
        if pem:
            key = pem.replace("\\n", "\n").encode()
        else:
            with open(os.path.expanduser(os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"]), "rb") as f:
                key = f.read()
        kw.setdefault("warehouse", os.environ.get("SNOWFLAKE_WAREHOUSE") or None)
        return snowflake.connector.connect(
            account=os.environ["SNOWFLAKE_ACCOUNT"],
            user=os.environ["SNOWFLAKE_USER"],
            private_key=_der(key, os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")),
            role=os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
            **{k: v for k, v in kw.items() if v is not None})

    if not conn_name:
        raise SystemExit("No connection: set SNOWFLAKE_ACCOUNT/USER/PRIVATE_KEY env vars "
                         "or pass a connections.toml connection name.")
    import tomllib
    with open(os.path.expanduser("~/.snowflake/connections.toml"), "rb") as f:
        cfg = tomllib.load(f)[conn_name]
    with open(os.path.expanduser(cfg["private_key_path"]), "rb") as f:
        key = f.read()
    return snowflake.connector.connect(
        account=cfg["account"], user=cfg["user"],
        private_key=_der(key, cfg.get("private_key_passphrase")),
        role=cfg.get("role", "ACCOUNTADMIN"), **kw)
