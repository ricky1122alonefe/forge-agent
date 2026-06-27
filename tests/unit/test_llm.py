"""Unit tests for forge_agent.llm."""

from __future__ import annotations

import os
import pytest

from forge_agent.llm.config import LLMConfig, ProviderConfig, load_config
from forge_agent.llm.exceptions import (
    LLMAuthError,
    LLMContextOverflowError,
    LLMError,
    LLMNetworkError,
    LLMRateLimitError,
)
from forge_agent.llm.factory import LLMFactory
from forge_agent.llm.protocol import ChatMessage, LLMResponse, chat, multi_chat
from forge_agent.llm.providers.mock import MockClient
from forge_agent.llm.registry import LLMRegistry
from forge_agent.llm.secrets import APIKeyManager, APIKeySource


@pytest.fixture(autouse=True)
def _reset_llm_registry():
    LLMRegistry._instance = None
    yield
    LLMRegistry._instance = None


# ------------------------------------------------------------------ Config

def test_load_config_defaults():
    cfg = load_config()
    assert "deepseek" in cfg.providers
    assert cfg.primary_id == "deepseek"


def test_provider_config_from_dict():
    p = ProviderConfig.from_dict("test", {
        "type": "openai",
        "model": "gpt-4o",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "enabled": True,
    })
    assert p.provider_id == "test"
    assert p.model == "gpt-4o"
    assert p.enabled is True


# ------------------------------------------------------------------ Secrets

def test_api_key_manager_explicit():
    km = APIKeyManager()
    r = km.resolve("ANY_KEY", explicit="sk-explicit")
    assert r and r.value == "sk-explicit" and r.source == APIKeySource.EXPLICIT


def test_api_key_manager_env(monkeypatch):
    monkeypatch.setenv("TEST_KEY", "sk-env")
    km = APIKeyManager()
    r = km.resolve("TEST_KEY")
    assert r and r.value == "sk-env" and r.source == APIKeySource.ENV


def test_api_key_manager_missing():
    km = APIKeyManager()
    r = km.resolve("DEFINITELY_NOT_SET_KEY_XYZ")
    assert r is None


def test_api_key_manager_alt_names(monkeypatch):
    monkeypatch.setenv("BACKUP_KEY", "sk-backup")
    km = APIKeyManager()
    r = km.resolve("PRIMARY_KEY", alt_names=["BACKUP_KEY"])
    assert r and r.value == "sk-backup"


# ------------------------------------------------------------------ Mock client

@pytest.mark.asyncio
async def test_mock_client_chat():
    cfg = ProviderConfig(
        provider_id="mock", type="mock", model="mock-1",
        extra={"response": "Hello from mock!"},
    )
    client = MockClient(cfg)
    r = await client.chat([{"role": "user", "content": "Hi"}])
    assert r.content == "Hello from mock!"
    assert r.provider == "mock"
    assert r.tokens_out > 0


@pytest.mark.asyncio
async def test_mock_client_stream():
    cfg = ProviderConfig(provider_id="mock", type="mock", model="mock-1")
    client = MockClient(cfg)
    chunks = []
    async for c in client.stream([{"role": "user", "content": "Hi"}]):
        chunks.append(c.delta)
    text = "".join(chunks)
    assert "mock response" in text


# ------------------------------------------------------------------ Registry

@pytest.mark.asyncio
async def test_registry_get_client_creates_and_caches():
    reg = LLMRegistry()
    reg.configure(LLMConfig(
        primary_id="cached",
        predict_mode="single",
        providers={
            "cached": ProviderConfig(provider_id="cached", type="mock", model="x"),
        },
    ))
    c1 = await reg.get_client("cached")
    c2 = await reg.get_client("cached")
    assert c1 is c2


# ------------------------------------------------------------------ High-level chat

@pytest.mark.asyncio
async def test_chat_with_explicit_provider():
    reg = LLMRegistry()
    reg.configure(LLMConfig(
        primary_id="x",
        predict_mode="single",
        providers={
            "chatter": ProviderConfig(
                provider_id="chatter", type="mock", model="x",
                extra={"response": "via chatter"},
            ),
        },
    ))
    r = await chat("hi", provider="chatter")
    assert r.content == "via chatter"
    assert r.provider == "chatter"


@pytest.mark.asyncio
async def test_multi_chat_returns_one_per_provider():
    reg = LLMRegistry()
    reg.configure(LLMConfig(
        primary_id="x",
        predict_mode="multi",
        providers={
            "ma": ProviderConfig(provider_id="ma", type="mock", model="x",
                                 extra={"response": "A says hi"}),
            "mb": ProviderConfig(provider_id="mb", type="mock", model="x",
                                 extra={"response": "B says hi"}),
        },
    ))
    results = await multi_chat("hi", providers=["ma", "mb"])
    assert len(results) == 2
    assert {r.content for r in results} == {"A says hi", "B says hi"}


# ------------------------------------------------------------------ Exceptions

def test_exception_categories():
    e1 = LLMAuthError("bad key", provider="p")
    e2 = LLMRateLimitError("429", provider="p")
    e3 = LLMContextOverflowError("too long", provider="p")
    e4 = LLMNetworkError("connection failed", provider="p")
    assert all(isinstance(e, LLMError) for e in [e1, e2, e3, e4])
