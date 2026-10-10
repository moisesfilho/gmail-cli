import json
import os
from unittest.mock import MagicMock, call, patch

import pytest
from click.testing import CliRunner

from gmail_cli import batch_ops
from gmail_cli.cli import cli
from gmail_cli.gmail_client import GmailError
from gmail_cli.models import Label, Message


def msg(message_id, labels=None, body="Body"):
    return Message(
        id=message_id,
        thread_id=f"t-{message_id}",
        from_="sender@example.test",
        subject=f"Subject {message_id}",
        date="today",
        label_ids=labels or [],
        body=body,
    )


def assigned_client():
    client = MagicMock()
    client.list_messages.return_value = [msg("m1", ["INBOX"]), msg("m2", ["INBOX"])]
    client.list_labels.return_value = [Label(id="L1", name="Work")]
    client.get_message_metadata.side_effect = lambda mid: msg(mid, ["INBOX"])
    return client


def plan_input(messages=None, **extra):
    return {
        "version": 1,
        "query": "is:unread",
        "max_results": 2,
        "messages": messages or [{"id": "m1", "category": "Work"}],
        **extra,
    }


def create_plan(tmp_path, client=None, payload=None):
    client = client or assigned_client()
    path = tmp_path / "plan.json"
    result = batch_ops.build_plan(client, payload or plan_input(), path)
    return client, path, result


def test_batch_list_metadata_defaults_order_deduplicates_and_does_not_mutate():
    client = MagicMock()
    client.list_message_page.return_value = {"messages": [{"id": "b"}, {"id": "a"}, {"id": "b"}]}
    client.get_message_metadata.side_effect = msg
    with patch("gmail_cli.cli._create_client", return_value=client):
        result = CliRunner().invoke(cli, ["batch", "list", "--query", "q", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert list(data) == ["command", "status", "results"]
    assert [row["id"] for row in data["results"]] == ["b", "a"]
    assert all("body" not in row for row in data["results"])
    client.get_message_metadata.assert_has_calls([call("b"), call("a")])
    client.get_messages.assert_not_called()
    client.modify_message.assert_not_called()


def test_batch_list_include_body_is_bounded_and_preserves_order():
    client = MagicMock()
    client.list_message_page.return_value = {"messages": [{"id": "m"}]}
    client.get_messages.return_value = {"m": msg("m", body="x" * 20_000)}
    result = batch_ops.list_batch(client, "q", 1, include_body=True)
    assert list(result) == ["command", "status", "results"]
    assert len(result["results"][0]["body"]) == batch_ops.MAX_BODY_CHARS
    client.get_message_metadata.assert_not_called()


@pytest.mark.parametrize("maximum", [0, 101, True, "2"])
def test_batch_list_rejects_invalid_limit_before_gmail(maximum):
    client = MagicMock()
    with pytest.raises(ValueError, match="max must"):
        batch_ops.list_batch(client, "q", maximum)
    client.list_message_page.assert_not_called()


@pytest.mark.parametrize("payload", [None, {}, {"version": True}, {"version": 1, "max_results": 0}])
def test_plan_rejects_invalid_schema_before_gmail(tmp_path, payload):
    client = MagicMock()
    with pytest.raises(ValueError, match="Invalid batch plan"):
        batch_ops.build_plan(client, payload, tmp_path / "out.json")
    client.list_messages.assert_not_called()


def test_plan_rejects_duplicate_ids_before_gmail(tmp_path):
    client = MagicMock()
    with pytest.raises(ValueError, match="duplicate"):
        batch_ops.build_plan(
            client,
            plan_input([{"id": "m1", "category": "Work"}, {"id": "m1", "category": "Work"}]),
            tmp_path / "out.json",
        )
    client.list_messages.assert_not_called()


@pytest.mark.parametrize(
    ("extra", "message", "error"),
    [
        ({"label_map": []}, [{"id": "m1", "category": "Work"}], "label_map"),
        ({"label_map": {"Work": " "}}, [{"id": "m1", "category": "Work"}], "label_map entry"),
        ({}, [{"id": "m1", "category": " "}], "assignment"),
        ({}, [{"id": "m1", "category": "   "}], "assignment"),
    ],
)
def test_plan_rejects_invalid_assignments_and_mapping_before_gmail(tmp_path, extra, message, error):
    client = MagicMock()
    with pytest.raises(ValueError, match=error):
        batch_ops.build_plan(client, plan_input(message, **extra), tmp_path / "out.json")
    client.list_messages.assert_not_called()


def test_plan_rejects_empty_or_colliding_normalized_labels(tmp_path):
    client = assigned_client()
    with pytest.raises(ValueError, match="Invalid label_map entry"):
        batch_ops.build_plan(
            client,
            plan_input([{"id": "m1", "category": "Work"}], label_map={"Work": "  "}),
            tmp_path / "empty.json",
        )
    client.list_labels.return_value = []
    with pytest.raises(ValueError, match="Duplicate normalized"):
        batch_ops.build_plan(
            client,
            plan_input(
                [{"id": "m1", "category": "one"}, {"id": "m2", "category": "two"}],
                label_map={"one": " Work ", "two": "work"},
            ),
            tmp_path / "collision.json",
        )


def test_plan_rejects_ambiguous_existing_normalized_labels(tmp_path):
    client = assigned_client()
    client.list_labels.return_value = [Label("L1", "Work"), Label("L2", " work ")]
    with pytest.raises(ValueError, match="Ambiguous normalized existing"):
        batch_ops.build_plan(client, plan_input(), tmp_path / "ambiguous.json")


def test_batch_list_fails_when_body_fetch_contains_gmail_error():
    client = MagicMock()
    client.list_message_page.return_value = {"messages": [{"id": "m1"}]}
    client.get_messages.return_value = {"m1": GmailError("unavailable")}
    with pytest.raises(GmailError, match="unavailable"):
        batch_ops.list_batch(client, "q", 1, include_body=True)


def test_apply_dry_run_archive_cli_skips_prompts_and_all_writes(tmp_path):
    client, path, _ = create_plan(tmp_path)
    original_artifact = path.read_bytes()
    with (
        patch("gmail_cli.cli._create_client", return_value=client),
        patch.object(
            batch_ops, "click_tty_confirm", side_effect=AssertionError("prompt")
        ) as confirm,
    ):
        result = CliRunner().invoke(
            cli, ["batch", "apply", "--plan", str(path), "--dry-run", "--archive"]
        )
    assert result.exit_code == 0
    response = json.loads(result.output)
    assert response["status"] == "success"
    assert response["results"] == [
        {"message_id": "m1", "status": "preflight_ok", "expected_archived": True}
    ]
    confirm.assert_not_called()
    client.create_label.assert_not_called()
    client.modify_message.assert_not_called()
    assert path.read_bytes() == original_artifact


def test_cli_batch_apply_partial_has_exit_three(tmp_path):
    client, path, _ = create_plan(tmp_path)
    client.modify_message.side_effect = GmailError("write failed")
    with (
        patch("gmail_cli.cli._create_client", return_value=client),
        patch.object(batch_ops, "click_tty_confirm", return_value=True),
    ):
        result = CliRunner().invoke(cli, ["batch", "apply", "--plan", str(path)])
    assert result.exit_code == 3
    assert json.loads(result.output)["results"][0]["status"] == "failed"


def test_cli_plan_and_verify_errors_have_exit_two(tmp_path):
    input_path = tmp_path / "input.json"
    input_path.write_text("{}")
    runner = CliRunner()
    plan_result = runner.invoke(
        cli, ["batch", "plan", "--input", str(input_path), "--out", str(tmp_path / "plan")]
    )
    assert plan_result.exit_code == 2
    assert json.loads(plan_result.output)["status"] == "failed"
    artifact = tmp_path / "bad.json"
    artifact.write_text("not json")
    verify_result = runner.invoke(
        cli, ["batch", "verify", "--plan", str(artifact), "--format", "json"]
    )
    assert verify_result.exit_code == 2
    assert json.loads(verify_result.output)["status"] == "failed"


def test_plan_checks_query_membership_and_never_reads_bodies(tmp_path):
    client = assigned_client()
    with pytest.raises(ValueError, match="member"):
        batch_ops.build_plan(
            client, plan_input([{"id": "other", "category": "Work"}]), tmp_path / "x"
        )
    client.get_message.assert_not_called()
    client.get_message_metadata.assert_not_called()
    client.list_messages.assert_called_once_with(query="is:unread", max_results=2)


def test_label_list_json_schema_and_default_table_compatibility():
    client = MagicMock()
    client.list_labels.return_value = [Label(id="L1", name="Work")]
    with patch("gmail_cli.cli._create_client", return_value=client):
        json_result = CliRunner().invoke(cli, ["list", "labels", "--format", "json"])
        table_result = CliRunner().invoke(cli, ["list", "labels"])
    assert json_result.exit_code == table_result.exit_code == 0
    labels_response = json.loads(json_result.output)
    assert list(labels_response) == ["labels"]
    assert labels_response["labels"] == [{"id": "L1", "name": "Work", "type": "user"}]
    assert "Work" in table_result.output


def test_plan_label_normalization_exact_matching_override_and_deferred_creation(tmp_path):
    client = assigned_client()
    client.list_labels.return_value = [Label(id="L1", name=f"{chr(0xFF21)}lpha Work")]
    _, path, _ = create_plan(
        tmp_path,
        client,
        plan_input(label_map={"topic": "Alpha Work"}, messages=[{"id": "m1", "category": "topic"}]),
    )
    artifact = json.loads(path.read_text())
    assert artifact["assignments"][0]["label_id"] == "L1"
    client.create_label.assert_not_called()


def test_plan_artifact_is_private_versioned_and_contains_no_body(tmp_path):
    _client, path, result = create_plan(tmp_path)
    artifact = json.loads(path.read_text())
    assert artifact["schema_version"] == 1
    assert "body" not in path.read_text()
    assert os.stat(path).st_mode & 0o777 == 0o600
    assert set(result) >= {"results"}


def test_plan_atomic_write_failure_preserves_existing_artifact(tmp_path):
    destination = tmp_path / "plan.json"
    destination.write_text("old")
    with (
        patch.object(batch_ops.os, "replace", side_effect=OSError("fail")),
        pytest.raises(OSError, match="fail"),
    ):
        batch_ops._write_plan(destination, {"schema_version": 1})
    assert destination.read_text() == "old"


def test_apply_preflights_every_message_before_writes(tmp_path):
    client = assigned_client()
    path = tmp_path / "plan.json"
    batch_ops.build_plan(
        client,
        plan_input([{"id": "m1", "category": "Work"}, {"id": "m2", "category": "Work"}]),
        path,
    )
    client.list_messages.return_value = []
    with pytest.raises(ValueError, match="no longer in the query"):
        batch_ops.apply_plan(client, path)
    client.modify_message.assert_not_called()
    client.create_label.assert_not_called()


@pytest.mark.parametrize(
    "artifact_text", ["not json", "{}", '{"schema_version": 1, "assignments": [null]}']
)
def test_apply_rejects_malformed_artifact_without_writes(tmp_path, artifact_text):
    client = assigned_client()
    path = tmp_path / "malformed.json"
    path.write_text(artifact_text)
    with pytest.raises((ValueError, OSError, KeyError)):
        batch_ops.apply_plan(client, path)
    client.list_messages.assert_not_called()
    client.create_label.assert_not_called()
    client.modify_message.assert_not_called()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda plan: plan["assignments"].__setitem__(
            0, {**plan["assignments"][0], "label_name": []}
        ),
        lambda plan: plan["labels_to_create"].append({"label_name": [], "normalized_name": "new"}),
    ],
)
@pytest.mark.parametrize("operation", ["apply", "verify"])
def test_cli_rejects_wrong_nested_artifact_shapes_before_client_or_write(
    tmp_path, monkeypatch, mutate, operation
):
    _, path, _ = create_plan(tmp_path)
    artifact = json.loads(path.read_text())
    mutate(artifact)
    path.write_text(json.dumps(artifact))
    with patch("gmail_cli.cli._create_client", side_effect=AssertionError("client created")):
        result = CliRunner().invoke(
            cli,
            [
                "batch",
                operation,
                "--plan",
                str(path),
                *(["--dry-run"] if operation == "apply" else ["--format", "json"]),
            ],
        )
    assert result.exit_code == 2
    assert json.loads(result.output)["status"] == "failed"
    assert "results" in json.loads(result.output)
    assert "items" not in json.loads(result.output)


def test_cli_batch_json_errors_hide_traceback_and_sensitive_details(tmp_path):
    artifact = tmp_path / "broken.json"
    artifact.write_text('{"schema_version": 1, "assignments": [null]}')
    with patch("gmail_cli.cli._create_client", return_value=assigned_client()):
        result = CliRunner().invoke(cli, ["batch", "apply", "--plan", str(artifact)])
    assert result.exit_code == 2
    response = json.loads(result.output)
    assert response["status"] == "failed"
    assert "results" in response
    assert "Traceback" not in result.output
    assert "secret" not in result.output.lower()


def test_cli_batch_unknown_operation_is_rejected():
    result = CliRunner().invoke(cli, ["batch", "unknown"])
    assert result.exit_code != 0
    assert "Usage:" in result.output


def test_apply_dry_run_no_write_and_apply_preserves_inbox(tmp_path):
    client, path, _ = create_plan(tmp_path)
    with patch.object(batch_ops, "click_tty_confirm", return_value=True):
        dry = batch_ops.apply_plan(client, path, dry_run=True)
    assert dry["results"][0]["status"] == "preflight_ok"
    client.modify_message.assert_not_called()
    with patch.object(batch_ops, "click_tty_confirm", return_value=True):
        applied = batch_ops.apply_plan(client, path)
    assert applied["status"] == "success"
    client.modify_message.assert_called_once_with("m1", add_labels=["L1"], remove_labels=None)


def test_apply_archive_requires_separate_confirmation_and_removes_inbox(tmp_path):
    client, path, _ = create_plan(tmp_path)
    with patch.object(batch_ops, "click_tty_confirm", side_effect=[True, True]) as confirm:
        batch_ops.apply_plan(client, path, archive=True)
    assert confirm.call_count == 2
    client.modify_message.assert_called_once_with("m1", add_labels=["L1"], remove_labels=["INBOX"])


def test_apply_rejects_non_tty_without_writes(tmp_path):
    client, path, _ = create_plan(tmp_path)
    with (
        patch.object(batch_ops, "click_tty_confirm", return_value=False),
        pytest.raises(ValueError, match="TTY confirmation required"),
    ):
        batch_ops.apply_plan(client, path)
    client.modify_message.assert_not_called()


def test_apply_partial_creation_never_writes_messages(tmp_path):
    client = assigned_client()
    client.list_labels.return_value = []
    payload = plan_input(label_map={"topic": "New"}, messages=[{"id": "m1", "category": "topic"}])
    _, path, _ = create_plan(tmp_path, client, payload)
    client.create_label.side_effect = GmailError("failed")
    with patch.object(batch_ops, "click_tty_confirm", return_value=True):
        response = batch_ops.apply_plan(client, path)
    assert response["status"] == "partial"
    assert "results" in response
    assert "items" not in response
    client.modify_message.assert_not_called()


def test_apply_created_label_id_is_persisted_before_message_modification(tmp_path):
    client = assigned_client()
    client.list_labels.return_value = []
    _, path, _ = create_plan(
        tmp_path,
        client,
        plan_input([{"id": "m1", "category": "New"}]),
    )
    client.create_label.return_value = {"id": "NEW-ID", "name": "New"}
    with patch.object(batch_ops, "click_tty_confirm", return_value=True):
        response = batch_ops.apply_plan(client, path)
    assert response["status"] == "success"
    assert json.loads(path.read_text())["assignments"][0]["label_id"] == "NEW-ID"
    client.modify_message.assert_called_once_with("m1", add_labels=["NEW-ID"], remove_labels=None)


def test_apply_plan_write_failure_keeps_messages_unmodified(tmp_path):
    client, path, _ = create_plan(tmp_path)
    with (
        patch.object(batch_ops, "click_tty_confirm", return_value=True),
        patch.object(batch_ops, "_write_plan", side_effect=OSError("disk full")),
    ):
        response = batch_ops.apply_plan(client, path)
    assert response["status"] == "partial"
    assert response["errors"] == ["plan_update_failed"]
    assert response["results"] == []
    client.modify_message.assert_not_called()


def test_apply_detects_label_removed_after_plan_without_writes(tmp_path):
    client, path, _ = create_plan(tmp_path)
    client.list_labels.return_value = []
    with pytest.raises(ValueError, match="changed or disappeared"):
        batch_ops.apply_plan(client, path, dry_run=True)
    client.modify_message.assert_not_called()
    client.create_label.assert_not_called()


def test_apply_archive_decline_does_not_create_or_modify(tmp_path):
    client, path, _ = create_plan(tmp_path)
    with (
        patch.object(batch_ops, "click_tty_confirm", side_effect=[True, False]),
        pytest.raises(ValueError, match="Archive confirmation declined"),
    ):
        batch_ops.apply_plan(client, path, archive=True)
    client.create_label.assert_not_called()
    client.modify_message.assert_not_called()


def test_click_tty_confirm_accepts_using_click_input_stream(monkeypatch):
    @batch_ops.click.command()
    def confirm_command():
        click_value = batch_ops.click_tty_confirm("Proceed?")
        batch_ops.click.echo(str(click_value))

    monkeypatch.setattr(
        batch_ops.click,
        "get_text_stream",
        lambda name: type("TTY", (), {"isatty": lambda self: True})(),
    )
    monkeypatch.setattr(batch_ops.click, "confirm", lambda prompt, default=False: True)
    result = CliRunner().invoke(confirm_command)
    assert result.exit_code == 0
    assert result.output.rstrip().endswith("True")


@pytest.mark.parametrize("answer", [True, False])
def test_click_tty_confirm_tty_accepts_or_rejects(answer, monkeypatch):
    stream = MagicMock()
    stream.isatty.return_value = True
    confirm = MagicMock(return_value=answer)
    monkeypatch.setattr(batch_ops.click, "get_text_stream", lambda name: stream)
    monkeypatch.setattr(batch_ops.click, "confirm", confirm)
    assert batch_ops.click_tty_confirm("Proceed?") is answer
    confirm.assert_called_once_with("Proceed?", default=False)


def test_click_tty_confirm_non_tty_returns_false_without_prompt(monkeypatch):
    stream = MagicMock()
    stream.isatty.return_value = False
    confirm = MagicMock(side_effect=AssertionError("prompted"))
    monkeypatch.setattr(batch_ops.click, "get_text_stream", lambda name: stream)
    monkeypatch.setattr(batch_ops.click, "confirm", confirm)
    assert batch_ops.click_tty_confirm("Proceed?") is False
    confirm.assert_not_called()


def test_preflight_rejects_new_ambiguous_label_before_writes(tmp_path):
    client = assigned_client()
    client.list_labels.return_value = []
    _, path, _ = create_plan(
        tmp_path, client, plan_input(messages=[{"id": "m1", "category": "New"}])
    )
    client.list_labels.return_value = [Label("L1", "New"), Label("L2", " new ")]
    with pytest.raises(ValueError, match="Ambiguous label appeared after planning"):
        batch_ops.apply_plan(client, path)
    client.create_label.assert_not_called()
    client.modify_message.assert_not_called()


def test_creation_aborts_on_new_label_ambiguity_without_message_writes(tmp_path):
    client = assigned_client()
    client.list_labels.return_value = []
    _, path, _ = create_plan(
        tmp_path, client, plan_input(messages=[{"id": "m1", "category": "New"}])
    )
    client.list_labels.side_effect = [[], [Label("L1", "New"), Label("L2", " new ")]]
    with patch.object(batch_ops, "click_tty_confirm", return_value=True):
        response = batch_ops.apply_plan(client, path)
    assert response["status"] == "partial"
    assert response["errors"] == ["label_creation_failed"]
    client.create_label.assert_not_called()
    client.modify_message.assert_not_called()


def test_batch_cli_table_and_error_response(tmp_path):
    client = MagicMock()
    client.list_message_page.return_value = {"messages": [{"id": "m1"}]}
    client.get_message_metadata.return_value = msg("m1")
    with patch("gmail_cli.cli._create_client", return_value=client):
        table = CliRunner().invoke(cli, ["batch", "list", "--query", "q", "--format", "table"])
        client.list_message_page.side_effect = ValueError("invalid query")
        error = CliRunner().invoke(cli, ["batch", "list", "--query", "q"])
    assert table.exit_code == 0
    assert "m1" in table.output
    assert error.exit_code == 2
    assert json.loads(error.output)["results"] == []
    assert "invalid query" in json.loads(error.output)["errors"][0]


def test_plan_cli_success_writes_artifact_and_emits_results(tmp_path):
    client = assigned_client()
    source = tmp_path / "input.json"
    destination = tmp_path / "plan.json"
    source.write_text(json.dumps(plan_input()))
    with patch("gmail_cli.cli._create_client", return_value=client):
        result = CliRunner().invoke(
            cli, ["batch", "plan", "--input", str(source), "--out", str(destination)]
        )
    assert result.exit_code == 0
    response = json.loads(result.output)
    assert response["status"] == "success"
    assert response["results"][0]["message_id"] == "m1"
    assert json.loads(destination.read_text())["assignments"][0]["message_id"] == "m1"


@pytest.mark.parametrize(
    ("labels", "expected_exit", "status"),
    [(["L1", "INBOX"], 0, "success"), (["INBOX"], 3, "partial")],
)
def test_verify_cli_json_success_and_mismatch_results(tmp_path, labels, expected_exit, status):
    client, path, _ = create_plan(tmp_path)
    client.get_message_metadata.side_effect = None
    client.get_message_metadata.return_value = msg("m1", labels)
    with patch("gmail_cli.cli._create_client", return_value=client):
        result = CliRunner().invoke(
            cli, ["batch", "verify", "--plan", str(path), "--format", "json"]
        )
    assert result.exit_code == expected_exit
    response = json.loads(result.output)
    assert response["status"] == status
    assert response["results"][0]["message_id"] == "m1"
    assert response["results"][0]["status"] == ("success" if expected_exit == 0 else "mismatch")
    assert "items" not in response


def test_verify_cli_default_table_outputs_message_results_without_body(tmp_path):
    artifact = tmp_path / "plan.json"
    artifact.write_text("{}")
    client = MagicMock()
    response = {
        "status": "success",
        "results": [
            {"message_id": "m1", "status": "success", "body": "secret body"},
            {"message_id": "m2", "status": "mismatch", "body": "other body"},
        ],
    }
    with (
        patch("gmail_cli.cli._read_plan", return_value={}),
        patch("gmail_cli.cli._create_client", return_value=client),
        patch("gmail_cli.cli.verify_plan", return_value=response),
    ):
        result = CliRunner().invoke(cli, ["batch", "verify", "--plan", str(artifact)])

    assert result.exit_code == 0
    assert result.output.splitlines() == ["m1  success", "m2  mismatch"]
    assert "body" not in result.output


def test_apply_write_failure_is_fail_fast_with_partial_results(tmp_path):
    client, path, _ = create_plan(
        tmp_path,
        payload=plan_input([{"id": "m1", "category": "Work"}, {"id": "m2", "category": "Work"}]),
    )
    client.modify_message.side_effect = [GmailError("fail"), None]
    with patch.object(batch_ops, "click_tty_confirm", return_value=True):
        response = batch_ops.apply_plan(client, path)
    assert response["status"] == "partial"
    assert [r["status"] for r in response["results"]] == ["failed", "not_attempted"]
    assert client.modify_message.call_count == 1


def test_verify_reloads_metadata_and_reports_actual_mismatch(tmp_path):
    client, path, _ = create_plan(tmp_path)
    client.get_message_metadata.return_value = msg("m1", ["INBOX"])
    response = batch_ops.verify_plan(client, path)
    assert response["status"] == "partial"
    assert response["results"][0]["status"] == "mismatch"
    client.get_message_metadata.assert_called_with("m1")
    assert "results" in response
    assert "items" not in response


def test_verify_reports_matching_message_and_operation_error(tmp_path):
    client, path, _ = create_plan(tmp_path)
    with patch.object(batch_ops, "click_tty_confirm", return_value=True):
        batch_ops.apply_plan(client, path)
    plan = json.loads(path.read_text())
    client.get_message_metadata.side_effect = None
    client.get_message_metadata.return_value = msg(
        "m1", [plan["assignments"][0]["label_id"], "INBOX"]
    )
    response = batch_ops.verify_plan(client, path)
    assert response["status"] == "success"
    assert response["counts"] == {"success": 1, "mismatch": 0}
    assert response["results"][0] == {
        "message_id": "m1",
        "status": "success",
        "label_matches": True,
        "archive_matches": True,
        "label_exists": True,
    }


def test_harness_command_removed_and_standalone_classify_preserved():
    runner = CliRunner()
    help_result = runner.invoke(cli, ["--help"])
    assert "harness" not in help_result.output
    assert runner.invoke(cli, ["classify", "--help"]).exit_code == 0
