"""Execution metadata only: no prompts, responses, secrets or hidden reasoning."""
from contextvars import ContextVar
from contextlib import contextmanager
import sqlite3
import uuid
import time
from datetime import datetime, timezone

current = ContextVar("trace", default=None)


def init(db):
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS traces (id INTEGER PRIMARY KEY, run TEXT, mode TEXT, node TEXT, status TEXT, timestamp TEXT, elapsed_ms INTEGER, provider TEXT)")


@contextmanager
def scope(db, mode, run=None):
    token = current.set((db, mode, run or uuid.uuid4().hex))
    try:
        yield current.get()[2]
    finally:
        current.reset(token)


def event(node, status, elapsed_ms=None, provider=None):
    trace = current.get()
    if not trace:
        return
    db, mode, run = trace
    with sqlite3.connect(db, timeout=5) as conn:
        conn.execute("INSERT INTO traces(run,mode,node,status,timestamp,elapsed_ms,provider) VALUES (?,?,?,?,?,?,?)",
                     (run, mode, node, status, datetime.now(timezone.utc).isoformat(), elapsed_ms, provider))


async def stage(node, operation):
    started = time.monotonic()
    event(node, "running")
    try:
        result = await operation
    except BaseException:
        event(node, "failed", round((time.monotonic()-started)*1000))
        raise
    event(node, "complete", round((time.monotonic()-started)*1000))
    return result
