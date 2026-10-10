import importlib
import json
import os
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from gmail_cli.cli import cli
from gmail_cli.gmail_client import GmailClient, GmailError
from gmail_cli.harness_v1 import (
    _bounded_body,
    apply_v1,
    list_v1,
    validate_v1_request,
)
from gmail_cli.models import Label, Message

cli_module = importlib.import_module("gmail_cli.cli")


def message(message_id, body="", label_ids=None):
    return Message(
        id=message_id,
        thread_id=f"thread-{message_id}",
        from_="sender@example.test",
        to="recipient@example.test",
        subject="Synthetic",
        date="2026-01-01",
        label_ids=label_ids or [],
        body=body,
    )


def serialized_body_size(body):
    return len(json.dumps(body, ensure_ascii=False).encode("utf-8"))


@pytest.mark.parametrize("version", [2, True, 1.0])
def test_validate_v1_request_rejects_non_exact_protocol_version(version):
    with pytest.raises(ValueError, match=r"^Invalid protocol version$"):
        validate_v1_request({"version": version, "operation": "list"})


def test_validate_v1_request_rejects_malformed_cursor_without_client_access():
    client = MagicMock()
    request = {"version": 1, "operation": "list", "cursor": "not-a-cursor"}

    with pytest.raises(ValueError, match=r"^Invalid cursor$"):
        validate_v1_request(request)

    client.list_message_page.assert_not_called()
    client.get_messages.assert_not_called()


def test_validate_v1_request_rejects_invalid_assignments_shape():
    request = {
        "version": 1,
        "operation": "apply",
        "authorize": True,
        "archive_authorized": False,
        "assignments": [{"message_id": "m1", "labels": "Work"}],
    }

    with pytest.raises(ValueError, match=r"^Invalid v1 assignments$"):
        validate_v1_request(request)


@pytest.mark.parametrize(
    "payload",
    [
        {"version": 1, "operation": "list", "limit": 1},
        {
            "version": 1,
            "operation": "apply",
            "authorize": True,
            "archive_authorized": False,
            "assignments": [{"message_id": "m1", "labels": ["Work"]}],
        },
    ],
)
def test_validate_v1_request_accepts_valid_list_and_apply_schemas(payload):
    assert validate_v1_request(payload) is None


def list_client(pages, messages):
    client = MagicMock()
    list_call = client._service.users.return_value.messages.return_value.list
    list_call.return_value.execute.side_effect = pages
    client.list_message_page.side_effect = lambda **params: list_call(**params).execute()
    client.get_messages.side_effect = lambda ids: {mid: messages[mid] for mid in ids}
    return client, list_call


def test_list_uses_opaque_cursor_and_deduplicates_ids():
    client, request = list_client(
        [
            {"messages": [{"id": "a"}, {"id": "a"}], "nextPageToken": "opaque+/="},
            {"messages": [{"id": "b"}]},
        ],
        {"a": message("a"), "b": message("b")},
    )
    first = list_v1(client, {"version": 1, "limit": 2})
    second = list_v1(client, {"version": 1, "limit": 2, "cursor": first["next_cursor"]})
    assert [m["id"] for m in first["messages"]] == ["a"]
    assert first["has_more"] is True
    assert second["has_more"] is False
    assert request.call_args_list[1].kwargs["pageToken"] == "opaque+/="


@pytest.mark.parametrize(
    "payload",
    [
        {"version": 1, "limit": 0},
        {"version": 1, "limit": 101},
        {"version": 1, "limit": True},
        {"version": 1, "cursor": "!"},
    ],
)
def test_invalid_list_request_fails_before_api(payload):
    client = MagicMock()
    with pytest.raises(ValueError, match="Invalid"):
        list_v1(client, payload)
    client.list_message_page.assert_not_called()


def test_cursor_filter_mismatch_fails_before_api():
    client, list_call = list_client([{"messages": [], "nextPageToken": "p"}], {})
    cursor = list_v1(client, {"version": 1, "query": "first"})["next_cursor"]
    with pytest.raises(ValueError, match="cursor"):
        list_v1(client, {"version": 1, "query": "other", "cursor": cursor})
    assert list_call.call_count == 1


def test_cursor_boundary_and_final_page_have_no_extra_remote_call():
    client, list_call = list_client(
        [{"messages": [{"id": "a"}], "nextPageToken": "last-token"}, {"messages": []}],
        {"a": message("a")},
    )
    first = list_v1(client, {"version": 1, "limit": 1})
    final = list_v1(client, {"version": 1, "limit": 1, "cursor": first["next_cursor"]})
    assert first["has_more"] is True
    assert final["messages"] == []
    assert final["has_more"] is False
    assert list_call.call_count == 2
    assert list_call.call_args_list[1].kwargs["pageToken"] == "last-token"


def test_invalid_cursor_does_not_invoke_remote_service():
    client = MagicMock()
    with pytest.raises(ValueError, match="Invalid cursor"):
        list_v1(client, {"version": 1, "cursor": "not-a-cursor"})
    client.list_message_page.assert_not_called()


def test_oversized_cursor_is_rejected_before_api_call():
    client = MagicMock()
    with pytest.raises(ValueError, match="Invalid cursor"):
        list_v1(client, {"version": 1, "cursor": "x" * 8193})
    client.list_message_page.assert_not_called()


def test_v1_list_schema_rejects_unsupported_field_without_api_call():
    client = MagicMock()
    with pytest.raises(ValueError, match="Invalid v1 list schema"):
        list_v1(client, {"version": 1, "unexpected": True})
    client.list_message_page.assert_not_called()


@pytest.mark.parametrize("version", [True, 1.0, "1", 2])
def test_v1_list_rejects_non_exact_version_before_api_call(version):
    client = MagicMock()
    with pytest.raises(ValueError, match="Invalid v1 list schema"):
        list_v1(client, {"version": version})
    client.list_message_page.assert_not_called()
    client.get_messages.assert_not_called()


@pytest.mark.parametrize("version", [True, 1.0, "1", 2])
def test_v1_apply_rejects_non_exact_version_before_gmail_calls(version):
    client = MagicMock()
    request = apply_request([{"message_id": "m1", "labels": ["Work"]}])
    request["version"] = version
    with pytest.raises(ValueError, match="Invalid or unauthorized v1 apply request"):
        apply_v1(client, request)
    client.list_labels.assert_not_called()
    client.get_message.assert_not_called()
    client.modify_message.assert_not_called()


def test_v1_list_uses_single_batch_for_deduplicated_bounded_page_in_stable_order():
    class StubBatch:
        def __init__(self):
            self.requests = []
            self.execute_count = 0

        def add(self, request, callback, request_id):
            self.requests.append((request_id, callback))

        def execute(self):
            self.execute_count += 1
            for request_id, callback in reversed(self.requests):
                callback(
                    request_id,
                    {
                        "id": request_id,
                        "threadId": f"thread-{request_id}",
                        "labelIds": [],
                        "payload": {"headers": []},
                    },
                    None,
                )

    service = MagicMock()
    batch = StubBatch()
    service.new_batch_http_request.return_value = batch
    service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": [{"id": "b"}, {"id": "a"}, {"id": "b"}]
    }
    client = GmailClient(service)
    list_call = service.users.return_value.messages.return_value.list
    response = list_v1(client, {"version": 1, "limit": 2})
    assert [record["id"] for record in response["messages"]] == ["b", "a"]
    assert [request_id for request_id, _ in batch.requests] == ["b", "a"]
    assert batch.execute_count == 1
    assert list_call.call_count == 1
    assert list_call.call_args.kwargs["maxResults"] == 2
    service.users.return_value.messages.return_value.modify.assert_not_called()


def test_v1_list_batch_failure_fails_closed_without_mutation():
    class FailingBatch:
        def add(self, request, callback, request_id):
            self.callback = callback
            self.request_id = request_id

        def execute(self):
            self.callback(self.request_id, None, RuntimeError("batch read failed"))

    service = MagicMock()
    service.new_batch_http_request.return_value = FailingBatch()
    service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": [{"id": "m1"}]
    }
    client = GmailClient(service)
    with pytest.raises(GmailError, match="Erro ao obter mensagem"):
        list_v1(client, {"version": 1, "limit": 1})
    service.users.return_value.messages.return_value.modify.assert_not_called()


def test_v1_list_individual_fallback_error_fails_closed_without_mutation():
    service = MagicMock()
    del service.new_batch_http_request
    service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": [{"id": "m1"}, {"id": "m2"}]
    }
    client = GmailClient(service)
    with (
        patch.object(client, "get_message", side_effect=[message("m1"), GmailError("synthetic")]),
        pytest.raises(GmailError, match="synthetic"),
    ):
        list_v1(client, {"version": 1, "limit": 2})
    service.users.return_value.messages.return_value.modify.assert_not_called()


def test_list_normalizes_and_bounds_utf8_body_with_marker():
    client, _ = list_client([{"messages": [{"id": "a"}]}], {"a": message("a", "é\r\n" * 12000)})
    body = list_v1(client, {"version": 1})["messages"][0]["body"]
    assert "\r" not in body
    assert serialized_body_size(body) <= 16 * 1024
    assert body.endswith("\n...[truncated]")


def test_page_body_budget_includes_markers_and_multibyte_utf8():
    client, _ = list_client(
        [{"messages": [{"id": "a"}, {"id": "b"}]}],
        {"a": message("a", "é" * 20000), "b": message("b", "界" * 20000)},
    )
    result = list_v1(client, {"version": 1, "limit": 2})
    bodies = [item["body"] for item in result["messages"]]
    assert sum(serialized_body_size(body) for body in bodies) <= 256 * 1024
    assert all(serialized_body_size(body) <= 16 * 1024 for body in bodies)
    assert bodies[0].endswith("\n...[truncated]")
    assert bodies[1].endswith("\n...[truncated]")


def test_exact_marker_boundary_does_not_exceed_body_budget():
    marker = "\n...[truncated]"
    budget = serialized_body_size(marker) + 1
    bounded, truncated = _bounded_body('"\\\n\\té' * 200, budget)
    assert truncated is True
    assert bounded.endswith(marker)
    assert serialized_body_size(bounded) <= budget


def test_body_marker_too_large_for_remaining_budget_sets_truncation_signal():
    page_ids = [f"m{index}" for index in range(17)]
    client, _ = list_client(
        [{"messages": [{"id": message_id} for message_id in page_ids], "nextPageToken": "next"}],
        {message_id: message(message_id, "x" * 20000) for message_id in page_ids},
    )
    response = list_v1(client, {"version": 1, "limit": 17})
    bodies = [record["body"] for record in response["messages"]]
    assert len(response["messages"]) == 17
    assert sum(serialized_body_size(body) for body in bodies) <= 256 * 1024
    assert response["messages"][-1]["body"] == ""
    assert response["messages"][-1]["body_truncated"] is True


def test_json_escaping_and_unicode_are_included_in_body_budget():
    body_text = 'quote " slash \\ newline\n tab\t control\x01 café 界' * 1000
    client, _ = list_client(
        [{"messages": [{"id": "special"}]}],
        {"special": message("special", body_text)},
    )
    emitted_body = list_v1(client, {"version": 1})["messages"][0]["body"]
    assert serialized_body_size(emitted_body) <= 16 * 1024
    assert emitted_body.endswith("\n...[truncated]")
    assert body_text.startswith(emitted_body.removesuffix("\n...[truncated]"))


def test_body_preserves_arbitrary_email_content_without_secret_metadata():
    body_text = "synthetic body may contain credential-like text"
    client, _ = list_client([{"messages": [{"id": "m"}]}], {"m": message("m", body_text)})
    response = list_v1(client, {"version": 1})
    assert response["messages"][0]["body"] == body_text
    assert set(response["messages"][0]) == {
        "id",
        "thread_id",
        "from",
        "to",
        "subject",
        "date",
        "label_ids",
        "body",
    }


@pytest.mark.parametrize(
    ("page", "expected"),
    [
        ({"messages": []}, []),
        ({"messages": [{"id": "a"}, {"id": "b"}]}, ["a", "b"]),
        ({"messages": [{"id": "a"}], "nextPageToken": "next"}, ["a"]),
    ],
)
def test_list_empty_limit_and_page_boundary(page, expected):
    messages = {key: message(key) for key in ("a", "b", "c")}
    client, _ = list_client([page], messages)
    result = list_v1(client, {"version": 1, "limit": 2})
    assert [item["id"] for item in result["messages"]] == expected
    assert result["has_more"] is bool(page.get("nextPageToken"))
    assert (
        client._service.users.return_value.messages.return_value.list.call_args.kwargs["maxResults"]
        == 2
    )


def test_list_filters_are_sent_and_response_has_only_allowlisted_fields():
    client, list_call = list_client([{"messages": [{"id": "m"}]}], {"m": message("m")})
    result = list_v1(client, {"version": 1, "query": "from:synthetic", "label_ids": ["INBOX"]})
    assert set(result["messages"][0]) == {
        "id",
        "thread_id",
        "from",
        "to",
        "subject",
        "date",
        "label_ids",
        "body",
    }
    assert list_call.call_args.kwargs["q"] == "from:synthetic"
    assert list_call.call_args.kwargs["labelIds"] == ["INBOX"]
    assert "token" not in json.dumps(result).lower()


def test_gmail_client_prefers_plain_text_and_falls_back_to_html():
    service = MagicMock()
    service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
        "id": "m",
        "threadId": "t",
        "payload": {
            "headers": [],
            "parts": [
                {"mimeType": "text/html", "body": {"data": "PGI+aHRtbDwvYj4="}},
                {"mimeType": "text/plain", "body": {"data": "cGxhaW4="}},
            ],
        },
    }
    assert GmailClient(service).get_message("m").body == "plain"
    service.users.return_value.messages.return_value.get.return_value.execute.return_value[
        "payload"
    ]["parts"].pop()
    assert GmailClient(service).get_message("m").body == "<b>html</b>"


@pytest.mark.parametrize(("failure", "status_code"), [(False, 0), (True, 2)])
def test_cli_protocol_emits_one_json_line_and_separates_stderr(failure, status_code):
    client = apply_client()
    if failure:
        client.get_message.side_effect = GmailError("synthetic")
    payload = apply_request([{"message_id": "m1", "labels": ["Work"]}])
    with patch.object(cli_module, "_create_client", return_value=client):
        result = CliRunner().invoke(cli, ["harness"], input=json.dumps(payload))
    assert result.exit_code == status_code
    assert len(result.output.splitlines()) == 1
    decoded = json.loads(result.output)
    assert decoded["status"] == ("success" if not failure else "preflight_failed")
    assert "synthetic" not in result.output
    assert client.modify_message.call_count == (0 if failure else 1)


def test_cli_v1_list_dispatch_emits_json_response():
    client, _ = list_client([{"messages": [{"id": "m1"}]}], {"m1": message("m1")})
    request = {"version": 1, "operation": "list", "limit": 1}
    with patch.object(cli_module, "_create_client", return_value=client):
        result = CliRunner().invoke(cli, ["harness"], input=json.dumps(request))
    assert result.exit_code == 0
    decoded = json.loads(result.output)
    assert decoded["version"] == 1
    assert [item["id"] for item in decoded["messages"]] == ["m1"]
    client.modify_message.assert_not_called()


@pytest.mark.parametrize("version", [2, True, "1"])
def test_cli_unsupported_protocol_version_fails_before_client_creation(version):
    request = {"version": version, "operation": "list"}
    with patch.object(cli_module, "_create_client") as create_client:
        result = CliRunner().invoke(cli, ["harness"], input=json.dumps(request))
    assert result.exit_code == 2
    decoded = json.loads(result.output)
    assert decoded["status"] == "failed"
    assert decoded["error"]["code"] == "request_or_gmail_error"
    create_client.assert_not_called()


@pytest.mark.parametrize(
    "payload",
    [
        {"version": 1, "operation": "list", "unexpected": True},
        {
            "version": 1,
            "operation": "apply",
            "authorize": True,
            "archive_authorized": False,
            "assignments": [{"message_id": "m1", "labels": ["Work"]}],
            "unexpected": True,
        },
        {"version": 1.0, "operation": "list"},
        {"version": True, "operation": "apply"},
    ],
)
def test_cli_invalid_v1_schema_fails_before_client_creation(payload):
    with patch.object(cli_module, "_create_client") as create_client:
        result = CliRunner().invoke(cli, ["harness"], input=json.dumps(payload))
    assert result.exit_code == 2
    decoded = json.loads(result.output)
    assert decoded["status"] == "failed"
    assert decoded["error"]["code"] == "request_or_gmail_error"
    create_client.assert_not_called()


def test_cli_v1_unsupported_operation_emits_safe_failure_json():
    request = {"version": 1, "operation": "delete"}
    with patch.object(cli_module, "_create_client") as create_client:
        result = CliRunner().invoke(cli, ["harness"], input=json.dumps(request))
    assert result.exit_code == 2
    decoded = json.loads(result.output)
    assert decoded["status"] == "failed"
    assert decoded["error"]["code"] == "request_or_gmail_error"
    create_client.assert_not_called()


def test_cli_v1_unexpected_handler_error_reports_internal_error():
    request = {"version": 1, "operation": "list"}
    with (
        patch.object(cli_module, "_create_client", return_value=MagicMock()),
        patch.object(cli_module, "list_v1", side_effect=RuntimeError("private detail")),
    ):
        result = CliRunner().invoke(cli, ["harness"], input=json.dumps(request))
    assert result.exit_code == 2
    decoded = json.loads(result.output)
    assert decoded["status"] == "failed"
    assert decoded["error"]["code"] == "internal_error"
    assert "private detail" not in result.output


def test_cli_partial_apply_uses_exit_three_and_keeps_per_item_json():
    client = apply_client()
    client.modify_message.side_effect = [None, GmailError("synthetic"), None]
    payload = apply_request(
        [
            {"message_id": "m1", "labels": ["Work"]},
            {"message_id": "m2", "labels": ["Work"]},
        ]
    )
    with patch.object(cli_module, "_create_client", return_value=client):
        result = CliRunner().invoke(cli, ["harness"], input=json.dumps(payload))
    assert result.exit_code == 3
    decoded = json.loads(result.output)
    assert decoded["status"] == "partial"
    assert [row["status"] for row in decoded["results"]] == ["success", "failed"]


@pytest.mark.parametrize(
    ("assignments", "expected_exit", "expected_status"),
    [
        ([{"message_id": "m1", "labels": ["Work"]}], 0, "success"),
        ([{"message_id": "m1", "labels": ["unknown"]}], 2, "preflight_failed"),
        (
            [{"message_id": "m1", "labels": ["Work"]}, {"message_id": "m2", "labels": ["Work"]}],
            3,
            "partial",
        ),
    ],
)
def test_subprocess_harness_isolated_json_stream_and_exit_codes(
    assignments, expected_exit, expected_status
):
    script = r"""import importlib, sys
from unittest.mock import MagicMock
from gmail_cli.cli import cli
from gmail_cli.models import Label, Message
from gmail_cli.gmail_client import GmailError
m = importlib.import_module("gmail_cli.cli")
c = MagicMock()
c.list_labels.return_value = [Label(id="L1", name="Work")]
c.get_message.side_effect = lambda mid: Message(id=mid, thread_id="t", from_="", subject="", date="", label_ids=["INBOX"])
if len(sys.argv) > 1 and sys.argv[1] == "partial": c.modify_message.side_effect = [None, GmailError("synthetic")]
m._create_client = lambda: c
cli.main(args=["harness"])
"""
    kind = "partial" if expected_exit == 3 else "normal"
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)}
    proc = subprocess.run(
        [sys.executable, "-c", script, kind],
        input=json.dumps(apply_request(assignments)),
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    assert proc.returncode == expected_exit
    assert len(proc.stdout.splitlines()) == 1
    assert json.loads(proc.stdout)["status"] == expected_status
    assert "synthetic" not in proc.stdout
    assert "synthetic" not in proc.stderr


def test_apply_records_following_item_as_not_attempted_after_write_failure():
    client = apply_client()
    client.modify_message.side_effect = [None, GmailError("synthetic"), None]
    result = apply_v1(
        client,
        apply_request(
            [
                {"message_id": "m1", "labels": ["Work"]},
                {"message_id": "m2", "labels": ["Work"]},
                {"message_id": "m3", "labels": ["Work"]},
            ]
        ),
    )
    assert [row["status"] for row in result["results"]] == ["success", "failed", "not_attempted"]
    assert client.modify_message.call_count == 2


@pytest.mark.parametrize(
    ("operation", "expected_call"),
    [
        ("get", "get_message"),
        ("list", "list_messages"),
        ("mark", "modify_message"),
    ],
)
def test_legacy_harness_operations_remain_compatible(operation, expected_call):
    client = apply_client()
    client.list_messages.return_value = [message("m1")]
    payload = {"operation": operation}
    if operation == "get":
        payload["id"] = "m1"
    elif operation == "list":
        payload["max_results"] = 1
    else:
        payload.update(id="m1", action="read", authorized=True)
    with patch.object(cli_module, "_create_client", return_value=client):
        result = CliRunner().invoke(cli, ["harness"], input=json.dumps(payload))
    assert result.exit_code == 0
    assert json.loads(result.output)["ok"] is True
    getattr(client, expected_call).assert_called()


def test_legacy_standalone_mark_command_preserved():
    client = apply_client()
    with patch.object(cli_module, "_create_client", return_value=client):
        result = CliRunner().invoke(cli, ["mark", "unread", "m1"])
    assert result.exit_code == 0
    client.modify_message.assert_called_once_with("m1", add_labels=["UNREAD"])


def apply_client():
    client = MagicMock()
    client.list_labels.return_value = [Label(id="L1", name="Work")]
    client.get_message.side_effect = lambda mid: message(mid, label_ids=["INBOX"])
    return client


def apply_request(assignments, archive=False):
    return {
        "version": 1,
        "authorize": True,
        "archive_authorized": archive,
        "assignments": assignments,
    }


def test_apply_invalid_last_assignment_preflights_entire_batch_without_writes():
    client = apply_client()
    client.get_message.side_effect = [message("m1", label_ids=["INBOX"]), GmailError("missing")]
    result = apply_v1(
        client,
        apply_request(
            [
                {"message_id": "m1", "labels": ["Work"]},
                {"message_id": "m2", "labels": ["Work"]},
            ]
        ),
    )
    assert result["status"] == "preflight_failed"
    assert [entry["status"] for entry in result["results"]] == ["not_attempted", "failed"]
    client.modify_message.assert_not_called()


def test_apply_invalid_assignment_shape_fails_before_reads_or_writes():
    client = apply_client()
    with pytest.raises(ValueError, match="Invalid assignments"):
        apply_v1(client, apply_request([{"message_id": "m1", "labels": "Work"}]))
    client.list_labels.assert_not_called()
    client.get_message.assert_not_called()
    client.modify_message.assert_not_called()


def test_apply_missing_message_id_reports_preflight_failure_without_writes():
    client = apply_client()
    client.get_message.side_effect = None
    client.get_message.return_value = message("")
    result = apply_v1(client, apply_request([{"message_id": "m1", "labels": ["Work"]}]))
    assert result["status"] == "preflight_failed"
    assert result["results"][0]["status"] == "failed"
    assert result["results"][0]["error"] == "preflight_failed"
    client.modify_message.assert_not_called()


def test_apply_assigns_labels_and_archives_only_when_separately_authorized():
    client = apply_client()
    result = apply_v1(client, apply_request([{"message_id": "m1", "labels": ["Work"]}], True))
    assert result["status"] == "success"
    client.modify_message.assert_called_once_with("m1", add_labels=["L1"], remove_labels=["INBOX"])


def test_apply_without_archive_authorization_preserves_inbox():
    client = apply_client()
    result = apply_v1(client, apply_request([{"message_id": "m1", "labels": ["Work"]}]))
    assert result["status"] == "success"
    client.modify_message.assert_called_once_with("m1", add_labels=["L1"], remove_labels=[])


@pytest.mark.parametrize(
    "assignments",
    [
        [{"message_id": "m1", "labels": ["unknown"]}],
        [{"message_id": "m1", "labels": ["INBOX"]}],
        [{"message_id": "m1", "labels": ["Work"]}, {"message_id": "m1", "labels": ["Work"]}],
    ],
)
def test_apply_invalid_label_or_duplicate_rejects_batch_before_write(assignments):
    client = apply_client()
    if assignments[0]["message_id"] == assignments[-1]["message_id"] and len(assignments) > 1:
        with pytest.raises(ValueError, match="duplicate"):
            apply_v1(client, apply_request(assignments))
    else:
        result = apply_v1(client, apply_request(assignments))
        assert result["status"] == "preflight_failed"
    client.modify_message.assert_not_called()


@pytest.mark.parametrize(("authorize", "archive"), [(False, False), (True, "yes")])
def test_apply_rejects_invalid_authorization_before_reads_or_writes(authorize, archive):
    client = apply_client()
    payload = apply_request([{"message_id": "m1", "labels": ["Work"]}], archive)
    payload["authorize"] = authorize
    with pytest.raises(ValueError, match="Invalid or unauthorized v1 apply request"):
        apply_v1(client, payload)
    client.list_labels.assert_not_called()
    client.modify_message.assert_not_called()


def test_apply_reports_real_partial_failure_without_rollback():
    client = apply_client()
    client.modify_message.side_effect = [None, GmailError("remote")]
    result = apply_v1(
        client,
        apply_request(
            [
                {"message_id": "m1", "labels": ["Work"]},
                {"message_id": "m2", "labels": ["Work"]},
            ]
        ),
    )
    assert result["status"] == "partial"
    assert [entry["status"] for entry in result["results"]] == ["success", "failed"]
    assert client.modify_message.call_count == 2
    assert client.modify_message.call_args_list == [
        (("m1",), {"add_labels": ["L1"], "remove_labels": []}),
        (("m2",), {"add_labels": ["L1"], "remove_labels": []}),
    ]
    assert result["results"][0]["added_label_ids"] == ["L1"]
    assert result["results"][1]["error"] == "gmail_write_failed"


def test_apply_retry_is_idempotent_for_identical_mapping():
    class StatefulClient:
        def __init__(self):
            self.state = {"m1": set()}
            self.calls = 0

        def list_labels(self):
            return [Label(id="L1", name="Work")]

        def get_message(self, mid):
            return message(mid, label_ids=list(self.state[mid]))

        def modify_message(self, mid, add_labels=None, remove_labels=None):
            self.calls += 1
            self.state[mid].update(add_labels or [])
            self.state[mid].difference_update(remove_labels or [])

    client = StatefulClient()
    request = apply_request([{"message_id": "m1", "labels": ["Work"]}])
    assert apply_v1(client, request)["status"] == "success"
    assert apply_v1(client, request)["status"] == "success"
    assert client.state["m1"] == {"L1"}
    assert client.calls == 2
