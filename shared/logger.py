"""Модуль логирования для Kodi Library Organizer.

Обёртка над Kodi xbmc.log(). Работает и в Kodi, и без Kodi (fallback на print).
"""
from __future__ import annotations


class Logger:
    """Логгер с поддержкой Kodi xbmc.log() и fallback на print()."""

    PREFIX = "[LibOrganizer]"

    def __init__(self, debug_enabled: bool = False) -> None:
        self._debug_enabled = debug_enabled

    def debug(self, message: str) -> None:
        """Лог DEBUG — только при debug_enabled=True."""
        if not self._debug_enabled:
            return
        self._log(message, level="DEBUG")

    def info(self, message: str) -> None:
        """Лог INFO — всегда."""
        self._log(message, level="INFO")

    def warning(self, message: str) -> None:
        """Лог WARNING — всегда."""
        self._log(message, level="WARNING")

    def error(self, message: str) -> None:
        """Лог ERROR — всегда."""
        self._log(message, level="ERROR")

    def _log(self, message: str, level: str) -> None:
        """Форматирует и отправляет сообщение в xbmc.log() или print()."""
        formatted = f"{self.PREFIX} {message}"
        try:
            import xbmc  # type: ignore[import-not-found]

            level_map = {
                "DEBUG": xbmc.LOGDEBUG,
                "INFO": xbmc.LOGINFO,
                "WARNING": xbmc.LOGWARNING,
                "ERROR": xbmc.LOGERROR,
            }
            xbmc.log(formatted, level_map.get(level, xbmc.LOGINFO))
        except ImportError:
            print(f"[{level}] {formatted}")
