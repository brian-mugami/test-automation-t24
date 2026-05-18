"""Read-only Locust scenarios for the T24 demo environment.

This file is intentionally independent from the Selenium functional tests.
It defaults to safe GET probes and can optionally submit a login form when
explicitly enabled through environment variables.
"""
import os
from urllib.parse import urlparse

from locust import HttpUser, between, task


def _env_float(name, default):
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _paths_from_env():
    raw = os.getenv("PERF_PATHS", "").strip()
    if not raw:
        return ["/"]
    paths = []
    for item in raw.splitlines():
        item = item.strip()
        if not item:
            continue
        parsed = urlparse(item)
        if parsed.scheme and parsed.netloc:
            path = parsed.path or "/"
            if parsed.query:
                path = f"{path}?{parsed.query}"
            paths.append(path)
        else:
            paths.append(item if item.startswith("/") else f"/{item}")
    return paths or ["/"]


class T24ReadOnlyUser(HttpUser):
    """Safe HTTP-level probes for T24 pages/endpoints."""

    wait_time = between(
        _env_float("PERF_MIN_WAIT", 1.0),
        _env_float("PERF_MAX_WAIT", 3.0),
    )

    def on_start(self):
        self.paths = _paths_from_env()
        if os.getenv("PERF_LOGIN_ENABLED", "0") != "1":
            return

        username = os.getenv("PERF_LOGIN_USER", "")
        password = os.getenv("PERF_LOGIN_PASS", "")
        login_path = os.getenv(
            "PERF_LOGIN_PATH",
            "/BrowserWeb/servlet/BrowserLoginServlet",
        )
        if username and password:
            self.client.post(
                login_path,
                data={
                    "signOnName": username,
                    "password": password,
                    "sign-in": "Sign in",
                },
                name="POST login form",
                catch_response=False,
            )

    @task
    def read_only_probe(self):
        for path in self.paths:
            self.client.get(path, name=f"GET {path}", catch_response=False)
