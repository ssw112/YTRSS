"""Runtime status tracking, backing the /status page.

The Aug 2026 outage went unnoticed for ~10 days because failures were
invisible. Everything the scheduler and summarizer do is recorded here.
"""
import json
import os
import threading
from datetime import datetime, timezone


class State:
    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        self.data = {
            "started_at": self._now(),
            "last_run_at": None,
            "last_run_result": None,   # "ok" | "error: ..." | "nothing_new"
            "last_success_at": None,   # last time an article was published
            "last_article": None,
            "runs": 0,
            "providers": {},           # label -> {last_ok, last_error, error_msg}
        }
        self._load()

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    saved = json.load(f)
                # keep persistent fields, refresh started_at
                for k in ("last_success_at", "last_article", "providers"):
                    if k in saved:
                        self.data[k] = saved[k]
            except Exception:
                pass

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w") as f:
                json.dump(self.data, f, indent=2)
        except Exception:
            pass

    def run_finished(self, result):
        with self._lock:
            self.data["last_run_at"] = self._now()
            self.data["last_run_result"] = result
            self.data["runs"] += 1
            self._save()

    def article_published(self, title):
        with self._lock:
            self.data["last_success_at"] = self._now()
            self.data["last_article"] = title
            self._save()

    def provider_ok(self, label):
        with self._lock:
            self.data["providers"].setdefault(label, {})["last_ok"] = self._now()
            self._save()

    def provider_fail(self, label, msg):
        with self._lock:
            p = self.data["providers"].setdefault(label, {})
            p["last_error"] = self._now()
            p["error_msg"] = msg
            self._save()

    def snapshot(self):
        with self._lock:
            return json.loads(json.dumps(self.data))
