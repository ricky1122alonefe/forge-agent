"""Tests for PromptProvider Protocol (generator/prompt_provider.py)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from forge_agent.core.agent_type import AgentType
from forge_agent.generator.prompt_provider import (
    ChainPromptProvider,
    DefaultPromptProvider,
    FilePromptProvider,
    PromptProvider,
    get_prompt_provider,
    reset_prompt_provider,
    set_prompt_provider,
)

# ------------------------------------------------------------------ DefaultPromptProvider


class TestDefaultPromptProvider:
    def test_get_system_prompt_general(self):
        provider = DefaultPromptProvider()
        prompt = provider.get_system_prompt(AgentType.GENERAL)
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_get_system_prompt_scraper(self):
        provider = DefaultPromptProvider()
        prompt = provider.get_system_prompt(AgentType.SCRAPER)
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_get_system_prompt_all_types(self):
        provider = DefaultPromptProvider()
        for at in AgentType:
            prompt = provider.get_system_prompt(at)
            assert isinstance(prompt, str)
            assert len(prompt) > 0

    def test_get_user_prompt_template_returns_none(self):
        provider = DefaultPromptProvider()
        for at in AgentType:
            assert provider.get_user_prompt_template(at) is None


# ------------------------------------------------------------------ FilePromptProvider


class TestFilePromptProvider:
    def test_fallback_to_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = FilePromptProvider(tmpdir)
            prompt = provider.get_system_prompt(AgentType.GENERAL)
            assert isinstance(prompt, str)
            assert len(prompt) > 0

    def test_load_from_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "scraper.system.txt"
            path.write_text("Custom scraper prompt", encoding="utf-8")
            provider = FilePromptProvider(tmpdir)
            prompt = provider.get_system_prompt(AgentType.SCRAPER)
            assert prompt == "Custom scraper prompt"

    def test_user_prompt_template_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = FilePromptProvider(tmpdir)
            assert provider.get_user_prompt_template(AgentType.GENERAL) is None

    def test_user_prompt_template_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "analyzer.user.txt"
            path.write_text("Custom user template", encoding="utf-8")
            provider = FilePromptProvider(tmpdir)
            result = provider.get_user_prompt_template(AgentType.ANALYZER)
            assert result == "Custom user template"

    def test_empty_file_falls_back(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "monitor.system.txt"
            path.write_text("   ", encoding="utf-8")
            provider = FilePromptProvider(tmpdir)
            prompt = provider.get_system_prompt(AgentType.MONITOR)
            # Should fall back to default since file is empty
            assert isinstance(prompt, str)
            assert len(prompt) > 0


# ------------------------------------------------------------------ ChainPromptProvider


class TestChainPromptProvider:
    def test_first_provider_wins(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "scraper.system.txt"
            path.write_text("File prompt", encoding="utf-8")
            chain = ChainPromptProvider(
                [
                    FilePromptProvider(tmpdir),
                    DefaultPromptProvider(),
                ]
            )
            prompt = chain.get_system_prompt(AgentType.SCRAPER)
            assert prompt == "File prompt"

    def test_falls_through_chain(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # No files in tmpdir, so FilePromptProvider falls back to default
            chain = ChainPromptProvider(
                [
                    FilePromptProvider(tmpdir),
                    DefaultPromptProvider(),
                ]
            )
            prompt = chain.get_system_prompt(AgentType.GENERAL)
            assert isinstance(prompt, str)
            assert len(prompt) > 0

    def test_user_prompt_first_non_none(self):
        with tempfile.TemporaryDirectory() as tmpdir1, tempfile.TemporaryDirectory() as tmpdir2:
            path = Path(tmpdir2) / "scraper.user.txt"
            path.write_text("Template from dir2", encoding="utf-8")
            chain = ChainPromptProvider(
                [
                    FilePromptProvider(tmpdir1),
                    FilePromptProvider(tmpdir2),
                ]
            )
            result = chain.get_user_prompt_template(AgentType.SCRAPER)
            assert result == "Template from dir2"

    def test_user_prompt_all_none(self):
        chain = ChainPromptProvider([DefaultPromptProvider()])
        result = chain.get_user_prompt_template(AgentType.GENERAL)
        assert result is None


# ------------------------------------------------------------------ Protocol check


class TestProtocol:
    def test_default_is_prompt_provider(self):
        assert isinstance(DefaultPromptProvider(), PromptProvider)

    def test_file_is_prompt_provider(self):
        assert isinstance(FilePromptProvider("/tmp"), PromptProvider)

    def test_chain_is_prompt_provider(self):
        assert isinstance(ChainPromptProvider([]), PromptProvider)


# ------------------------------------------------------------------ Singleton


class TestSingleton:
    def setup_method(self):
        reset_prompt_provider()

    def teardown_method(self):
        reset_prompt_provider()

    def test_get_returns_default(self):
        provider = get_prompt_provider()
        assert isinstance(provider, DefaultPromptProvider)

    def test_set_and_get(self):
        custom = DefaultPromptProvider()
        set_prompt_provider(custom)
        assert get_prompt_provider() is custom

    def test_reset(self):
        p1 = get_prompt_provider()
        reset_prompt_provider()
        p2 = get_prompt_provider()
        assert p1 is not p2
