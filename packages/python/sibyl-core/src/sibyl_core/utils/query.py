"""Query text helpers."""

from __future__ import annotations


def query_tokens(query: str) -> list[str]:
    tokens: list[str] = []
    index = 0
    length = len(query)

    while index < length:
        char = query[index]
        next_char = query[index + 1] if index + 1 < length else ""

        if char in {"'", '"', "`"}:
            quote = char
            index += 1
            while index < length:
                current = query[index]
                if current == "\\":
                    index += 2
                    continue
                index += 1
                if current == quote:
                    break
            continue

        if char == "/" and next_char == "*":
            index += 2
            while index + 1 < length and not (query[index] == "*" and query[index + 1] == "/"):
                index += 1
            index = min(index + 2, length)
            continue

        if (char == "-" and next_char == "-") or (char == "/" and next_char == "/"):
            index += 2
            while index < length and query[index] not in "\r\n":
                index += 1
            continue

        if char.isalpha() or char == "_":
            start = index
            index += 1
            while index < length and (query[index].isalnum() or query[index] == "_"):
                index += 1
            tokens.append(query[start:index])
            continue

        index += 1

    return tokens


def upper_query_tokens(query: str) -> set[str]:
    return {token.upper() for token in query_tokens(query)}


__all__ = ["query_tokens", "upper_query_tokens"]
