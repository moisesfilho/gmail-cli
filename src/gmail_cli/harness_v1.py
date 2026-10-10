"""Versioned JSON harness operations with bounded, explicit Gmail access."""

import base64
import hashlib
import json

from .gmail_client import GmailError

MAX_BODY_BYTES = 16 * 1024
MAX_PAGE_BODY_BYTES = 256 * 1024
SYSTEM_LABELS = {
    "INBOX",
    "UNREAD",
    "STARRED",
    "IMPORTANT",
    "SENT",
    "DRAFT",
    "SPAM",
    "TRASH",
    "CATEGORY_PERSONAL",
    "CATEGORY_SOCIAL",
    "CATEGORY_PROMOTIONS",
    "CATEGORY_UPDATES",
    "CATEGORY_FORUMS",
}


def validate_v1_request(request):
    """Validate the complete v1 request before any OAuth/Gmail access."""
    if (
        not isinstance(request, dict)
        or type(request.get("version")) is not int
        or request["version"] != 1
    ):
        raise ValueError("Invalid protocol version")
    operation = request.get("operation")
    if operation is None:
        operation = "apply" if "assignments" in request else "list"
    elif operation not in {"list", "apply"}:
        raise ValueError("Unsupported v1 operation")
    if operation == "list":
        allowed = {"version", "operation", "query", "label_ids", "limit", "cursor"}
        query, labels = request.get("query", ""), request.get("label_ids", [])
        limit, cursor = request.get("limit", 50), request.get("cursor")
        if (
            set(request) - allowed
            or not isinstance(query, str)
            or not isinstance(labels, list)
            or any(not isinstance(label, str) or not label for label in labels)
            or type(limit) is not int
            or not 1 <= limit <= 100
            or (cursor is not None and not isinstance(cursor, str))
        ):
            raise ValueError("Invalid v1 list schema")
        if cursor is not None:
            _decode_cursor(cursor, _cursor_fingerprint(query, sorted(set(labels))))
    else:
        if (
            set(request) - {"operation"}
            != {"version", "authorize", "archive_authorized", "assignments"}
            or request.get("authorize") is not True
            or type(request.get("archive_authorized")) is not bool
            or not isinstance(request.get("assignments"), list)
            or not request["assignments"]
        ):
            raise ValueError("Invalid v1 apply schema")
        seen = set()
        for item in request["assignments"]:
            if (
                not isinstance(item, dict)
                or set(item) != {"message_id", "labels"}
                or not isinstance(item.get("message_id"), str)
                or not item["message_id"]
                or item["message_id"] in seen
                or not isinstance(item.get("labels"), list)
                or not item["labels"]
                or any(not isinstance(label, str) or not label for label in item["labels"])
            ):
                raise ValueError("Invalid v1 assignments")
            seen.add(item["message_id"])


def _cursor_fingerprint(query, label_ids):
    filters = json.dumps([query, sorted(set(label_ids))], separators=(",", ":"))
    return hashlib.sha256(filters.encode("utf-8")).hexdigest()


def _decode_cursor(cursor, fingerprint):
    if not isinstance(cursor, str) or not cursor or len(cursor) > 8192:
        raise ValueError("Invalid cursor")
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid cursor") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("v") != 1
        or not isinstance(payload.get("p"), str)
        or not payload["p"]
        or payload.get("f") != fingerprint
    ):
        raise ValueError("Invalid or mismatched cursor")
    return payload["p"]


def _encode_cursor(page_token, fingerprint):
    payload = json.dumps(
        {"v": 1, "p": page_token, "f": fingerprint}, separators=(",", ":")
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _bounded_body(body, budget):
    body = (body or "").replace("\r\n", "\n").replace("\r", "\n")
    if _serialized_body_size(body) <= budget:
        return body, False
    marker = "\n...[truncated]"
    if _serialized_body_size(marker) > budget:
        return "", True
    low, high = 0, len(body)
    while low < high:
        middle = (low + high + 1) // 2
        if _serialized_body_size(body[:middle] + marker) <= budget:
            low = middle
        else:
            high = middle - 1
    return body[:low] + marker, True


def _serialized_body_size(body):
    return len(json.dumps(body, ensure_ascii=False).encode("utf-8"))


def list_v1(client, request):
    allowed = {"version", "operation", "query", "label_ids", "limit", "cursor"}
    if (
        set(request) - allowed
        or type(request.get("version")) is not int
        or request["version"] != 1
        or request.get("operation", "list") != "list"
    ):
        raise ValueError("Invalid v1 list schema")
    query, labels = request.get("query", ""), request.get("label_ids", [])
    limit, cursor = request.get("limit", 50), request.get("cursor")
    if (
        not isinstance(query, str)
        or not isinstance(labels, list)
        or any(not isinstance(label, str) or not label for label in labels)
        or type(limit) is not int
        or not 1 <= limit <= 100
        or (cursor is not None and not isinstance(cursor, str))
    ):
        raise ValueError("Invalid v1 list filters")
    labels = sorted(set(labels))
    fingerprint = _cursor_fingerprint(query, labels)
    page_token = _decode_cursor(cursor, fingerprint) if cursor is not None else None
    params = {"userId": "me", "maxResults": limit}
    if query:
        params["q"] = query
    if labels:
        params["labelIds"] = labels
    if page_token:
        params["pageToken"] = page_token
    result = client.list_message_page(**params)
    ids = list(dict.fromkeys(item["id"] for item in result.get("messages", []) if item.get("id")))
    messages, used_bytes = [], 0
    messages_by_id = client.get_messages(ids)
    for index, message_id in enumerate(ids):
        message = messages_by_id[message_id]
        if isinstance(message, GmailError):
            raise message
        record = {
            "id": message.id,
            "thread_id": message.thread_id,
            "from": message.from_,
            "to": message.to,
            "subject": message.subject,
            "date": message.date,
            "label_ids": message.label_ids,
        }
        remaining_bodies = len(ids) - index - 1
        available_page_bytes = MAX_PAGE_BODY_BYTES - used_bytes - 2 * remaining_bodies
        body, truncated = _bounded_body(message.body, min(MAX_BODY_BYTES, available_page_bytes))
        record["body"] = body
        if truncated:
            record["body_truncated"] = True
        used_bytes += _serialized_body_size(body)
        messages.append(record)
    next_token = result.get("nextPageToken")
    return {
        "version": 1,
        "messages": messages,
        "next_cursor": _encode_cursor(next_token, fingerprint) if next_token else None,
        "has_more": bool(next_token),
    }


def apply_v1(client, request):  # noqa: PLR0912
    if (
        set(request) - {"operation"}
        != {"version", "authorize", "archive_authorized", "assignments"}
        or request.get("operation", "apply") != "apply"
        or type(request.get("version")) is not int
        or request["version"] != 1
        or request.get("authorize") is not True
        or type(request.get("archive_authorized")) is not bool
        or not isinstance(request.get("assignments"), list)
        or not request["assignments"]
    ):
        raise ValueError("Invalid or unauthorized v1 apply request")
    assignments = request["assignments"]
    ids = []
    valid_shape = True
    for item in assignments:
        if (
            not isinstance(item, dict)
            or set(item) != {"message_id", "labels"}
            or not isinstance(item.get("message_id"), str)
            or not item["message_id"]
            or not isinstance(item.get("labels"), list)
            or not item["labels"]
            or any(not isinstance(label, str) or not label for label in item["labels"])
        ):
            valid_shape = False
            continue
        ids.append(item["message_id"])
    if not valid_shape or len(ids) != len(set(ids)):
        raise ValueError("Invalid assignments or duplicate message IDs")

    results = [
        {
            "message_id": item["message_id"],
            "status": "not_attempted",
            "added_label_ids": [],
            "removed_label_ids": [],
            "error": None,
        }
        for item in assignments
    ]
    labels = client.list_labels()
    by_name = {label.name: label for label in labels}
    by_id = {label.id: label for label in labels}
    prepared, failures = [], False
    for index, item in enumerate(assignments):
        try:
            message = client.get_message(item["message_id"])
            if not message.id:
                raise ValueError("Message does not exist")
            resolved = []
            for name_or_id in item["labels"]:
                label = by_id.get(name_or_id) or by_name.get(name_or_id)
                if not label or label.id in SYSTEM_LABELS or label.name.upper() in SYSTEM_LABELS:
                    raise ValueError("Unknown or system label")
                if label.id not in resolved:
                    resolved.append(label.id)
            remove = []
            if request["archive_authorized"]:
                remove = ["INBOX"] if "INBOX" in message.label_ids else []
            prepared.append((index, item["message_id"], resolved, remove))
        except (GmailError, ValueError, KeyError):
            failures = True
            results[index]["status"] = "failed"
            results[index]["error"] = "preflight_failed"
    if failures:
        return {"status": "preflight_failed", "results": results}

    any_failed = False
    for index, message_id, add_ids, remove_ids in prepared:
        try:
            client.modify_message(message_id, add_labels=add_ids, remove_labels=remove_ids)
            results[index].update(
                status="success", added_label_ids=add_ids, removed_label_ids=remove_ids
            )
        except GmailError:
            any_failed = True
            results[index]["status"] = "failed"
            results[index]["error"] = "gmail_write_failed"
            break
    status = (
        "partial"
        if any_failed and any(r["status"] == "success" for r in results)
        else ("failed" if any_failed else "success")
    )
    return {"status": status, "results": results}
