"""
core/logger.py
Sistema de logging centralizado do AURA.
"""

import glob
import logging
import os
import time
from datetime import datetime


LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
LOG_RETENTION_DAYS = 30
os.makedirs(LOG_DIR, exist_ok=True)

_cleanup_done = False


def _cleanup_old_logs(retention_days: int = LOG_RETENTION_DAYS, log_dir: str = None) -> int:
    """
    Remove arquivos de log mais velhos que retention_days. Um arquivo
    novo por dia sem limpeza vira milhares de arquivos ao longo de anos
    de uso real (a própria filosofia do projeto: pensar na V20, não só
    na versão atual). Roda uma vez por processo, não a cada logger
    criado — não tem sentido escanear o diretório dezenas de vezes na
    mesma inicialização.
    """
    log_dir = log_dir or LOG_DIR
    removed = 0
    cutoff = time.time() - (retention_days * 86400)
    for path in glob.glob(os.path.join(log_dir, "aura_*.log")):
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
                removed += 1
        except OSError:
            continue
    return removed


def setup_logger(name: str, level=logging.DEBUG) -> logging.Logger:
    """
    Cria e configura um logger com saída para console e arquivo.

    Args:
        name: Nome do módulo/logger.
        level: Nível de logging (default: DEBUG).

    Returns:
        Logger configurado.
    """
    global _cleanup_done
    if not _cleanup_done:
        _cleanup_done = True
        try:
            n = _cleanup_old_logs()
            if n:
                logging.getLogger("logger").info(f"Limpeza: {n} log(s) antigo(s) removido(s)")
        except Exception:
            pass  # limpeza de log nunca deve impedir o app de iniciar

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler console
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # Handler arquivo
    log_file = os.path.join(LOG_DIR, f"aura_{datetime.now().strftime('%Y%m%d')}.log")
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger
