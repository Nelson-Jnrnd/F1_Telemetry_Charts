"""Data gateway contracts."""

from __future__ import annotations

from typing import Protocol

from f1_telemetry_charts.data.models import SessionDataset, SessionQuery


class DataGatewayError(Exception):
    """Raised when a session dataset cannot be loaded."""


class SessionDataGateway(Protocol):
    def load_session(self, query: SessionQuery) -> SessionDataset:
        """Load a normalized session dataset for the query."""
