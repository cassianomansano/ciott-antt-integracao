from __future__ import annotations
import dataclasses
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

from .models import DeclaracaoInput, DeclaracaoResponse


_DDL = """
CREATE TABLE IF NOT EXISTS operacoes (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    id_operacao                 TEXT NOT NULL UNIQUE,
    ciot_codigo                 TEXT,
    ciot_verificador            TEXT,
    tipo_operacao               INTEGER,
    status                      TEXT NOT NULL DEFAULT 'declarada',
    data_declaracao             TEXT,
    data_inicio_viagem          TEXT,
    data_fim_viagem             TEXT,
    data_limite_encerramento    TEXT,
    data_encerramento           TEXT,
    cpf_cnpj_contratado         TEXT,
    valor_frete                 REAL,
    protocolo                   TEXT,
    request_json                TEXT,
    response_json               TEXT,
    created_at                  TEXT NOT NULL,
    updated_at                  TEXT NOT NULL
)
"""


class CiotStorage:
    def __init__(self, db_path: str = "ciot_operacoes.db"):
        self._db_path = db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(_DDL)

    def registrar_declaracao(
        self, dados: DeclaracaoInput, resp: DeclaracaoResponse
    ) -> None:
        now = datetime.now().isoformat()
        # Prazo: 5 dias corridos a partir do início da viagem
        try:
            inicio = datetime.fromisoformat(dados.data_inicio_viagem)
            limite = (inicio + timedelta(days=5)).date().isoformat()
        except (ValueError, TypeError):
            limite = None

        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO operacoes (
                    id_operacao, ciot_codigo, ciot_verificador, tipo_operacao,
                    status, data_declaracao, data_inicio_viagem, data_fim_viagem,
                    data_limite_encerramento, cpf_cnpj_contratado, valor_frete,
                    protocolo, request_json, response_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'declarada', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dados.id_operacao,
                    resp.codigo_identificacao_operacao,
                    resp.codigo_verificador,
                    int(dados.tipo_operacao),
                    dados.data_declaracao,
                    dados.data_inicio_viagem,
                    dados.data_fim_viagem,
                    limite,
                    dados.cpf_cnpj_contratado,
                    dados.valor_frete,
                    resp.protocolo,
                    json.dumps(dataclasses.asdict(dados), ensure_ascii=False),
                    json.dumps(resp.__dict__, ensure_ascii=False),
                    now,
                    now,
                ),
            )

    def atualizar_status(
        self, id_operacao: str, status: str, protocolo: str = ""
    ) -> None:
        now = datetime.now().isoformat()
        extra = {}
        if status == "encerrada":
            extra["data_encerramento"] = now
        with self._conn() as conn:
            conn.execute(
                "UPDATE operacoes SET status=?, protocolo=?, updated_at=? WHERE id_operacao=?",
                (status, protocolo, now, id_operacao),
            )
            if extra:
                conn.execute(
                    "UPDATE operacoes SET data_encerramento=? WHERE id_operacao=?",
                    (now, id_operacao),
                )

    def listar_pendentes_encerramento(self, dias_aviso: int = 1) -> list[dict]:
        limite_alerta = (datetime.now() + timedelta(days=dias_aviso)).date().isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM operacoes
                WHERE status = 'declarada'
                  AND data_limite_encerramento IS NOT NULL
                  AND data_limite_encerramento <= ?
                ORDER BY data_limite_encerramento
                """,
                (limite_alerta,),
            ).fetchall()
        return [dict(r) for r in rows]

    def buscar_por_ciot(self, ciot_codigo: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM operacoes WHERE ciot_codigo = ?", (ciot_codigo,)
            ).fetchone()
        return dict(row) if row else None

    def buscar_por_id_operacao(self, id_operacao: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM operacoes WHERE id_operacao = ?", (id_operacao,)
            ).fetchone()
        return dict(row) if row else None

    def listar_todas(self, status: Optional[str] = None, limite: int = 200) -> list[dict]:
        """Lista todas as operações registradas, opcionalmente filtradas por status."""
        with self._conn() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM operacoes WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                    (status, limite),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM operacoes ORDER BY created_at DESC LIMIT ?",
                    (limite,),
                ).fetchall()
        return [dict(r) for r in rows]


