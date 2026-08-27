"""Codex CLI implementation of the provider-neutral AI port."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from shiyi.ports.ai_provider import AIProviderRequest

DEFAULT_CODEX_TIMEOUT_SECONDS = 300.0
ERROR_MESSAGE_LIMIT = 1_000


class CodexCLIProvider:
    """Runs structured enrichment through a trusted local ChatGPT Codex login."""

    name = "codex-cli"

    def __init__(
        self,
        *,
        executable: str = "codex",
        timeout_seconds: float = DEFAULT_CODEX_TIMEOUT_SECONDS,
        require_chatgpt_login: bool = True,
    ) -> None:
        """Configure the local executable and fail-closed execution timeout."""
        if timeout_seconds <= 0:
            msg = "timeout_seconds must be greater than zero"
            raise ValueError(msg)
        self._executable = executable
        self._timeout_seconds = timeout_seconds
        self._require_chatgpt_login = require_chatgpt_login

    async def complete(self, request: AIProviderRequest) -> dict[str, Any]:
        """Execute one ephemeral, schema-constrained Codex CLI request."""
        with TemporaryDirectory(prefix="shiyi-codex-") as temporary_directory:
            workspace = Path(temporary_directory)
            environment = _codex_environment(workspace)
            if self._require_chatgpt_login:
                await self._assert_chatgpt_login(workspace=workspace, environment=environment)

            schema_path = workspace / "output-schema.json"
            schema_path.write_text(
                json.dumps(request.output_schema, ensure_ascii=False),
                encoding="utf-8",
            )
            command = self._completion_command(workspace=workspace, schema_path=schema_path)
            stdout, stderr, returncode = await self._run(
                command,
                workspace=workspace,
                environment=environment,
                stdin=request.prompt.encode(),
            )
            if returncode != 0:
                raise RuntimeError(_command_error("Codex CLI enrichment failed", stderr))
            try:
                decoded = json.loads(stdout)
            except json.JSONDecodeError as error:
                msg = "Codex CLI returned invalid JSON"
                raise ValueError(msg) from error
            if not isinstance(decoded, dict):
                msg = "Codex CLI returned a non-object JSON value"
                raise TypeError(msg)
            return decoded

    async def _assert_chatgpt_login(
        self,
        *,
        workspace: Path,
        environment: dict[str, str],
    ) -> None:
        stdout, stderr, returncode = await self._run(
            (self._executable, "login", "status"),
            workspace=workspace,
            environment=environment,
        )
        status = f"{stdout}\n{stderr}"
        if returncode != 0:
            raise RuntimeError(_command_error("Unable to check Codex CLI login", status))
        if "using ChatGPT" not in status:
            msg = (
                "Codex CLI is not logged in with ChatGPT; refusing to risk API-key billing. "
                "Run `codex login` and choose ChatGPT authentication."
            )
            raise RuntimeError(msg)

    def _completion_command(self, *, workspace: Path, schema_path: Path) -> tuple[str, ...]:
        return (
            self._executable,
            "exec",
            "--ephemeral",
            "--skip-git-repo-check",
            "--ignore-user-config",
            "--ignore-rules",
            "--strict-config",
            "--color",
            "never",
            "--cd",
            str(workspace),
            "--config",
            'approval_policy="never"',
            "--config",
            'web_search="disabled"',
            "--config",
            'shell_environment_policy.inherit="none"',
            "--config",
            'default_permissions="shiyi_ai"',
            "--config",
            'permissions.shiyi_ai.filesystem={":minimal"="read",":workspace_roots"={"."="read"}}',
            "--config",
            "permissions.shiyi_ai.network.enabled=false",
            "--output-schema",
            str(schema_path),
            "-",
        )

    async def _run(
        self,
        command: tuple[str, ...],
        *,
        workspace: Path,
        environment: dict[str, str],
        stdin: bytes | None = None,
    ) -> tuple[str, str, int]:
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=workspace,
                env=environment,
                stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as error:
            msg = f"Codex CLI executable not found: {self._executable}"
            raise RuntimeError(msg) from error
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=stdin),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as error:
            process.kill()
            await process.communicate()
            msg = f"Codex CLI timed out after {self._timeout_seconds:g} seconds"
            raise TimeoutError(msg) from error
        returncode = process.returncode
        if returncode is None:
            msg = "Codex CLI process did not report an exit status"
            raise RuntimeError(msg)
        return stdout.decode(errors="replace"), stderr.decode(errors="replace"), returncode


def _codex_environment(workspace: Path) -> dict[str, str]:
    environment: dict[str, str] = {
        "PATH": os.environ.get("PATH", os.defpath),
        "TMPDIR": str(workspace),
    }
    for name in ("HOME", "CODEX_HOME", "LANG", "LC_ALL", "LOGNAME", "USER"):
        if value := os.environ.get(name):
            environment[name] = value
    return environment


def _command_error(prefix: str, output: str) -> str:
    detail = output.strip()[-ERROR_MESSAGE_LIMIT:]
    return f"{prefix}: {detail}" if detail else prefix
