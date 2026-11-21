"""Minimal parser for the Lua table literals Lightroom stores in catalogs and preferences.

Handles `name = { ... }` wrappers, string/number/boolean/nil values, `key = v`,
`["key"] = v`, `[1] = v` and positional entries. Tables with only positional
entries become lists; everything else becomes a dict.
"""

from __future__ import annotations

import re
from typing import Any

_TOKEN = re.compile(
    r"""\s*(?:
        (?P<str>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')
      | (?P<num>-?(?:0x[0-9a-fA-F]+|\d+\.?\d*(?:[eE][-+]?\d+)?|\.\d+))
      | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
      | (?P<punct>[{}\[\]=,;])
    )""",
    re.VERBOSE | re.DOTALL,
)

_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'", "\n": "\n"}


def _unquote(s: str) -> str:
    body = s[1:-1]
    return re.sub(r"\\(.)", lambda m: _ESCAPES.get(m.group(1), m.group(1)), body, flags=re.DOTALL)


class _Parser:
    def __init__(self, text: str):
        self.tokens: list[tuple[str, str]] = []
        pos = 0
        text = re.sub(r"--[^\n]*", "", text)
        while pos < len(text):
            m = _TOKEN.match(text, pos)
            if not m:
                if text[pos:].strip() == "":
                    break
                raise ValueError(f"Unexpected Lua syntax at offset {pos}: {text[pos:pos + 20]!r}")
            kind = m.lastgroup or ""
            self.tokens.append((kind, m.group(kind)))
            pos = m.end()
        self.i = 0

    def peek(self) -> tuple[str, str] | None:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def next(self) -> tuple[str, str]:
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def expect(self, value: str) -> None:
        kind, tok = self.next()
        if tok != value:
            raise ValueError(f"Expected {value!r}, got {tok!r}")

    def value(self) -> Any:
        kind, tok = self.next()
        if kind == "str":
            return _unquote(tok)
        if kind == "num":
            if tok.lower().startswith(("0x", "-0x")):
                return int(tok, 16)
            f = float(tok)
            return int(f) if f.is_integer() and "." not in tok and "e" not in tok.lower() else f
        if kind == "name":
            if tok == "true":
                return True
            if tok == "false":
                return False
            if tok == "nil":
                return None
            return tok  # bare identifier (e.g. LOC); keep as text
        if tok == "{":
            return self.table()
        raise ValueError(f"Unexpected token {tok!r}")

    def table(self) -> Any:
        items: list[Any] = []
        fields: dict[Any, Any] = {}
        while True:
            tok = self.peek()
            if tok is None:
                raise ValueError("Unterminated table")
            if tok[1] == "}":
                self.next()
                break
            if tok[1] == "[":
                self.next()
                key = self.value()
                self.expect("]")
                self.expect("=")
                fields[key] = self.value()
            elif (
                tok[0] == "name"
                and self.i + 1 < len(self.tokens)
                and self.tokens[self.i + 1][1] == "="
            ):
                key = self.next()[1]
                self.next()
                fields[key] = self.value()
            else:
                items.append(self.value())
            sep = self.peek()
            if sep and sep[1] in ",;":
                self.next()
        if fields:
            for n, item in enumerate(items, start=1):
                fields.setdefault(n, item)
            return fields
        return items


def parse(text: str) -> Any:
    """Parse `{...}` or `name = {...}` and return the table as a dict or list."""
    p = _Parser(text)
    first = p.peek()
    if first and first[0] == "name" and p.i + 1 < len(p.tokens) and p.tokens[1][1] == "=":
        p.next()
        p.next()
    return p.value()
