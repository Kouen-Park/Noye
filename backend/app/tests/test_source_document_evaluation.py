"""Evaluation transport/report regressions; every HTTP response is a test double."""

import hashlib
import json
from contextlib import closing

import httpx
import pytest

from app.config import get_settings
from app.evaluation import source_documents as evaluation
from app.models.wiki import WikiScope
from app.services.source_documents import jobs, pipeline
from app.tests.test_folder_foundation import discover, folder
from app.tests.test_source_documents import enqueue, model, workspace


def test_call_measurements_keep_exact_response_counters_and_preflight(caplog):
    text = '{"title":"한국어 notes","body":"line one\\nline two"}'
    metrics = {
        "response": text,
        "done": True,
        "done_reason": "stop",
        "total_duration": 900,
        "load_duration": 100,
        "prompt_eval_count": 20,
        "prompt_eval_duration": 300,
        "eval_count": 30,
        "eval_duration": 500,
    }
    received = []

    def respond(request):
        received.append(json.loads(request.content))
        return httpx.Response(
            200,
            json=metrics
            if request.url.path.endswith("generate")
            else {"model_info": {"architecture": "synthetic"}},
        )

    clock = iter([1.0, 1.25, 2.0, 2.75])
    with closing(
        evaluation.MeasuredClient(
            httpx.Client(transport=httpx.MockTransport(respond)), clock=lambda: next(clock)
        )
    ) as client:
        client.post("http://127.0.0.1/api/show", json={"model": "test"})
        payload = {"model": "test", "prompt": json.dumps({"task": "verify_heading"})}
        response = client.post("http://127.0.0.1/api/generate", json=payload)
        assert received[-1] == payload
        assert client.calls[0]["task"] == "model_preflight"
        assert client.calls[0]["wall_seconds"] == 0.25
        call = client.calls[1]
        assert call["task"] == "verify_heading"
        assert call["http_status"] == 200
        assert call["wall_seconds"] == 0.75
        assert call["raw_response"] == response.text
        assert {key: call[key] for key in evaluation.MODEL_FIELDS} == metrics
        assert "prompt" not in call
    assert text not in caplog.text


def test_owned_measurement_client_ignores_proxies_and_redirects(monkeypatch):
    options = {}
    transport = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200)))

    def client(**kwargs):
        options.update(kwargs)
        return transport

    monkeypatch.setattr(evaluation.httpx, "Client", client)
    evaluation.MeasuredClient().close()
    assert options == {"timeout": 300, "follow_redirects": False, "trust_env": False}


@pytest.mark.parametrize("failure", ["invalid_json", "transport"])
def test_failed_calls_remain_measured_and_validation_receives_same_failure(failure):
    def respond(request):
        if failure == "transport":
            raise httpx.ConnectError("Synthetic offline model", request=request)
        return httpx.Response(502, content=b"synthetic malformed response")

    with closing(
        evaluation.MeasuredClient(httpx.Client(transport=httpx.MockTransport(respond)))
    ) as client:
        if failure == "transport":
            with pytest.raises(httpx.ConnectError, match="Synthetic offline model"):
                client.post("http://127.0.0.1/api/generate", json={"prompt": '{"task":"outline"}'})
        else:
            response = client.post(
                "http://127.0.0.1/api/generate", json={"prompt": '{"task":"outline"}'}
            )
            assert response.status_code == 502
        assert client.calls[0]["task"] == "outline"
        assert client.calls[0]["wall_seconds"] >= 0
        assert client.calls[0]["response"] is None
        if failure == "transport":
            assert client.calls[0]["error"]["type"] == "ConnectError"
        else:
            assert client.calls[0]["raw_response"] == "synthetic malformed response"


@pytest.mark.parametrize("invalid", [None, "json"])
def test_document_reports_bind_body_or_preserve_failed_model_output(
    workspace, tmp_path, caplog, invalid
):
    db, *_ = workspace
    discover(workspace)
    job = enqueue(db)
    jobs.register()
    original = pipeline.generate
    with closing(evaluation.MeasuredClient(model(invalid=invalid)[0])) as client:
        report = evaluation.measured_document(db, job, get_settings(), client)
    assert pipeline.generate is original
    assert report["model_calls"]
    assert any(call["task"] == "interpret_intent" for call in report["model_calls"])
    if invalid:
        assert report["job"]["state"] == "failed"
        assert report["job"]["error"] == "Invalid local model JSON. No document was saved."
        assert report["revision"] is None
        assert report["revision_body_sha256"] is None
        response = next(
            call for call in report["model_calls"] if call["task"] == "interpret_intent"
        )["response"]
        assert json.loads(response) == {"unexpected": True}
    else:
        assert report["job"]["state"] == "complete"
        assert (
            report["revision_body_sha256"]
            == hashlib.sha256(report["revision"]["content"].encode("utf-8")).hexdigest()
        )
    target = evaluation.save_report(tmp_path / "attempt.json", report)
    repeated = evaluation.save_report(target, {"second_attempt": True})
    assert repeated != target
    assert json.loads(target.read_text()) == report
    assert json.loads(repeated.read_text()) == {"second_attempt": True}
    assert all(
        call["response"] is None or call["response"] not in caplog.text
        for call in report["model_calls"]
    )


def test_wiki_failure_also_retains_measurements_and_report(workspace, monkeypatch, tmp_path):
    db, *_ = workspace
    source = discover(workspace)

    def fail(_db, _identifier, _scope, _manifest, *, client):
        client.post(
            "http://127.0.0.1/api/generate", json={"prompt": '{"task":"summarize_section"}'}
        )
        raise ValueError("Synthetic rejected Wiki output")

    monkeypatch.setattr(evaluation.service, "generate_source", fail)
    with closing(
        evaluation.MeasuredClient(
            httpx.Client(
                transport=httpx.MockTransport(
                    lambda _: httpx.Response(200, json={"response": "Exact rejected Wiki response"})
                )
            )
        )
    ) as client:
        report = evaluation.measured_wiki(
            db, WikiScope(mode="chosen", source_ids=[source.id]), client
        )
    target = evaluation.save_report(tmp_path / "wiki.json", report)
    saved = json.loads(target.read_text())
    assert saved["state"] == "failed"
    assert saved["error"]["source_id"] == source.id
    assert saved["model_calls"][0]["response"] == "Exact rejected Wiki response"
