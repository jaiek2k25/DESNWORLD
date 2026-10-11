"""Error handling tests: credentials, malformed JSON, rate limits, timeouts, CLI."""

from __future__ import annotations

import json
from types import SimpleNamespace

try:  # openai>=3 uses the httpx2 transport package
    import httpx2 as httpx
except ImportError:  # pragma: no cover - openai 1.x/2.x era
    import httpx  # type: ignore[no-redef]
import openai
import pytest

from desnworld.cli import main as cli_main
from desnworld.config import Config
from desnworld.engine import ScenarioEngine
from desnworld.errors import (
    InputValidationError,
    MalformedResponseError,
    MissingCredentialsError,
    ProviderError,
    ProviderTimeoutError,
    RateLimitError,
    SchemaValidationError,
)
from desnworld.llm_client import LLMClient, _map_provider_error, parse_json_response
from desnworld.providers import MockScenarioProvider, ScriptedProvider
from desnworld.retry import retry_with_backoff


def _fake_response(content, finish_reason="stop"):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason=finish_reason,
                message=SimpleNamespace(content=content),
            )
        ]
    )


class TestMissingCredentials:
    def test_llm_client_requires_api_key(self):
        with pytest.raises(MissingCredentialsError):
            LLMClient(api_key="")

    def test_config_validate_reports_missing_key(self, monkeypatch):
        monkeypatch.setattr(Config, "LLM_API_KEY", None)
        problems = Config.validate(require_llm=True)
        assert any("LLM_API_KEY" in p for p in problems)

    def test_config_validate_without_llm(self, monkeypatch):
        monkeypatch.setattr(Config, "LLM_API_KEY", None)
        assert Config.validate(require_llm=False) == []

    def test_error_payload_code(self):
        exc = MissingCredentialsError("no key", hint="set LLM_API_KEY")
        assert exc.to_payload() == {
            "error": "missing_credentials",
            "message": "no key",
            "hint": "set LLM_API_KEY",
        }


class TestJSONParsing:
    def test_valid_json_object(self):
        assert parse_json_response(_fake_response('{"a": 1}')) == {"a": 1}

    def test_markdown_fence_is_stripped(self):
        content = '```json\n{"a": 1}\n```'
        assert parse_json_response(_fake_response(content)) == {"a": 1}

    def test_trailing_prose_is_tolerated(self):
        content = '{"a": 1}\nI hope this helps!'
        assert parse_json_response(_fake_response(content)) == {"a": 1}

    def test_multiple_json_values_rejected(self):
        content = '{"a": 1} {"b": 2}'
        with pytest.raises(MalformedResponseError):
            parse_json_response(_fake_response(content))

    def test_truncated_json_rejected_not_repaired(self):
        content = '{"a": 1, "b": {"nested": tru'
        with pytest.raises(MalformedResponseError):
            parse_json_response(_fake_response(content))

    def test_empty_content_rejected(self):
        with pytest.raises(MalformedResponseError):
            parse_json_response(_fake_response("   "))

    def test_length_finish_reason_rejected(self):
        with pytest.raises(MalformedResponseError) as exc:
            parse_json_response(_fake_response('{"a": 1}', finish_reason="length"))
        assert exc.value.finish_reason == "length"

    def test_top_level_array_rejected(self):
        with pytest.raises(MalformedResponseError):
            parse_json_response(_fake_response('[1, 2, 3]'))

    def test_no_choices_rejected(self):
        with pytest.raises(MalformedResponseError):
            parse_json_response(SimpleNamespace(choices=[]))


class TestProviderErrorMapping:
    def _request(self):
        return httpx.Request("POST", "https://api.example.com/v1/chat/completions")

    def test_rate_limit_maps_to_rate_limit_error(self):
        response = httpx.Response(429, request=self._request())
        error = openai.RateLimitError("slow down", response=response, body=None)
        mapped = _map_provider_error(error)
        assert isinstance(mapped, RateLimitError)
        assert mapped.to_payload()["error"] == "rate_limit_error"

    def test_timeout_maps_to_provider_timeout(self):
        error = openai.APITimeoutError(request=self._request())
        mapped = _map_provider_error(error)
        assert isinstance(mapped, ProviderTimeoutError)
        assert mapped.to_payload()["error"] == "provider_timeout"

    def test_auth_error_maps_to_missing_credentials(self):
        response = httpx.Response(401, request=self._request())
        error = openai.AuthenticationError("bad key", response=response, body=None)
        mapped = _map_provider_error(error)
        assert isinstance(mapped, MissingCredentialsError)

    def test_connection_error_maps_to_provider_error(self):
        error = openai.APIConnectionError(message="nope", request=self._request())
        mapped = _map_provider_error(error)
        assert isinstance(mapped, ProviderError)

    def test_unknown_errors_pass_through(self):
        error = ValueError("weird")
        assert _map_provider_error(error) is error


class TestRetryDecorator:
    def test_retries_then_succeeds(self):
        attempts = []

        @retry_with_backoff(max_retries=3, initial_delay=0.001, jitter=False)
        def flaky():
            attempts.append(1)
            if len(attempts) < 3:
                raise ProviderError("boom")
            return "ok"

        assert flaky() == "ok"
        assert len(attempts) == 3

    def test_exhausts_and_raises(self):
        @retry_with_backoff(max_retries=2, initial_delay=0.001, jitter=False)
        def always_fails():
            raise ProviderError("boom")

        with pytest.raises(ProviderError):
            always_fails()

    def test_on_retry_callback(self):
        seen = []

        @retry_with_backoff(
            max_retries=2,
            initial_delay=0.001,
            jitter=False,
            exceptions=(ProviderError,),
            on_retry=lambda exc, n: seen.append(n),
        )
        def fails_once():
            if not seen or len(seen) < 1:
                raise ProviderError("boom")
            return "ok"

        assert fails_once() == "ok"
        assert seen == [1]


class TestEngineErrorHandling:
    def test_provider_exception_propagates(self, valid_request):
        provider = ScriptedProvider([RateLimitError("rate limited by provider")])
        with pytest.raises(RateLimitError):
            ScenarioEngine(provider).generate(valid_request)

    def test_malformed_response_propagates(self, valid_request):
        provider = ScriptedProvider([MalformedResponseError("not json")])
        with pytest.raises(MalformedResponseError):
            ScenarioEngine(provider).generate(valid_request)

    def test_missing_stage_key_triggers_repair(self, valid_request):
        provider = ScriptedProvider(
            [
                {"unexpected": "shape"},  # baseline stage: missing "scenario"
                {"scenario": MockScenarioProvider()._baseline("q")["scenario"]},  # repair
                {"alternatives": MockScenarioProvider()._alternatives("q")["alternatives"]},
                MockScenarioProvider()._uncertainties(),
                {"comparison": MockScenarioProvider()._comparison()["comparison"]},
            ]
        )
        report = ScenarioEngine(provider).generate(valid_request)
        assert report["baseline"]["id"] == "baseline"
        assert len(provider.calls) == 5

    def test_repair_failure_raises_with_problems(self, valid_request):
        provider = ScriptedProvider(
            [
                {"unexpected": "shape"},
                {"still": "wrong"},
            ]
        )
        with pytest.raises(SchemaValidationError) as exc:
            ScenarioEngine(provider).generate(valid_request)
        assert exc.value.problems


class TestCLI:
    def test_generate_with_mock(self, tmp_path, valid_request, capsys):
        out = tmp_path / "report.json"
        code = cli_main(
            [
                "--question",
                valid_request["question"],
                "--domain",
                "stock_market_education",
                "--horizon",
                "12",
                "--mock",
                "--output",
                str(out),
                "--markdown",
            ]
        )
        assert code == 0
        report = json.loads(out.read_text(encoding="utf-8"))
        assert report["generator"]["mock"] is True
        assert out.with_suffix(".md").exists()
        assert "Report written" in capsys.readouterr().out

    def test_generate_missing_arguments(self, capsys):
        code = cli_main(["--mock"])
        assert code == 2
        payload = json.loads(capsys.readouterr().err)
        assert payload["error"] == "input_validation_error"
        assert payload["problems"]

    def test_generate_invalid_domain(self, valid_request, capsys):
        code = cli_main(
            [
                "--question",
                valid_request["question"],
                "--domain",
                "general",
                "--horizon",
                "0",
                "--mock",
            ]
        )
        assert code == 2

    def test_generate_without_credentials(self, monkeypatch, valid_request, capsys):
        monkeypatch.setattr(Config, "LLM_API_KEY", None)
        code = cli_main(
            [
                "--question",
                valid_request["question"],
                "--domain",
                "general",
                "--horizon",
                "12",
            ]
        )
        assert code == 2
        payload = json.loads(capsys.readouterr().err)
        assert payload["error"] == "missing_credentials"

    def test_validate_only_ok(self, tmp_path, generated_report):
        path = tmp_path / "report.json"
        path.write_text(json.dumps(generated_report), encoding="utf-8")
        assert cli_main(["--validate-only", str(path)]) == 0

    def test_validate_only_invalid(self, tmp_path, capsys):
        path = tmp_path / "bad.json"
        path.write_text(json.dumps({"schema_version": "1.0.0"}), encoding="utf-8")
        assert cli_main(["--validate-only", str(path)]) == 4
        payload = json.loads(capsys.readouterr().err)
        assert payload["error"] == "schema_validation_error"

    def test_validate_only_missing_file(self, tmp_path, capsys):
        assert cli_main(["--validate-only", str(tmp_path / "nope.json")]) == 2

    def test_expand_unknown_scenario(self, tmp_path, generated_report, capsys):
        path = tmp_path / "report.json"
        path.write_text(json.dumps(generated_report), encoding="utf-8")
        code = cli_main(
            ["--expand", "alt-99", "--from-report", str(path), "--mock", "--output", str(tmp_path / "out.json")]
        )
        assert code == 4

    def test_expand_ok(self, tmp_path, generated_report):
        path = tmp_path / "report.json"
        path.write_text(json.dumps(generated_report), encoding="utf-8")
        out = tmp_path / "expanded.json"
        code = cli_main(
            ["--expand", "alt-1", "--from-report", str(path), "--mock", "--output", str(out)]
        )
        assert code == 0
        expanded = json.loads(out.read_text(encoding="utf-8"))
        node = next(a for a in expanded["alternatives"] if a["id"] == "alt-1")
        assert len(node["children"]) == 3

    def test_evidence_file(self, tmp_path, capsys):
        evidence_path = tmp_path / "evidence.json"
        evidence_path.write_text(
            json.dumps([{"text": "A useful user observation about the question."}]),
            encoding="utf-8",
        )
        out = tmp_path / "report.json"
        code = cli_main(
            [
                "--question",
                "How might remote work adoption evolve over two years?",
                "--domain",
                "business",
                "--horizon",
                "24",
                "--evidence-file",
                str(evidence_path),
                "--mock",
                "--output",
                str(out),
            ]
        )
        assert code == 0
        report = json.loads(out.read_text(encoding="utf-8"))
        assert report["request"]["evidence"][0]["kind"] == "user_supplied_fact"

    def test_bad_evidence_file(self, tmp_path, capsys):
        evidence_path = tmp_path / "evidence.json"
        evidence_path.write_text("not json", encoding="utf-8")
        code = cli_main(
            [
                "--question",
                "A perfectly reasonable question here",
                "--domain",
                "general",
                "--horizon",
                "12",
                "--evidence-file",
                str(evidence_path),
                "--mock",
            ]
        )
        assert code == 2
