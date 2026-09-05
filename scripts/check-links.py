#!/usr/bin/env python3
"""Validate Markdown links against tracked and explicitly selected candidate files.

Nonignored new files are included for pre-stage verification. Ignored local
evidence cannot satisfy published links unless explicitly named with --candidate.
Cross-repository destinations must use explicit external URLs.
"""
import argparse
import os
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

from candidate import inventory


def prose(text):
    lines = []
    fence = None
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", line)
        if match:
            marker, rest = match.groups()
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence) and not rest.strip():
                fence = None
            lines.append("")
        else:
            lines.append(line if fence is None else "")
    return "\n".join(lines)


def anchors(text):
    result, counts = set(), {}
    lines = prose(text).splitlines()
    for index, line in enumerate(lines):
        heading = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        title = heading.group(1) if heading else None
        if index + 1 < len(lines) and line.strip() and re.match(r"^\s{0,3}(?:=+|-+)\s*$", lines[index + 1]):
            title = line.strip()
        if title is not None:
            title = re.sub(r"<[^>]+>", "", title)
            title = re.sub(r"!?\[([^]]+)\]\([^)]*\)", r"\1", title)
            slug = re.sub(r"[^\w\-\s]", "", title.lower()).replace(" ", "-")
            suffix = counts.get(slug, 0)
            counts[slug] = suffix + 1
            result.add(slug + ("-" + str(suffix) if suffix else ""))
        result.update(re.findall(r"\b(?:id|name)=[\"']([^\"']+)[\"']", line))
    return result


def links(text):
    text = prose(text)
    # Inline code is an example, not a rendered link.
    text = re.sub(r"(`+).*?\1", "", text)
    destination = r"(<[^>]*>|(?:[^\s()]|\([^()]*\))*)"
    closing = re.compile(r"\(\s*" + destination + r"(?:\s+[\"'][^\n]*?[\"'])?\s*\)")
    # A bracket stack retains both destinations in linked images/badges.
    brackets = []
    escaped = False
    for index, character in enumerate(text):
        if escaped:
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == "[":
            brackets.append(index)
        elif character == "]" and brackets:
            brackets.pop()
            match = closing.match(text, index + 1)
            if match:
                yield match.group(1).strip("<>")
    # A reference definition is checked even if the label is currently unused.
    for match in re.finditer(r"^\s{0,3}\[[^]\n]+\]:\s*" + destination, text, re.M):
        yield match.group(1).strip("<>")


def candidate_symlink(path, root, available):
    seen = set()
    while path.is_symlink():
        if path in seen:
            return False
        seen.add(path)
        path = Path(os.path.abspath(path.parent / os.readlink(path)))
        try:
            name = str(path.relative_to(root))
        except ValueError:
            return False
        if name not in available:
            return False
    try:
        return str(path.resolve().relative_to(root)) in available
    except ValueError:
        return False


def check(root, extra=()):
    paths = inventory(root, extra)
    available = {str(path) for path in paths}
    documents = [path for path in paths if path.suffix.lower() == ".md"]
    if not documents:
        raise ValueError("no candidate Markdown documents found")
    errors, count = [], 0
    cached_anchors = {}
    for document in documents:
        source = root / document
        if not source.is_file():
            errors.append(f"{document}: missing candidate document")
            continue
        if not candidate_symlink(source, root, available):
            errors.append(f"{document}: source symlink target absent from clean candidate")
            continue
        for link in links(source.read_text(encoding="utf-8")):
            if not link:
                continue
            parsed = urlsplit(link)
            if parsed.scheme or parsed.netloc:
                continue
            target = source.parent / unquote(parsed.path) if parsed.path else source
            # Normalize lexical paths first: a local symlink must not lend an
            # ignored target legitimacy in a clean checkout.
            target = Path(os.path.abspath(target))
            try:
                relative = target.relative_to(root)
            except ValueError:
                errors.append(f"{document}: {link}: local target escapes candidate; use an explicit external URL")
                continue
            count += 1
            name = str(relative)
            is_dir = any(p.startswith(name.rstrip("/") + "/") for p in available)
            if name == ".":
                is_dir = True
            if (name not in available and not is_dir) or not target.exists():
                errors.append(f"{document}: {link}: target absent from clean candidate")
                continue
            if target.is_symlink():
                if not candidate_symlink(target, root, available):
                    errors.append(f"{document}: {link}: symlink target absent from candidate")
                    continue
            if parsed.fragment and target.suffix.lower() == ".md":
                if name not in cached_anchors:
                    cached_anchors[name] = anchors(target.read_text(encoding="utf-8"))
                if unquote(parsed.fragment) not in cached_anchors[name]:
                    errors.append(f"{document}: {link}: missing Markdown anchor")
    print(f"Checked {len(documents)} candidate Markdown files and {count} internal links")
    for error in errors:
        print("BLOCKED / WHY: " + error + " / FIX: correct the link or include its target", file=sys.stderr)
    return not errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--candidate", action="append", default=[])
    args = parser.parse_args()
    try:
        return 0 if check(args.root.resolve(), args.candidate) else 1
    except (OSError, ValueError) as error:
        print(f"BLOCKED / WHY: {error} / FIX: provide a nonempty Git candidate", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
