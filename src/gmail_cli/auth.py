import json
import os
import time
import webbrowser
from pathlib import Path

import click
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://mail.google.com/"]

GCP_CONSOLE_URL = (
    "https://console.cloud.google.com/apis/credentials?project=_&supportedpurview=project"
)
GMAIL_API_URL = "https://console.cloud.google.com/apis/library/gmail.googleapis.com?project=_"


class AuthError(Exception):
    pass


class CredentialsNotFoundError(AuthError):
    pass


class AuthService:
    TOKEN_FILE = os.path.expanduser("~/.gmail_cli_token.json")
    CREDENTIALS_FILE = os.path.expanduser("~/.gmail_cli_credentials.json")

    def get_service(self):
        creds = self._load_credentials()
        if creds and not creds.valid:
            creds = self._refresh_credentials(creds)
        if not creds:
            creds = self._create_from_oauth_flow()
        self._save_credentials(creds)
        return build("gmail", "v1", credentials=creds)

    def login(self):
        creds = self._create_from_oauth_flow()
        self._save_credentials(creds)

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
            _open_guide_and_wait()
        flow = InstalledAppFlow.from_client_secrets_file(self.CREDENTIALS_FILE, SCOPES)
        return flow.run_local_server(port=0)

    def revoke(self):
        creds = self._load_credentials()
        if creds:
            creds.revoke(Request())
        if os.path.exists(self.TOKEN_FILE):
            os.remove(self.TOKEN_FILE)


def _open_guide_and_wait():
    creds_path = str(Path("~/.gmail_cli_credentials.json").expanduser())
    click.echo(
        "═══ Autenticação necessária ═══\n\n"
        "Para usar este CLI, você precisa:\n\n"
        "  1. Um projeto no Google Cloud\n"
        "  2. A Gmail API ativada\n"
        "  3. Credenciais OAuth 2.0 do tipo 'Aplicativo para desktop'\n\n"
        "Seu navegador será aberto nas páginas necessárias.\n"
        "Siga os passos e salve o arquivo em:\n"
        f"  {creds_path}\n"
    )
    click.prompt("Pressione Enter para abrir o Google Cloud Console", default="", prompt_suffix="")
    webbrowser.open(GMAIL_API_URL)
    click.echo(
        "Ative a Gmail API e clique em 'CRIAR CREDENCIAIS' >\n"
        "   'ID do cliente OAuth' > 'Aplicativo para desktop'.\n"
        "Depois baixe o JSON e salve no caminho acima.\n"
    )
    wait_for_file(creds_path)


def wait_for_file(path: str, timeout: int = 300):
    click.echo(f"Aguardando {path}...", nl=False)
    start = time.time()
    while not os.path.exists(path):
        if time.time() - start > timeout:
            raise CredentialsNotFoundError(
                f"Arquivo {path} não encontrado após {timeout}s.\n"
                "Execute 'gmail auth login' quando tiver o arquivo."
            )
        time.sleep(2)
        click.echo(".", nl=False)
    click.echo(" OK")
