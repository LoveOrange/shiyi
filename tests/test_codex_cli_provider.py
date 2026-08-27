import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from shiyi import AIProviderRequest, CodexCLIProvider

EXPECTED_SUBPROCESS_CALLS = 2


class FakeProcess:
    def __init__(
        self,
        *,
        stdout: bytes,
        stderr: bytes = b"",
        returncode: int = 0,
        inputs: list[bytes | None] | None = None,
    ) -> None:
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode
        self._inputs = inputs

    async def communicate(
        self,
        input: bytes | None = None,  # noqa: A002
    ) -> tuple[bytes, bytes]:
        if self._inputs is not None:
            self._inputs.append(input)
        return self._stdout, self._stderr

    def kill(self) -> None:
        return None


def test_codex_cli_provider_uses_subscription_guard_and_hardened_structured_exec(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[tuple[str, ...], dict[str, object]]] = []
    inputs: list[bytes | None] = []
    response: dict[str, Any] = {"items": []}

    async def fake_create_subprocess_exec(
        *command: str,
        **options: object,
    ) -> FakeProcess:
        calls.append((command, options))
        if command[1:] == ("login", "status"):
            return FakeProcess(stdout=b"Logged in using ChatGPT\n")
        schema_path = Path(command[command.index("--output-schema") + 1])
        assert json.loads(schema_path.read_text()) == {"type": "object"}
        return FakeProcess(stdout=json.dumps(response).encode(), inputs=inputs)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setenv("SHIYI_MONGO_URI", "mongodb://private.example")
    provider = CodexCLIProvider()

    result = asyncio.run(
        provider.complete(
            AIProviderRequest(prompt="input content", output_schema={"type": "object"})
        )
    )

    assert result == response
    assert len(calls) == EXPECTED_SUBPROCESS_CALLS
    command, options = calls[1]
    assert command[:2] == ("codex", "exec")
    assert "--ephemeral" in command
    assert 'web_search="disabled"' in command
    assert 'default_permissions="shiyi_ai"' in command
    environment = options["env"]
    assert isinstance(environment, dict)
    assert environment.get("SHIYI_MONGO_URI") is None
    assert inputs == [b"input content"]


def test_codex_cli_provider_refuses_non_chatgpt_authentication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_create_subprocess_exec(
        *_command: str,
        **_options: object,
    ) -> FakeProcess:
        return FakeProcess(stdout=b"Logged in using an API key\n")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    provider = CodexCLIProvider()

    with pytest.raises(RuntimeError, match="refusing to risk API-key billing"):
        asyncio.run(
            provider.complete(
                AIProviderRequest(prompt="input content", output_schema={"type": "object"})
            )
        )
