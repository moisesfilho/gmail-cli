import base64
import os
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from googleapiclient.errors import HttpError

from .models import Draft, Label, Message


class GmailError(Exception):
    pass


class GmailClient:
    def __init__(self, service):
        self._service = service

    def list_messages(self, query="", max_results=20, label_ids=None):
        params = {"userId": "me", "maxResults": max_results}
        if query:
            params["q"] = query
        if label_ids:
            params["labelIds"] = label_ids if isinstance(label_ids, list) else [label_ids]
        try:
            result = self._service.users().messages().list(**params).execute()
            messages = result.get("messages", [])
            return [self._build_message_meta(m) for m in messages]
        except HttpError as e:
            raise GmailError(f"Erro ao listar mensagens: {e}")

    def _build_message_meta(self, msg_data):
        meta = (
            self._service.users()
            .messages()
            .get(
                userId="me",
                id=msg_data["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            )
            .execute()
        )
        headers = {h["name"]: h["value"] for h in meta["payload"]["headers"]}
        return Message(
            id=msg_data["id"],
            thread_id=meta["threadId"],
            from_=headers.get("From", ""),
            subject=headers.get("Subject", ""),
            date=headers.get("Date", ""),
            label_ids=meta.get("labelIds", []),
        )

    def get_message(self, msg_id):
        try:
            msg = (
                self._service.users()
                .messages()
                .get(userId="me", id=msg_id, format="full")
                .execute()
            )
        except HttpError as e:
            raise GmailError(f"Erro ao obter mensagem: {e}")
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        return Message(
            id=msg["id"],
            thread_id=msg["threadId"],
            from_=headers.get("From", ""),
            subject=headers.get("Subject", ""),
            date=headers.get("Date", ""),
            to=headers.get("To", ""),
            body=self._extract_body(msg["payload"]),
            label_ids=msg.get("labelIds", []),
        )

    def _decode_body(self, payload_body):
        data = payload_body["data"]
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    def _extract_body(self, payload):
        if "parts" in payload:
            for part in payload["parts"]:
                if part["mimeType"] == "text/plain" and "data" in part.get("body", {}):
                    return self._decode_body(part["body"])
            for part in payload["parts"]:
                if part["mimeType"] == "text/html" and "data" in part.get("body", {}):
                    return self._decode_body(part["body"])
        if "data" in payload.get("body", {}):
            return self._decode_body(payload["body"])
        return ""

    def send_message(self, to, subject, body_text, cc=None, bcc=None, attachments=None):  # noqa: PLR0913, PLR0917
        mime_msg = self._build_mime_message(to, subject, body_text, cc, bcc, attachments)
        raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode()
        try:
            return self._service.users().messages().send(userId="me", body={"raw": raw}).execute()
        except HttpError as e:
            raise GmailError(f"Erro ao enviar e-mail: {e}")

    def _build_mime_message(self, to, subject, body_text, cc=None, bcc=None, attachments=None):  # noqa: PLR0913, PLR0917
        msg = MIMEMultipart()
        msg["To"] = to
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc
        if bcc:
            msg["Bcc"] = bcc
        msg.attach(MIMEText(body_text, "plain"))
        if attachments:
            for filepath in attachments:
                self._attach_file(msg, filepath)
        return msg

    def _attach_file(self, mime_msg, filepath):
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Anexo não encontrado: {filepath}")
        with open(filepath, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{os.path.basename(filepath)}"',
            )
            mime_msg.attach(part)

    def list_labels(self):
        try:
            result = self._service.users().labels().list(userId="me").execute()
            return [Label(id=lab["id"], name=lab["name"]) for lab in result.get("labels", [])]
        except HttpError as e:
            raise GmailError(f"Erro ao listar labels: {e}")

    def create_label(self, name, label_list_visibility="labelShow", message_list_visibility="show"):
        body = {
            "name": name,
            "labelListVisibility": label_list_visibility,
            "messageListVisibility": message_list_visibility,
        }
        try:
            return self._service.users().labels().create(userId="me", body=body).execute()
        except HttpError as e:
            raise GmailError(f"Erro ao criar label: {e}")

    def delete_label(self, label_id):
        try:
            self._service.users().labels().delete(userId="me", id=label_id).execute()
        except HttpError as e:
            raise GmailError(f"Erro ao deletar label: {e}")

    def modify_message(self, msg_id, add_labels=None, remove_labels=None):
        body = {}
        if add_labels:
            body["addLabelIds"] = add_labels if isinstance(add_labels, list) else [add_labels]
        if remove_labels:
            body["removeLabelIds"] = (
                remove_labels if isinstance(remove_labels, list) else [remove_labels]
            )
        try:
            return (
                self._service.users().messages().modify(userId="me", id=msg_id, body=body).execute()
            )
        except HttpError as e:
            raise GmailError(f"Erro ao modificar mensagem: {e}")

    def list_drafts(self, max_results=20):
        try:
            result = (
                self._service.users().drafts().list(userId="me", maxResults=max_results).execute()
            )
            return [self._build_draft_meta(d) for d in result.get("drafts", [])]
        except HttpError as e:
            raise GmailError(f"Erro ao listar rascunhos: {e}")

    def _build_draft_meta(self, draft_data):
        meta = (
            self._service.users()
            .drafts()
            .get(
                userId="me",
                id=draft_data["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            )
            .execute()
        )
        msg = meta["message"]
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        return Draft(
            id=draft_data["id"],
            message_id=msg["id"],
            from_=headers.get("From", ""),
            subject=headers.get("Subject", ""),
            date=headers.get("Date", ""),
        )

    def create_draft(self, to, subject, body_text, cc=None, bcc=None):
        mime_msg = self._build_mime_message(to, subject, body_text, cc, bcc)
        raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode()
        try:
            return (
                self._service.users()
                .drafts()
                .create(userId="me", body={"message": {"raw": raw}})
                .execute()
            )
        except HttpError as e:
            raise GmailError(f"Erro ao criar rascunho: {e}")

    def send_draft(self, draft_id):
        try:
            return self._service.users().drafts().send(userId="me", body={"id": draft_id}).execute()
        except HttpError as e:
            raise GmailError(f"Erro ao enviar rascunho: {e}")

    def delete_draft(self, draft_id):
        try:
            self._service.users().drafts().delete(userId="me", id=draft_id).execute()
        except HttpError as e:
            raise GmailError(f"Erro ao deletar rascunho: {e}")

    def download_attachments(self, msg_id, output_dir="."):
        try:
            msg = (
                self._service.users()
                .messages()
                .get(userId="me", id=msg_id, format="full")
                .execute()
            )
        except HttpError as e:
            raise GmailError(f"Erro ao obter mensagem: {e}")
        os.makedirs(output_dir, exist_ok=True)
        downloaded = []
        parts = [msg["payload"]]
        while parts:
            part = parts.pop()
            if "parts" in part:
                parts.extend(part["parts"])
            if part.get("filename"):
                data = self._get_attachment_data(msg_id, part)
                if data:
                    filepath = os.path.join(output_dir, part["filename"])
                    with open(filepath, "wb") as f:
                        f.write(data)
                    downloaded.append(filepath)
        return downloaded

    def _get_attachment_data(self, msg_id, part):
        if "data" in part.get("body", {}):
            return base64.urlsafe_b64decode(part["body"]["data"])
        if "attachmentId" in part.get("body", {}):
            try:
                att = (
                    self._service.users()
                    .messages()
                    .attachments()
                    .get(userId="me", messageId=msg_id, id=part["body"]["attachmentId"])
                    .execute()
                )
                return base64.urlsafe_b64decode(att["data"])
            except HttpError:
                return None
        return None

    def trash_message(self, msg_id):
        try:
            self._service.users().messages().trash(userId="me", id=msg_id).execute()
        except HttpError as e:
            raise GmailError(f"Erro ao mover para lixeira: {e}")

    def delete_message(self, msg_id):
        try:
            self._service.users().messages().delete(userId="me", id=msg_id).execute()
        except HttpError as e:
            raise GmailError(f"Erro ao deletar mensagem: {e}")

    def untrash_message(self, msg_id):
        try:
            self._service.users().messages().untrash(userId="me", id=msg_id).execute()
        except HttpError as e:
            raise GmailError(f"Erro ao restaurar mensagem: {e}")
