"""
updater/downloader.py
====================
Download de atualizações com progresso, retry, checksum SHA256.

API:
  download_release(url, dest_dir, on_progress=None) → Path
  verify_checksum(filepath, expected_sha256) → bool

Thread-safe: downloads rodam em QThread para não travar a UI.
"""

import hashlib
import os
import tempfile
import threading
from pathlib import Path
from typing import Callable, Optional

import requests

from core.logger import setup_logger

logger = setup_logger("updater.downloader")

_USER_AGENT = "AURA-V11-Updater/1.0"
_CHUNK_SIZE = 8192  # 8KB chunks para download
_MAX_RETRIES = 3


def sha256_file(filepath: str) -> str:
    """Calcula SHA256 de um arquivo."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK_SIZE * 8), b""):
            h.update(chunk)
    return h.hexdigest()


def download_release(
    url: str,
    dest_dir: str,
    on_progress: Optional[Callable[[int, int], None]] = None,
    expected_sha256: Optional[str] = None,
    timeout: int = 600,
) -> Optional[str]:
    """
    Baixa um arquivo com barra de progresso e verificação opcional.

    Args:
        url:            URL do arquivo a baixar
        dest_dir:       Diretório de destino
        on_progress:    Callback (bytes_recebidos, bytes_total)
        expected_sha256: SHA256 esperado para verificação pós-download
        timeout:        Timeout em segundos

    Returns:
        Caminho do arquivo baixado, ou None se falhou.
    """
    os.makedirs(dest_dir, exist_ok=True)
    filename = _extract_filename(url)
    dest_path = os.path.join(dest_dir, filename)

    # Se já existe e passou na verificação, pula
    if os.path.exists(dest_path) and expected_sha256:
        actual = sha256_file(dest_path)
        if actual == expected_sha256:
            logger.info(f"Arquivo já existe e checksum OK: {dest_path}")
            return dest_path

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            logger.info(f"Download: {url} (tentativa {attempt}/{_MAX_RETRIES})")

            headers = {"User-Agent": _USER_AGENT}

            # Suporte a resumo se o download anterior foi parcial
            resume_pos = 0
            if attempt > 1 and os.path.exists(dest_path):
                resume_pos = os.path.getsize(dest_path)
                headers["Range"] = f"bytes={resume_pos}-"

            resp = requests.get(
                url,
                headers=headers,
                stream=True,
                timeout=(30, timeout),
                allow_redirects=True,
            )
            resp.raise_for_status()

            # Tamanho total (pode ser None se servidor não informar)
            total_size = int(resp.headers.get("content-length", 0))
            if resume_pos and resp.status_code == 206:
                total_size += resume_pos

            mode = "ab" if resume_pos else "wb"
            downloaded = resume_pos

            with open(dest_path, mode) as f:
                for chunk in resp.iter_content(chunk_size=_CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if on_progress and total_size > 0:
                            on_progress(downloaded, total_size)

            # Verifica checksum
            if expected_sha256:
                actual = sha256_file(dest_path)
                if actual != expected_sha256:
                    logger.error(
                        f"Checksum inválido: esperado={expected_sha256[:16]}..., "
                        f"recebido={actual[:16]}..."
                    )
                    os.remove(dest_path)
                    continue  # tenta de novo

            logger.info(f"Download concluído: {dest_path} ({downloaded} bytes)")
            return dest_path

        except requests.exceptions.ConnectionError:
            logger.warning(f"Erro de conexão na tentativa {attempt}")
            if attempt == _MAX_RETRIES:
                return None
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout na tentativa {attempt}")
            if attempt == _MAX_RETRIES:
                return None
        except Exception as e:
            logger.error(f"Erro no download: {e}")
            return None

    return None


def _extract_filename(url: str) -> str:
    """Extrai nome do arquivo da URL."""
    from urllib.parse import urlparse, unquote
    parsed = urlparse(url)
    path = unquote(parsed.path)
    filename = os.path.basename(path)
    if not filename or "." not in filename:
        filename = "aura_update.zip"
    return filename


class DownloadThread(threading.Thread):
    """
    Thread de download com callback de progresso.

    Uso:
        thread = DownloadThread(url, dest, on_progress=callback)
        thread.start()
        thread.join()  # ou conectar thread.finished
    """

    def __init__(
        self,
        url: str,
        dest_dir: str,
        on_progress: Optional[Callable[[int, int], None]] = None,
        on_finished: Optional[Callable[[Optional[str]], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        expected_sha256: Optional[str] = None,
    ):
        super().__init__(daemon=True)
        self.url = url
        self.dest_dir = dest_dir
        self.on_progress = on_progress
        self.on_finished = on_finished
        self.on_error = on_error
        self.expected_sha256 = expected_sha256
        self.result: Optional[str] = None

    def run(self):
        try:
            self.result = download_release(
                self.url,
                self.dest_dir,
                on_progress=self.on_progress,
                expected_sha256=self.expected_sha256,
            )
            if self.result and self.on_finished:
                self.on_finished(self.result)
            elif not self.result and self.on_error:
                self.on_error("Download falhou após múltiplas tentativas")
        except Exception as e:
            if self.on_error:
                self.on_error(str(e))
