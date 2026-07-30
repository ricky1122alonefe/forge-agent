"""SQLiteTaskStore — persistent TaskRun storage.

Reuses ``SQLiteConnection`` (WAL mode, busy_timeout, lazy connection).
Stores each TaskRun as a single row with JSON-serialised dict fields.

S3.1 — concrete implementation of the ``TaskStore`` protocol.
"""

from __future__ import annotations

import json
from typing import Any

from forge_agent.runtime.models import TaskRun
from forge_agent.storage.base import SQLiteConnection


class SQLiteTaskStore(SQLiteConnection):
    """SQLite-backed TaskStore. One row per TaskRun."""

    def _default_db_name(self) -> str:
        return "forge_tasks.db"

    def _ensure_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS task_runs (
                run_id         TEXT PRIMARY KEY,
                pipeline_id    TEXT NOT NULL,
                tenant_id      TEXT NOT NULL DEFAULT 'default',
                project_id     TEXT NOT NULL DEFAULT 'default',
                payload        TEXT NOT NULL DEFAULT '{}',
                status         TEXT NOT NULL DEFAULT 'pending',
                result         TEXT,
                error          TEXT,
                attempts       INTEGER NOT NULL DEFAULT 0,
                max_attempts   INTEGER NOT NULL DEFAULT 3,
                trigger_source TEXT NOT NULL DEFAULT 'manual',
                trigger_id     TEXT,
                callback_url   TEXT,
                created_at     TEXT NOT NULL,
                started_at     TEXT,
                finished_at    TEXT,
                metadata       TEXT NOT NULL DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_task_status     ON task_runs(status);
            CREATE INDEX IF NOT EXISTS idx_task_tenant     ON task_runs(tenant_id);
            CREATE INDEX IF NOT EXISTS idx_task_pipeline   ON task_runs(pipeline_id);
            CREATE INDEX IF NOT EXISTS idx_task_created    ON task_runs(created_at);
            """
        )
        self.conn.commit()

    # -- TaskStore protocol ------------------------------------------------

    def create(self, run: TaskRun) -> None:
        self.execute(
            """
            INSERT INTO task_runs
                (run_id, pipeline_id, tenant_id, project_id, payload, status,
                 result, error, attempts, max_attempts, trigger_source,
                 trigger_id, callback_url, created_at, started_at,
                 finished_at, metadata)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                run.run_id,
                run.pipeline_id,
                run.tenant_id,
                run.project_id,
                json.dumps(run.payload, ensure_ascii=False),
                run.status,
                json.dumps(run.result, ensure_ascii=False) if run.result else None,
                run.error,
                run.attempts,
                run.max_attempts,
                run.trigger_source,
                run.trigger_id,
                run.callback_url,
                run.created_at,
                run.started_at,
                run.finished_at,
                json.dumps(run.metadata, ensure_ascii=False),
            ),
        )
        self.commit()

    def get(self, run_id: str) -> TaskRun | None:
        row = self.execute("SELECT * FROM task_runs WHERE run_id = ?", (run_id,)).fetchone()
        return self._row_to_run(row) if row else None

    def update(self, run: TaskRun) -> None:
        self.execute(
            """
            UPDATE task_runs SET
                status = ?, result = ?, error = ?, attempts = ?,
                started_at = ?, finished_at = ?, metadata = ?
            WHERE run_id = ?
            """,
            (
                run.status,
                json.dumps(run.result, ensure_ascii=False) if run.result else None,
                run.error,
                run.attempts,
                run.started_at,
                run.finished_at,
                json.dumps(run.metadata, ensure_ascii=False),
                run.run_id,
            ),
        )
        self.commit()

    def list(
        self,
        *,
        tenant_id: str | None = None,
        project_id: str | None = None,
        pipeline_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[TaskRun]:
        clauses: list[str] = []
        params: list[Any] = []
        if tenant_id:
            clauses.append("tenant_id = ?")
            params.append(tenant_id)
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        if pipeline_id:
            clauses.append("pipeline_id = ?")
            params.append(pipeline_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM task_runs {where} ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self.execute(sql, tuple(params)).fetchall()
        return [self._row_to_run(r) for r in rows]

    def list_by_status(self, status: str) -> list[TaskRun]:
        rows = self.execute(
            "SELECT * FROM task_runs WHERE status = ? ORDER BY created_at",
            (status,),
        ).fetchall()
        return [self._row_to_run(r) for r in rows]

    def delete(self, run_id: str) -> bool:
        cur = self.execute("DELETE FROM task_runs WHERE run_id = ?", (run_id,))
        self.commit()
        return cur.rowcount > 0

    # -- internal ----------------------------------------------------------

    @staticmethod
    def _row_to_run(row: tuple) -> TaskRun:
        (
            run_id,
            pipeline_id,
            tenant_id,
            project_id,
            payload,
            status,
            result,
            error,
            attempts,
            max_attempts,
            trigger_source,
            trigger_id,
            callback_url,
            created_at,
            started_at,
            finished_at,
            metadata,
        ) = row
        return TaskRun(
            run_id=run_id,
            pipeline_id=pipeline_id,
            tenant_id=tenant_id,
            project_id=project_id,
            payload=json.loads(payload) if payload else {},
            status=status,
            result=json.loads(result) if result else None,
            error=error,
            attempts=attempts,
            max_attempts=max_attempts,
            trigger_source=trigger_source,
            trigger_id=trigger_id,
            callback_url=callback_url,
            created_at=created_at,
            started_at=started_at,
            finished_at=finished_at,
            metadata=json.loads(metadata) if metadata else {},
        )
