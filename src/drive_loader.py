"""Carregamento das faturas — Google Drive (produção) ou pasta local (dev).

Estratégia:
  1. Se `st.secrets["gdrive"]["service_account"]` estiver configurado → usa Drive API.
  2. Senão, varre `data/raw/` no projeto (modo desenvolvimento).

Detecção do cartão:
  - Arquivos em `data/raw/<NOME_CARTAO>/...` herdam `cartao = NOME_CARTAO`.
  - No Drive: subpastas dentro da pasta principal funcionam do mesmo jeito.
  - Arquivos soltos na raiz usam `DEFAULT_CARTAO` (config.py).
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Iterable

import streamlit as st

from .config import DEFAULT_CARTAO, KNOWN_CARTOES, ROOT_DIR

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
LOCAL_DIR = ROOT_DIR / "data" / "raw"
SUPPORTED_EXTS = (".csv", ".xlsx", ".xls", ".ofx", ".pdf")


def _normalize_cartao(name: str | None) -> str:
    """Casa o nome do subdiretório com KNOWN_CARTOES (case-insensitive)."""
    if not name:
        return DEFAULT_CARTAO
    lower = name.strip().lower()
    for k in KNOWN_CARTOES:
        if k.lower() == lower:
            return k
    return name.strip() or DEFAULT_CARTAO


# ---------------------------------------------------------------------------
# Detecção de modo
# ---------------------------------------------------------------------------
def _has_drive_secrets() -> bool:
    try:
        sa = st.secrets["gdrive"]["service_account"]
        return bool(sa) and "client_email" in dict(sa)
    except (KeyError, FileNotFoundError, AttributeError):
        return False


# ---------------------------------------------------------------------------
# Modo Google Drive
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def _drive_service():
    from google.oauth2 import service_account  # imports tardios para iniciar app sem deps
    from googleapiclient.discovery import build

    creds_info = dict(st.secrets["gdrive"]["service_account"])
    creds = service_account.Credentials.from_service_account_info(
        creds_info, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _list_drive(folder_id: str) -> list[dict]:
    service = _drive_service()
    query = f"'{folder_id}' in parents and trashed = false"
    files: list[dict] = []
    page_token: str | None = None
    while True:
        resp = service.files().list(
            q=query,
            fields="nextPageToken, files(id, name, mimeType, modifiedTime)",
            pageToken=page_token,
            pageSize=200,
        ).execute()
        files.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return files


def _download_drive(file_id: str) -> bytes:
    from googleapiclient.http import MediaIoBaseDownload

    service = _drive_service()
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Modo local (fallback para desenvolvimento)
# ---------------------------------------------------------------------------
def _list_local() -> list[tuple[str, bytes, str]]:
    """Devolve [(nome, bytes, cartao), ...] varrendo `data/raw/` recursivamente.

    Cartão é o nome do subdiretório imediato dentro de `data/raw/`.
    Arquivos soltos na raiz usam DEFAULT_CARTAO.
    """
    out: list[tuple[str, bytes, str]] = []
    if not LOCAL_DIR.exists():
        return out
    for p in sorted(LOCAL_DIR.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in SUPPORTED_EXTS:
            continue
        # caminho relativo a data/raw/
        rel = p.relative_to(LOCAL_DIR)
        if len(rel.parts) >= 2:
            cartao = _normalize_cartao(rel.parts[0])
        else:
            cartao = DEFAULT_CARTAO
        out.append((p.name, p.read_bytes(), cartao))
    return out


def _list_drive_recursive(folder_id: str, cartao: str | None = None) -> list[tuple[str, bytes, str]]:
    """Varre a pasta do Drive recursivamente; subpastas viram `cartao`."""
    service = _drive_service()
    out: list[tuple[str, bytes, str]] = []
    items = _list_drive(folder_id)
    for it in items:
        if it["mimeType"] == "application/vnd.google-apps.folder":
            sub_cartao = _normalize_cartao(it["name"]) if cartao is None else cartao
            out.extend(_list_drive_recursive(it["id"], sub_cartao))
        else:
            name = it["name"]
            if any(name.lower().endswith(ext) for ext in SUPPORTED_EXTS):
                out.append((name, _download_drive(it["id"]), cartao or DEFAULT_CARTAO))
    return out


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300, show_spinner="Buscando faturas...")
def fetch_invoices(folder_id: str | None = None) -> list[tuple[str, bytes, str]]:
    """Retorna [(nome, bytes, cartao), ...] da fonte ativa (Drive ou local)."""
    if _has_drive_secrets():
        folder_id = folder_id or st.secrets["gdrive"]["folder_id"]
        return _list_drive_recursive(folder_id)
    return _list_local()


def filter_by_extension(
    files: Iterable[tuple],
    extensions: tuple[str, ...] = SUPPORTED_EXTS,
) -> list[tuple]:
    """Funciona com tuplas (name, bytes) ou (name, bytes, cartao)."""
    return [t for t in files if t[0].lower().endswith(extensions)]


def current_source() -> str:
    """Texto humano-legível para exibir na UI."""
    return "Google Drive" if _has_drive_secrets() else f"Pasta local ({LOCAL_DIR.name}/)"
