from __future__ import annotations

import os
from typing import Any

import openai
from langchain_core.messages import AIMessage, BaseMessage
from langchain_openai import ChatOpenAI


class _KimiChatOpenAI(ChatOpenAI):
    """ChatOpenAI subclass that round-trips Kimi's `reasoning` field.

    Kimi returns a `reasoning` field alongside `content`. On the *next* turn
    the provider requires `reasoning_content` in the assistant message or it
    returns 400. LangChain doesn't know about this field, so we:
    1. capture `reasoning` from the raw response into additional_kwargs
    2. inject it back as `reasoning_content` when serialising outgoing messages
    """

    def _create_chat_result(self, response: dict | openai.BaseModel, generation_info: dict | None = None) -> Any:  # type: ignore[override]
        result = super()._create_chat_result(response, generation_info)
        response_dict = (
            response if isinstance(response, dict) else response.model_dump()
        )
        for i, choice in enumerate(response_dict.get("choices", [])):
            reasoning = choice.get("message", {}).get("reasoning")
            if reasoning and i < len(result.generations):
                msg = result.generations[i].message
                if isinstance(msg, AIMessage):
                    msg.additional_kwargs["reasoning_content"] = reasoning
        return result

    def _get_request_payload(self, input_: Any, *, stop: list[str] | None = None, **kwargs: Any) -> dict:  # type: ignore[override]
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        for msg_dict in payload.get("messages", []):
            if msg_dict.get("role") == "assistant" and msg_dict.get("tool_calls"):
                # provider requires reasoning_content present on tool-call turns;
                # we stash it in additional_kwargs during _create_chat_result
                pass  # handled below via message objects
        # Re-inject reasoning_content from AIMessage.additional_kwargs
        messages: list[BaseMessage] = self._convert_input(input_).to_messages()
        for i, base_msg in enumerate(messages):
            if (
                isinstance(base_msg, AIMessage)
                and "reasoning_content" in base_msg.additional_kwargs
                and i < len(payload.get("messages", []))
            ):
                payload["messages"][i]["reasoning_content"] = base_msg.additional_kwargs["reasoning_content"]
        return payload


def load_model() -> _KimiChatOpenAI:
    """Load the LLM from environment variables.

    Reads LLM_API_KEY, LLM_BASE_URL, MODEL from the environment.
    Compatible with any OpenAI-compatible endpoint.
    """
    api_key = os.environ["LLM_API_KEY"]
    base_url = os.environ["LLM_BASE_URL"]
    model_name = os.environ["MODEL"]

    return _KimiChatOpenAI(
        model=model_name,
        api_key=api_key,  # type: ignore[arg-type]
        base_url=base_url,
        temperature=0,
    )
