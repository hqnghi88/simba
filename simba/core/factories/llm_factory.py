import os
from functools import lru_cache
from typing import Optional

from langchain_community.llms import VLLM
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from simba.core.config import LLMConfig, settings


@lru_cache()
def get_llm(LLMConfig: Optional[LLMConfig] = None):
    """
    Get a Language Learning Model (LLM) instance based on the configured provider.

    Args:
        LLMConfig: Configuration object containing provider, model name, API key and other settings

    Returns:
        A LangChain chat model instance (ChatOpenAI, ChatAnthropic etc.) configured with the specified settings

    Raises:
        ValueError: If an unsupported LLM provider is specified in the config

    Example:
        llm = get_llm(LLMConfig(
            provider="openai",
            model_name="gpt-4",
            api_key="...",
            temperature=0.7
        ))
    """

    if settings.llm.provider == "openai":
        try:
            return ChatOpenAI(
                model_name=settings.llm.model_name,
                temperature=settings.llm.temperature,
                api_key=settings.llm.api_key,
                streaming=settings.llm.streaming,
            )
        except Exception as e:
            print(f"Error initializing LLM: {e}, openai is not supported")
            raise e

    elif settings.llm.provider == "ollama":
        base_url = os.environ.get("OLLAMA_HOST", settings.llm.base_url)
        print(f"Using Ollama base_url: {base_url}")
        return ChatOllama(
            model=settings.llm.model_name,
            temperature=settings.llm.temperature,
            base_url=base_url,
            streaming=settings.llm.streaming,
            timeout=60,
        )

    elif settings.llm.provider == "vllm":
        # vllm-mlx and other vLLM servers provide an OpenAI-compatible API
        base_url = settings.llm.base_url
        if not base_url.endswith("/v1"):
            base_url = f"{base_url.rstrip('/')}/v1"
            
        return ChatOpenAI(
            model_name=settings.llm.model_name,
            temperature=settings.llm.temperature,
            api_key="not-needed",
            base_url=base_url,
            streaming=settings.llm.streaming,
            max_tokens=settings.llm.max_tokens or 2048,
            model_kwargs={"response_format": {"type": "json_object"}},
            timeout=60,
        )

    elif settings.llm.provider == "anthropic":
        return """ChatAnthropic(
            model=settings.llm.model_name,
            temperature=settings.llm.temperature,
            api_key=settings.llm.api_key,
            streaming=settings.llm.streaming
        )"""

    raise ValueError(f"Unsupported LLM provider: {settings.LLM.provider}")
