from __future__ import annotations

import os

from langchain_openai import ChatOpenAI


def load_model() -> ChatOpenAI:
    """Load the LLM from environment variables.

    Reads LLM_API_KEY, LLM_BASE_URL, MODEL from the environment.
    Compatible with any OpenAI-compatible endpoint.
    """
    api_key = os.environ["LLM_API_KEY"]
    base_url = os.environ["LLM_BASE_URL"]
    model_name = os.environ["MODEL"]

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,  # type: ignore[arg-type]
        base_url=base_url,
        temperature=0,
    )
