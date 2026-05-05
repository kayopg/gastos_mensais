"""Converte o JSON da Service Account do GCP em `.streamlit/secrets.toml`.

Uso:
    python scripts/json_to_secrets.py CAMINHO_DO_JSON [--folder-id ID_DA_PASTA]

Exemplos:
    python scripts/json_to_secrets.py "C:\\Users\\arima\\Downloads\\gastos-cartao-mensal-5c91c4ba9b10.json"
    python scripts/json_to_secrets.py ~/Downloads/sa.json --folder-id 19i_VwMuXWDGCkmFxkFftCP7ZPdcSsRum

O arquivo é gerado em `.streamlit/secrets.toml` (sobrescreve se existir).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_FOLDER_ID = "19i_VwMuXWDGCkmFxkFftCP7ZPdcSsRum"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SECRETS_PATH = PROJECT_ROOT / ".streamlit" / "secrets.toml"

# Campos esperados no JSON da SA (Google envia todos por padrão)
SA_FIELDS = [
    "type",
    "project_id",
    "private_key_id",
    "private_key",
    "client_email",
    "client_id",
    "auth_uri",
    "token_uri",
    "auth_provider_x509_cert_url",
    "client_x509_cert_url",
    "universe_domain",
]


def _toml_escape(value: str) -> str:
    """Escapa o valor para uma string TOML básica (entre aspas duplas)."""
    return (
        value
        .replace("\\", "\\\\")
        .replace("\"", "\\\"")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def build_toml(sa: dict, folder_id: str) -> str:
    out: list[str] = []
    out.append("# GERADO AUTOMATICAMENTE por scripts/json_to_secrets.py")
    out.append("# NAO commite este arquivo — .gitignore ja bloqueia.")
    out.append("")
    out.append("[gdrive]")
    out.append(f'folder_id = "{folder_id}"')
    out.append("")
    out.append("[gdrive.service_account]")
    for field in SA_FIELDS:
        if field not in sa:
            continue
        value = sa[field]
        out.append(f'{field} = "{_toml_escape(str(value))}"')
    out.append("")  # newline final
    return "\n".join(out)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("json_path", help="Caminho do arquivo JSON baixado do GCP")
    p.add_argument(
        "--folder-id", default=DEFAULT_FOLDER_ID,
        help=f"ID da pasta do Drive (default: {DEFAULT_FOLDER_ID})",
    )
    p.add_argument(
        "--print", action="store_true",
        help="Imprime no stdout em vez de gravar o arquivo (para inspeção)",
    )
    args = p.parse_args()

    json_path = Path(args.json_path).expanduser()
    if not json_path.exists():
        print(f"ERRO: arquivo nao encontrado: {json_path}", file=sys.stderr)
        return 1

    sa = json.loads(json_path.read_text(encoding="utf-8"))

    # Valida campos minimos
    missing = [f for f in ("type", "project_id", "private_key", "client_email") if f not in sa]
    if missing:
        print(f"ERRO: JSON nao parece ser uma SA do GCP. Campos faltando: {missing}", file=sys.stderr)
        return 2

    if sa.get("type") != "service_account":
        print(f"AVISO: type='{sa.get('type')}' (esperado 'service_account')", file=sys.stderr)

    toml = build_toml(sa, args.folder_id)

    if args.print:
        print(toml)
        return 0

    SECRETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SECRETS_PATH.write_text(toml, encoding="utf-8")

    print(f"OK escrito: {SECRETS_PATH}")
    print(f"  project_id   = {sa['project_id']}")
    print(f"  client_email = {sa['client_email']}")
    print(f"  folder_id    = {args.folder_id}")
    print()
    print("Proximo passo: rode `streamlit run app.py` (ou .\\run.bat) e confirme")
    print("que a sidebar mostra 'Fonte: Google Drive'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
