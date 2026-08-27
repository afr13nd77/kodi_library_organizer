"""Тесты для shared.logger.Logger.

Тестируем fallback-режим (print), xbmc не мокаем.
"""
from __future__ import annotations

from shared.logger import Logger


class TestLoggerDebug:
    """Тесты метода debug()."""

    def test_debug_disabled_no_output(self, capsys) -> None:
        """debug() при debug_enabled=False ничего не выводит."""
        logger = Logger(debug_enabled=False)
        logger.debug("secret debug msg")
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_debug_enabled_outputs_message(self, capsys) -> None:
        """debug() при debug_enabled=True выводит сообщение."""
        logger = Logger(debug_enabled=True)
        logger.debug("visible debug msg")
        captured = capsys.readouterr()
        assert "visible debug msg" in captured.out

    def test_debug_enabled_contains_prefix(self, capsys) -> None:
        """debug() при debug_enabled=True содержит PREFIX."""
        logger = Logger(debug_enabled=True)
        logger.debug("test")
        captured = capsys.readouterr()
        assert "[LibOrganizer]" in captured.out

    def test_debug_enabled_contains_level(self, capsys) -> None:
        """debug() при debug_enabled=True содержит [DEBUG]."""
        logger = Logger(debug_enabled=True)
        logger.debug("test")
        captured = capsys.readouterr()
        assert "[DEBUG]" in captured.out

    def test_debug_default_disabled(self, capsys) -> None:
        """По умолчанию debug_enabled=False."""
        logger = Logger()
        logger.debug("should not appear")
        captured = capsys.readouterr()
        assert captured.out == ""


class TestLoggerInfo:
    """Тесты метода info()."""

    def test_info_outputs_message(self, capsys) -> None:
        """info() выводит сообщение."""
        logger = Logger()
        logger.info("info message")
        captured = capsys.readouterr()
        assert "info message" in captured.out

    def test_info_contains_level(self, capsys) -> None:
        """info() содержит [INFO] в выводе."""
        logger = Logger()
        logger.info("test")
        captured = capsys.readouterr()
        assert "[INFO]" in captured.out

    def test_info_contains_prefix(self, capsys) -> None:
        """info() содержит [LibOrganizer] в выводе."""
        logger = Logger()
        logger.info("test")
        captured = capsys.readouterr()
        assert "[LibOrganizer]" in captured.out


class TestLoggerWarning:
    """Тесты метода warning()."""

    def test_warning_outputs_message(self, capsys) -> None:
        """warning() выводит сообщение."""
        logger = Logger()
        logger.warning("warning message")
        captured = capsys.readouterr()
        assert "warning message" in captured.out

    def test_warning_contains_level(self, capsys) -> None:
        """warning() содержит [WARNING] в выводе."""
        logger = Logger()
        logger.warning("test")
        captured = capsys.readouterr()
        assert "[WARNING]" in captured.out

    def test_warning_contains_prefix(self, capsys) -> None:
        """warning() содержит [LibOrganizer] в выводе."""
        logger = Logger()
        logger.warning("test")
        captured = capsys.readouterr()
        assert "[LibOrganizer]" in captured.out


class TestLoggerError:
    """Тесты метода error()."""

    def test_error_outputs_message(self, capsys) -> None:
        """error() выводит сообщение."""
        logger = Logger()
        logger.error("error message")
        captured = capsys.readouterr()
        assert "error message" in captured.out

    def test_error_contains_level(self, capsys) -> None:
        """error() содержит [ERROR] в выводе."""
        logger = Logger()
        logger.error("test")
        captured = capsys.readouterr()
        assert "[ERROR]" in captured.out

    def test_error_contains_prefix(self, capsys) -> None:
        """error() содержит [LibOrganizer] в выводе."""
        logger = Logger()
        logger.error("test")
        captured = capsys.readouterr()
        assert "[LibOrganizer]" in captured.out


class TestLoggerFormat:
    """Тесты формата вывода."""

    def test_format_info(self, capsys) -> None:
        """Проверка полного формата: [LEVEL] [LibOrganizer] message."""
        logger = Logger()
        logger.info("hello world")
        captured = capsys.readouterr()
        assert captured.out.strip() == "[INFO] [LibOrganizer] hello world"

    def test_format_error(self, capsys) -> None:
        """Проверка полного формата для error."""
        logger = Logger()
        logger.error("something broke")
        captured = capsys.readouterr()
        assert captured.out.strip() == "[ERROR] [LibOrganizer] something broke"

    def test_format_warning(self, capsys) -> None:
        """Проверка полного формата для warning."""
        logger = Logger()
        logger.warning("careful")
        captured = capsys.readouterr()
        assert captured.out.strip() == "[WARNING] [LibOrganizer] careful"

    def test_format_debug(self, capsys) -> None:
        """Проверка полного формата для debug."""
        logger = Logger(debug_enabled=True)
        logger.debug("trace info")
        captured = capsys.readouterr()
        assert captured.out.strip() == "[DEBUG] [LibOrganizer] trace info"
