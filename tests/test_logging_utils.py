import logging
from logging.handlers import TimedRotatingFileHandler
from unittest.mock import MagicMock, patch

from gmail_cli import logging_utils
from gmail_cli.logging_utils import _get_log_days, get_logger


class TestGetLogger:
    def test_returns_same_instance(self):
        assert get_logger() is get_logger()

    def test_creates_log_file(self, tmp_path):
        logger = get_logger(log_days=120)
        logger.info("hello")
        assert logging_utils.LOG_FILE.exists()
        assert "hello" in logging_utils.LOG_FILE.read_text()

    def test_uses_daily_rotating_handler(self):
        logger = get_logger(log_days=120)
        handler = next(h for h in logger.handlers if isinstance(h, TimedRotatingFileHandler))
        assert handler.when == "D"
        assert handler.interval == 86400
        assert handler.backupCount == 120

    def test_respects_log_days_config(self, monkeypatch):
        monkeypatch.setattr("gmail_cli.logging_utils._get_log_days", lambda: 30)
        logger = get_logger()
        handler = next(h for h in logger.handlers if isinstance(h, TimedRotatingFileHandler))
        assert handler.backupCount == 30

    def test_get_log_days_reads_config(self, monkeypatch):
        mock_cfg = MagicMock(log_days=15)
        with patch("gmail_cli.logging_utils.load_config", return_value=mock_cfg):
            assert _get_log_days() == 15

    def test_logger_uses_gmail_cli_name(self):
        logger = get_logger()
        assert logger.name == "gmail_cli"
        assert logger.level == logging.INFO
