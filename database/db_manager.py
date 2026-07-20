"""
database/db_manager.py
Gerenciador central do banco de dados SQLite do AURA.
Inicializa tabelas e oferece conexão thread-safe.
"""

import sqlite3
import os
import threading
from core.logger import setup_logger

logger = setup_logger("database")

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database")
DB_PATH = os.path.join(DB_DIR, "aura.db")


class DatabaseManager:
    """
    Gerencia conexão SQLite com suporte a múltiplas threads.
    Usa check_same_thread=False + lock manual para segurança.
    """

    def __init__(self, db_path: str = DB_PATH):
        os.makedirs(DB_DIR, exist_ok=True)
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # WAL mode: leitores não bloqueiam escritores. Essencial para
        # uso concorrente real (chat + monitor + memórias simultâneas).
        # Sem WAL, um SELECT pode bloquear um INSERT em outra thread.
        self._conn.execute("PRAGMA journal_mode=WAL")
        # 5s de timeout para contenção EXTERNA (outra ferramenta
        # abrindo o .db pra inspecionar, backup em andamento).
        self._conn.execute("PRAGMA busy_timeout = 5000")
        # synchronous=NORMAL: segurança + performance. FULL seria
        # mais seguro mas 2-3x mais lento em writes.
        self._conn.execute("PRAGMA synchronous=NORMAL")
        # Cache de 32MB para queries frequentes
        self._conn.execute("PRAGMA cache_size = -32768")
        self._init_tables()
        logger.info(f"Banco de dados iniciado (WAL): {db_path}")

    def _init_tables(self) -> None:
        """Cria todas as tabelas necessárias."""
        sql_statements = [
            # Memória permanente — inclui campos de importância e rastreamento de acesso
            """CREATE TABLE IF NOT EXISTS memory_permanent (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                categoria    TEXT    NOT NULL,
                chave        TEXT    NOT NULL UNIQUE,
                valor        TEXT    NOT NULL,
                importance   INTEGER NOT NULL DEFAULT 5,
                access_count INTEGER NOT NULL DEFAULT 0,
                last_access  TIMESTAMP,
                criado_em    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",

            # Memória de procedimentos — importance opcional
            """CREATE TABLE IF NOT EXISTS memory_procedures (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                nome        TEXT    NOT NULL UNIQUE,
                descricao   TEXT,
                passos      TEXT    NOT NULL,
                uso_count   INTEGER DEFAULT 0,
                importance  INTEGER NOT NULL DEFAULT 5,
                criado_em   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",

            # Histórico de conversas (memória temporária persistida)
            """CREATE TABLE IF NOT EXISTS chat_history (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                role       TEXT    NOT NULL,
                content    TEXT    NOT NULL,
                sessao_id  TEXT,
                criado_em  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",

            # Tarefas
            """CREATE TABLE IF NOT EXISTS tasks (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo       TEXT NOT NULL,
                descricao    TEXT,
                status       TEXT DEFAULT 'pendente',
                prioridade   INTEGER DEFAULT 2,
                agendado_em  TIMESTAMP,
                repeticao    TEXT,
                criado_em    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                concluido_em TIMESTAMP
            )""",

            # Log de ações executadas
            """CREATE TABLE IF NOT EXISTS action_log (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                acao         TEXT    NOT NULL,
                parametros   TEXT,
                resultado    TEXT,
                sucesso      INTEGER DEFAULT 1,
                executado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
        ]

        with self._lock:
            cursor = self._conn.cursor()
            for sql in sql_statements:
                cursor.execute(sql)
            self._conn.commit()

        # Migração não-destrutiva: adiciona colunas novas em tabelas já existentes
        self._migrate()

    def _migrate(self) -> None:
        """
        Aplica migrações de schema de forma segura e idempotente.
        Adiciona colunas ausentes sem perder dados existentes.
        """
        # Nova tabela: biblioteca de fluxos com métricas
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS flow_library (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                nome          TEXT    NOT NULL UNIQUE,
                descricao     TEXT,
                passos        TEXT    NOT NULL,
                contexto      TEXT,
                prioridade    REAL    NOT NULL DEFAULT 5.0,
                taxa_sucesso  REAL    NOT NULL DEFAULT 1.0,
                tempo_medio   REAL    NOT NULL DEFAULT 0.0,
                uso_count     INTEGER NOT NULL DEFAULT 0,
                erro_count    INTEGER NOT NULL DEFAULT 0,
                importancia   INTEGER NOT NULL DEFAULT 5,
                criado_em     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ultimo_uso    TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS execution_log (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                flow_nome     TEXT,
                objetivo      TEXT,
                passos_json   TEXT,
                sucesso       INTEGER DEFAULT 1,
                tempo_s       REAL    DEFAULT 0.0,
                erro_msg      TEXT,
                corrigido     INTEGER DEFAULT 0,
                executado_em  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS error_corrections (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                gatilho_padrao  TEXT    NOT NULL,
                acao_errada     TEXT,
                parametros_errados TEXT,
                erro_msg        TEXT,
                acao_correta    TEXT,
                parametros_corretos TEXT,
                vezes_evitado   INTEGER NOT NULL DEFAULT 0,
                criado_em       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ultima_aplicacao TIMESTAMP
            );
        """)
        self._conn.commit()

        migrations = [
            # memory_permanent — campos de importância
            ("memory_permanent", "importance",    "INTEGER NOT NULL DEFAULT 5"),
            ("memory_permanent", "access_count",  "INTEGER NOT NULL DEFAULT 0"),
            ("memory_permanent", "last_access",   "TIMESTAMP"),
            # memory_procedures — importance opcional
            ("memory_procedures", "importance",   "INTEGER NOT NULL DEFAULT 5"),
        ]

        with self._lock:
            cursor = self._conn.cursor()
            for table, column, definition in migrations:
                # Verifica se a coluna já existe antes de adicionar
                cursor.execute(f"PRAGMA table_info({table})")
                existing = {row[1] for row in cursor.fetchall()}
                if column not in existing:
                    cursor.execute(
                        f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
                    )
                    logger.info(f"Migração: coluna '{column}' adicionada em '{table}'")
            self._conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Executa um comando SQL com lock thread-safe."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            return cursor

    def fetchall(self, sql: str, params: tuple = ()) -> list:
        """Retorna todos os resultados de uma query."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]

    def fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        """Retorna o primeiro resultado de uma query."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            row = cursor.fetchone()
            return dict(row) if row else None

    def close(self) -> None:
        self._conn.close()
        logger.info("Banco de dados fechado.")


# Instância global
db = DatabaseManager()
