"""Gemini embedding helpers shared by graph and content embedding paths."""

from __future__ import annotations

from typing import Literal

from google.genai import types

GeminiInputKind = Literal["query", "document", "similarity", "classification", "clustering"]


def is_gemini_embedding_2(model: str) -> bool:
    return model.startswith("gemini-embedding-2")


def format_gemini_embedding_text(
    text: str,
    *,
    model: str,
    kind: GeminiInputKind,
    title: str | None = None,
) -> str:
    if not is_gemini_embedding_2(model):
        return text

    match kind:
        case "query":
            return f"task: search result | query: {text}"
        case "document":
            return f"title: {title or 'none'} | text: {text}"
        case "similarity":
            return f"task: sentence similarity | query: {text}"
        case "classification":
            return f"task: classification | query: {text}"
        case "clustering":
            return f"task: clustering | query: {text}"


def build_gemini_contents(texts: list[str]) -> list[types.Content]:
    return [
        types.Content(role="user", parts=[types.Part.from_text(text=text)])
        for text in texts
    ]
