import contextlib
import json
import logging
import os
import pickle  # nosec B403
import tempfile
import time
import webbrowser

import click
import requests as req_lib
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ["https://mail.google.com/"]

GCP_CONSOLE_URL = (
    "https://console.cloud.google.com/apis/credentials?project=_&supportedpurview=project"
)
GMAIL_API_URL = "https://console.cloud.google.com/apis/library/gmail.googleapis.com?project=_"


class AuthError(Exception):
    pass


class CredentialsNotFoundError(AuthError):
    pass


DATA_DIR = os.path.expanduser("~/.gmail-cli")
_OLD_TOKEN_FILE = os.path.expanduser("~/.gmail_cli_token.pickle")
_OLD_TOKEN_FILE_JSON = os.path.expanduser("~/.gmail_cli_token.json")
_OLD_CREDENTIALS_FILE = os.path.expanduser("~/.gmail_cli_credentials.json")
_OLD_CONFIG_FILE = os.path.expanduser("~/.gmail_cli_config.json")


class AuthService:
    TOKEN_FILE = os.path.join(DATA_DIR, "token.json")
    CREDENTIALS_FILE = os.path.join(DATA_DIR, "credentials.json")

    def get_service(self):
        creds = self._load_credentials()
        if not creds:
            raise AuthError(
                "Authentication token not found. Run 'gmail auth login' to authenticate."
            )
        if not creds.valid:
            if not self._refresh_credentials(creds):
                raise AuthError(
                    "Authentication token expired and could not be refreshed. "
                    "Run 'gmail auth login' to re-authenticate."
                )
            self._save_credentials(creds)
        return build("gmail", "v1", credentials=creds)

    def login(self):
        creds = self._create_from_oauth_flow()
        self._save_credentials(creds)

    @staticmethod
    def _ensure_data_dir():
        os.makedirs(DATA_DIR, exist_ok=True)

    def _load_credentials(self):
        path = self.TOKEN_FILE
        if not os.path.exists(path):
            for old in (_OLD_TOKEN_FILE, _OLD_TOKEN_FILE_JSON):
                if os.path.exists(old):
                    self._migrate_old_token(old, path)
                    break
        if os.path.exists(path):
            try:
                with open(path) as f:
                    return Credentials.from_authorized_user_info(json.load(f))
            except (json.JSONDecodeError, OSError, ValueError):
                return None
        return None

    @staticmethod
    def _migrate_old_token(old_path: str, new_path: str):
        _, ext = os.path.splitext(old_path)
        if ext == ".pickle":
            with open(old_path, "rb") as f:
                creds = pickle.load(f)  # nosec B301
            with open(new_path, "w") as f:
                json.dump(json.loads(creds.to_json()), f)
        else:
            os.rename(old_path, new_path)
        with contextlib.suppress(OSError):
            os.remove(old_path)

    def _save_credentials(self, creds):
        self._ensure_data_dir()
        fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, prefix="token.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(json.loads(creds.to_json()), f)
            os.replace(tmp_path, self.TOKEN_FILE)
        except BaseException:
            with contextlib.suppress(OSError):
                os.remove(tmp_path)
            raise

    def _refresh_credentials(self, creds):
        if not creds or not creds.refresh_token:
            return None
        try:
            session = req_lib.Session()
            session.timeout = (15, 30)
            creds.refresh(Request(session))
            return creds
        except (req_lib.RequestException, ValueError) as e:
            logger.warning("Token refresh failed: %s", e)
            return None

    def _create_from_oauth_flow(self):
        self._ensure_data_dir()
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
    os.makedirs(DATA_DIR, exist_ok=True)
    creds_path = os.path.join(DATA_DIR, "credentials.json")
    click.echo(
        "═══ Authentication required ═══\n\n"
        "To use this CLI, you need:\n\n"
        "  1. A project in Google Cloud\n"
        "  2. The Gmail API enabled\n"
        "  3. OAuth 2.0 credentials of type 'Desktop application'\n\n"
        "Your browser will open the required pages.\n"
        "Follow the steps and save the file at:\n"
        f"  {creds_path}\n"
    )
    click.prompt("Press Enter to open the Google Cloud Console", default="", prompt_suffix="")
    webbrowser.open(GMAIL_API_URL)
    click.echo(
        "Enable the Gmail API and click 'CREATE CREDENTIALS' >\n"
        "   'OAuth client ID' > 'Desktop application'.\n"
        "Then download the JSON and save it to the path above.\n"
    )
    wait_for_file(creds_path)


def wait_for_file(path: str, timeout: int = 300):
    click.echo(f"Waiting for {path}...", nl=False)
    start = time.time()
    while not os.path.exists(path):
        if time.time() - start > timeout:
            raise CredentialsNotFoundError(
                f"File {path} not found after {timeout}s.\n"
                "Run 'gmail auth login' once you have the file."
            )
        time.sleep(2)
        click.echo(".", nl=False)
    click.echo(" OK")
