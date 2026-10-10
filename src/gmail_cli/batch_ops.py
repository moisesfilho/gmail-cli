"""Validated, file-backed Gmail batch plans and bounded read operations."""

import json
import os
import tempfile
import unicodedata
import uuid
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

import click

from .gmail_client import GmailError

MAX_BODY_CHARS = 16_000


def normalize_label(name):
    return " ".join(unicodedata.normalize("NFKC", name).strip().split()).casefold()


def _write_plan(path, plan):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=destination.parent, prefix=f".{destination.name}.")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(plan, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        os.chmod(destination, 0o600)
    except BaseException:
        with suppress(OSError):
            os.unlink(temporary)
        raise


def _read_plan(path):
    try:
        with open(path, encoding="utf-8") as stream:
            plan = json.load(stream)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError("Invalid plan artifact") from error
    if (
        not isinstance(plan, dict)
        or type(plan.get("schema_version")) is not int
        or plan["schema_version"] != 1
        or not isinstance(plan.get("plan_id"), str)
        or not isinstance(plan.get("created_at"), str)
        or not isinstance(plan.get("query"), str)
        or type(plan.get("max_results")) is not int
        or not 1 <= plan["max_results"] <= 100
        or not isinstance(plan.get("assignments"), list)
        or not isinstance(plan.get("labels_to_create"), list)
        or type(plan.get("archive")) is not bool
    ):
        raise ValueError("Invalid plan artifact")
    for assignment in plan["assignments"]:
        if (
            not isinstance(assignment, dict)
            or not isinstance(assignment.get("message_id"), str)
            or not assignment["message_id"].strip()
            or not isinstance(assignment.get("category"), str)
            or not isinstance(assignment.get("label_name"), str)
            or (
                assignment.get("label_id") is not None
                and not isinstance(assignment["label_id"], str)
            )
            or type(assignment.get("expected_archived")) is not bool
        ):
            raise ValueError("Invalid plan artifact")
    for label in plan["labels_to_create"]:
        if (
            not isinstance(label, dict)
            or not isinstance(label.get("label_name"), str)
            or not isinstance(label.get("normalized_name"), str)
        ):
            raise ValueError("Invalid plan artifact")
    return plan


def list_batch(client, query, maximum, include_body=False):
    if not isinstance(query, str) or type(maximum) is not int or not 1 <= maximum <= 100:
        raise ValueError("query must be text and max must be between 1 and 100")
    page = client.list_message_page(userId="me", q=query, maxResults=maximum)
    ids = list(dict.fromkeys(row["id"] for row in page.get("messages", []) if row.get("id")))
    if include_body:
        messages = client.get_messages(ids)
        results = []
        for message_id in ids:
            message = messages[message_id]
            if isinstance(message, GmailError):
                raise message
            results.append(
                {
                    "id": message.id,
                    "thread_id": message.thread_id,
                    "from": message.from_,
                    "to": message.to,
                    "subject": message.subject,
                    "date": message.date,
                    "label_ids": message.label_ids,
                    "body": (message.body or "")[:MAX_BODY_CHARS],
                }
            )
    else:
        results = []
        for message_id in ids:
            message = client.get_message_metadata(message_id)
            results.append(
                {
                    "id": message.id,
                    "thread_id": message.thread_id,
                    "from": message.from_,
                    "subject": message.subject,
                    "date": message.date,
                    "label_ids": message.label_ids,
                }
            )
    return {"command": "gmail batch list", "status": "success", "results": results}


def _validate_input(data):
    if (
        not isinstance(data, dict)
        or type(data.get("version")) is not int
        or data["version"] != 1
        or not isinstance(data.get("query"), str)
        or type(data.get("max_results")) is not int
        or not 1 <= data["max_results"] <= 100
        or not isinstance(data.get("messages"), list)
    ):
        raise ValueError("Invalid batch plan input schema")
    mapping = data.get("label_map", {})
    if not isinstance(mapping, dict):
        raise ValueError("label_map must be an object")
    for key, value in mapping.items():
        if (
            not isinstance(key, str)
            or not key.strip()
            or not isinstance(value, str)
            or not value.strip()
        ):
            raise ValueError("Invalid label_map entry")
    seen = set()
    for item in data["messages"]:
        if (
            not isinstance(item, dict)
            or set(item) != {"id", "category"}
            or not isinstance(item["id"], str)
            or not item["id"].strip()
            or not isinstance(item["category"], str)
            or not item["category"].strip()
            or item["id"] in seen
        ):
            raise ValueError("Invalid or duplicate message assignment")
        seen.add(item["id"])
    return mapping


def build_plan(client, data, output_path):
    mapping = _validate_input(data)
    memberships = {
        message.id
        for message in client.list_messages(query=data["query"], max_results=data["max_results"])
    }
    assignments = data["messages"]
    if any(item["id"] not in memberships for item in assignments):
        raise ValueError("An assigned message is not a member of the live query")
    labels = client.list_labels()
    indexed = {}
    for label in labels:
        indexed.setdefault(normalize_label(label.name), []).append(label)
    resolved, create = {}, {}
    for item in assignments:
        category = item["category"]
        target = mapping.get(category, category)
        normalized = normalize_label(target)
        if normalized in resolved and resolved[normalized][0] != target:
            raise ValueError("Duplicate normalized label target")
        matches = indexed.get(normalized, [])
        if len(matches) > 1:
            raise ValueError("Ambiguous normalized existing label")
        if matches:
            resolved[normalized] = (target, matches[0].name, matches[0].id)
        else:
            resolved[normalized] = (target, target, None)
            create[normalized] = target
    planned = []
    for item in assignments:
        target = mapping.get(item["category"], item["category"])
        _, canonical, label_id = resolved[normalize_label(target)]
        planned.append(
            {
                "message_id": item["id"],
                "category": item["category"],
                "label_name": canonical,
                "label_id": label_id,
                "expected_archived": False,
            }
        )
    plan = {
        "schema_version": 1,
        "plan_id": str(uuid.uuid4()),
        "created_at": datetime.now(UTC).isoformat(),
        "query": data["query"],
        "max_results": data["max_results"],
        "assignments": planned,
        "labels_to_create": [
            {"label_name": name, "normalized_name": key} for key, name in create.items()
        ],
        "archive": False,
    }
    _write_plan(output_path, plan)
    return {
        "command": "gmail batch plan",
        "status": "success",
        "plan_id": plan["plan_id"],
        "results": planned,
        "labels_to_create": plan["labels_to_create"],
    }


def _preflight(client, plan):
    members = {
        message.id
        for message in client.list_messages(query=plan["query"], max_results=plan["max_results"])
    }
    labels = client.list_labels()
    label_index = {label.id: label for label in labels}
    by_name = {}
    for label in labels:
        by_name.setdefault(normalize_label(label.name), []).append(label)
    prepared = []
    for item in plan["assignments"]:
        if item["message_id"] not in members:
            raise ValueError("A planned message is no longer in the query")
        client.get_message_metadata(item["message_id"])
        if item["label_id"]:
            label = label_index.get(item["label_id"])
            if not label or normalize_label(label.name) != normalize_label(item["label_name"]):
                raise ValueError("A planned label changed or disappeared")
        elif len(by_name.get(normalize_label(item["label_name"]), [])) > 1:
            raise ValueError("Ambiguous label appeared after planning")
        prepared.append(item)
    return prepared


def apply_plan(client, path, dry_run=False, archive=False):
    plan = _read_plan(path)
    prepared = _preflight(client, plan)
    if dry_run:
        return {
            "command": "gmail batch apply",
            "status": "success",
            "plan_id": plan["plan_id"],
            "results": [
                {
                    "message_id": row["message_id"],
                    "status": "preflight_ok",
                    "expected_archived": bool(archive),
                }
                for row in prepared
            ],
        }
    if not click_tty_confirm("Apply this Gmail batch plan?"):
        raise ValueError("TTY confirmation required")
    if archive and not click_tty_confirm("Confirm archive of these messages?"):
        raise ValueError("Archive confirmation declined")
    created = {}
    try:
        for entry in plan["labels_to_create"]:
            matches = [
                label
                for label in client.list_labels()
                if normalize_label(label.name) == entry["normalized_name"]
            ]
            if len(matches) > 1:
                raise ValueError("Ambiguous label appeared before creation")
            label = matches[0] if matches else client.create_label(entry["label_name"])
            created[entry["normalized_name"]] = label["id"] if isinstance(label, dict) else label.id
    except (GmailError, ValueError, OSError, KeyError):
        return {
            "command": "gmail batch apply",
            "status": "partial",
            "plan_id": plan["plan_id"],
            "results": [],
            "created_label_ids": created,
            "errors": ["label_creation_failed"],
        }
    by_name = {
        entry["normalized_name"]: created[entry["normalized_name"]]
        for entry in plan["labels_to_create"]
    }
    for item in prepared:
        if not item["label_id"]:
            item["label_id"] = by_name[normalize_label(item["label_name"])]
    plan["archive"] = bool(archive)
    for item in prepared:
        item["expected_archived"] = bool(archive)
    try:
        _write_plan(path, plan)
    except OSError:
        return {
            "command": "gmail batch apply",
            "status": "partial",
            "plan_id": plan["plan_id"],
            "results": [],
            "created_label_ids": created,
            "errors": ["plan_update_failed"],
        }
    results = []
    for item in prepared:
        try:
            client.modify_message(
                item["message_id"],
                add_labels=[item["label_id"]],
                remove_labels=["INBOX"] if archive else None,
            )
            results.append({"message_id": item["message_id"], "status": "success"})
        except GmailError:
            results.append({"message_id": item["message_id"], "status": "failed"})
            results.extend(
                {"message_id": rest["message_id"], "status": "not_attempted"}
                for rest in prepared[len(results) :]
            )
            break
    status = "partial" if any(row["status"] != "success" for row in results) else "success"
    return {
        "command": "gmail batch apply",
        "status": status,
        "plan_id": plan["plan_id"],
        "results": results,
        "created_label_ids": created,
    }


def click_tty_confirm(prompt):
    if not click.get_text_stream("stdin").isatty():
        return False
    return click.confirm(prompt, default=False)


def verify_plan(client, path):
    plan = _read_plan(path)
    results, errors = [], []
    labels = {label.id: label for label in client.list_labels()}
    for item in plan["assignments"]:
        message = client.get_message_metadata(item["message_id"])
        label_matches = item["label_id"] in message.label_ids
        archive_matches = ("INBOX" not in message.label_ids) == item["expected_archived"]
        results.append(
            {
                "message_id": item["message_id"],
                "status": "success" if label_matches and archive_matches else "mismatch",
                "label_matches": label_matches,
                "archive_matches": archive_matches,
                "label_exists": item["label_id"] in labels,
            }
        )
    counts = {
        "success": sum(row["status"] == "success" for row in results),
        "mismatch": sum(row["status"] != "success" for row in results),
    }
    return {
        "command": "gmail batch verify",
        "status": "success" if not counts["mismatch"] else "partial",
        "plan_id": plan["plan_id"],
        "counts": counts,
        "results": results,
        "errors": errors,
    }
