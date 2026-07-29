import json
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://mail.google.com/"]


class AuthError(Exception):
    pass


class AuthService:
    TOKEN_FILE = os.path.expanduser("~/.gmail_cli_token.json")
    CREDENTIALS_FILE = (
        os.path.expanduser("~/.gmail_cli_credentials.json")
        if os.path.exists(os.path.expanduser("~/.gmail_cli_credentials.json"))
        else ".gmail_cli_credentials.json"
    )

    def get_service(self):
        creds = self._load_credentials()
        if creds and not creds.valid:
            creds = self._refresh_credentials(creds)
        if not creds:
            creds = self._create_from_oauth_flow()
        self._save_credentials(creds)
        return build("gmail", "v1", credentials=creds)

    def _load_credentials(self):
        if os.path.exists(self.TOKEN_FILE):
            with open(self.TOKEN_FILE) as f:
                return Credentials.from_authorized_user_info(json.load(f))
        return None

    def _save_credentials(self, creds):
        with open(self.TOKEN_FILE, "w") as f:
            json.dump(json.loads(creds.to_json()), f)

    def _refresh_credentials(self, creds):
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            return creds
        return None

    def _create_from_oauth_flow(self):
        if not os.path.exists(self.CREDENTIALS_FILE):
            raise AuthError(
                f"Arquivo de credenciais não encontrado: {self.CREDENTIALS_FILE}\n"
                "Crie um projeto em https://console.cloud.google.com/,\n"
                "ative a Gmail API, baixe as credenciais OAuth 2.0\n"
                "e salve como ~/.gmail_cli_credentials.json"
            )
        flow = InstalledAppFlow.from_client_secrets_file(self.CREDENTIALS_FILE, SCOPES)
        return flow.run_local_server(port=0)
