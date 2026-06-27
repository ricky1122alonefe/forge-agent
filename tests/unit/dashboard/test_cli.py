"""Tests for the dashboard CLI command."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from forge_agent.cli.cmd_dashboard import add, run


class TestAddCommand:
    """Tests for the add() function."""

    def test_add_registers_dashboard_command(self):
        """add() should register the dashboard command."""
        import argparse

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="cmd")
        add(sub)

        # Parse with dashboard command
        args = parser.parse_args(["dashboard"])
        assert args.cmd == "dashboard"

    def test_add_sets_default_host(self):
        """Should set default host to 127.0.0.1."""
        import argparse

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="cmd")
        add(sub)

        args = parser.parse_args(["dashboard"])
        assert args.host == "127.0.0.1"

    def test_add_sets_default_port(self):
        """Should set default port to 8765."""
        import argparse

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="cmd")
        add(sub)

        args = parser.parse_args(["dashboard"])
        assert args.port == 8765

    def test_add_accepts_custom_host(self):
        """Should accept custom host."""
        import argparse

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="cmd")
        add(sub)

        args = parser.parse_args(["dashboard", "--host", "0.0.0.0"])
        assert args.host == "0.0.0.0"

    def test_add_accepts_custom_port(self):
        """Should accept custom port."""
        import argparse

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="cmd")
        add(sub)

        args = parser.parse_args(["dashboard", "--port", "9000"])
        assert args.port == 9000

    def test_add_accepts_reload_flag(self):
        """Should accept --reload flag."""
        import argparse

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="cmd")
        add(sub)

        args = parser.parse_args(["dashboard", "--reload"])
        assert args.reload is True

    def test_add_accepts_no_browser_flag(self):
        """Should accept --no-browser flag."""
        import argparse

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="cmd")
        add(sub)

        args = parser.parse_args(["dashboard", "--no-browser"])
        assert args.no_browser is True


class TestRunCommand:
    """Tests for the run() function."""

    def test_run_returns_error_when_uvicorn_missing(self):
        """Should return 1 when uvicorn is not installed."""
        import argparse

        args = argparse.Namespace(
            project=Path("/tmp"),
            host="127.0.0.1",
            port=8765,
            reload=False,
            no_browser=True,
        )

        with patch.dict(sys.modules, {"uvicorn": None}):
            result = run(args)
            assert result == 1

    def test_run_creates_app_with_correct_params(self):
        """Should create app with correct parameters."""
        import argparse

        args = argparse.Namespace(
            project=Path("/tmp/test-project"),
            host="0.0.0.0",
            port=9000,
            reload=False,
            no_browser=True,
        )

        mock_uvicorn = MagicMock()
        mock_create_app = MagicMock()

        with patch.dict(sys.modules, {"uvicorn": mock_uvicorn}):
            with patch("forge_agent.dashboard.app.create_app", mock_create_app):
                run(args)

        # Verify create_app was called with correct params
        mock_create_app.assert_called_once_with(
            project_root=Path("/tmp/test-project").resolve(),
            host="0.0.0.0",
            port=9000,
        )

    def test_run_calls_uvicorn_run(self):
        """Should call uvicorn.run with correct params."""
        import argparse

        args = argparse.Namespace(
            project=Path("/tmp"),
            host="127.0.0.1",
            port=8765,
            reload=True,
            no_browser=True,
        )

        mock_uvicorn = MagicMock()
        mock_create_app = MagicMock()

        with patch.dict(sys.modules, {"uvicorn": mock_uvicorn}):
            with patch("forge_agent.dashboard.app.create_app", mock_create_app):
                run(args)

        # Verify uvicorn.run was called
        mock_uvicorn.run.assert_called_once()
        call_kwargs = mock_uvicorn.run.call_args[1]
        assert call_kwargs["host"] == "127.0.0.1"
        assert call_kwargs["port"] == 8765
        assert call_kwargs["reload"] is True

    def test_run_returns_zero_on_success(self):
        """Should return 0 on successful run."""
        import argparse

        args = argparse.Namespace(
            project=Path("/tmp"),
            host="127.0.0.1",
            port=8765,
            reload=False,
            no_browser=True,
        )

        mock_uvicorn = MagicMock()
        mock_create_app = MagicMock()

        with patch.dict(sys.modules, {"uvicorn": mock_uvicorn}):
            with patch("forge_agent.dashboard.app.create_app", mock_create_app):
                result = run(args)

        assert result == 0
