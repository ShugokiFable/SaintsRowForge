"""Lua-aware helpers. SR uses stock Lua 5.x-family syntax; these are STATIC
checks only - they can never prove runtime behavior in-engine."""
import re
import io
import tokenize


def lint(path):
    problems = []
    src = open(path, "r", encoding="utf-8", errors="replace").read()
    # balance check for block keywords (string-stripped approximation)
    stripped = re.sub(r'--\[\[.*?\]\]', ' ', src, flags=re.S)
    stripped = re.sub(r'--[^\n]*', ' ', stripped)
    stripped = re.sub(r'"(?:\\.|[^"\\])*"', '""', stripped)
    stripped = re.sub(r"'(?:\\.|[^'\\])*'", "''", stripped)
    words = re.findall(r'\b(?:function|if|for|while|do|end|repeat|until|then)\b', stripped)
    opens = 0
    depth_stack = []
    tokens = iter(words)
    prev = None
    for w in words:
        if w == "function":
            opens += 1; depth_stack.append("function")
        elif w == "if":
            pass  # closed by end after then; counted loosely below
        elif w == "for" or w == "while":
            depth_stack.append("loop"); opens += 1
        elif w == "repeat":
            depth_stack.append("repeat"); opens += 1
        elif w == "until":
            if not depth_stack or depth_stack[-1] != "repeat":
                problems.append({"line": None, "message": "'until' without matching 'repeat'"})
            else:
                depth_stack.pop()
        elif w == "end":
            if not depth_stack or depth_stack[-1] == "repeat":
                problems.append({"line": None, "message": "'end' without open function/for/while"})
            else:
                depth_stack.pop()
    if depth_stack:
        problems.append({"line": None,
                         "message": f"unclosed blocks: {', '.join(depth_stack)}"})
    return problems


def search(paths, pattern):
    rx = re.compile(pattern)
    hits = []
    for p in paths:
        try:
            text = open(p, "r", encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                hits.append({"path": p, "line": i, "text": line.strip()[:200]})
    return hits
