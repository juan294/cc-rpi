"""Publishable working candidate inventory shared by local verification tools."""
import hashlib
import os
from pathlib import Path
import subprocess


def inventory(root, extra=()):
    output = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root)
    paths = {Path(os.fsdecode(name)) for name in output.split(b"\0") if name}
    paths.update(Path(name) for name in extra)
    for path in paths:
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("candidate path must be repository-relative: " + str(path))
    return sorted(path for path in paths
                  if not str(path).startswith(".rpi/local/")
                  and "__pycache__" not in path.parts)


def identity(root, excluded=()):
    digest = hashlib.sha256()
    paths = [p for p in inventory(root) if (root / p).absolute() not in excluded]
    if not paths:
        raise ValueError("candidate inventory is empty")
    for path in paths:
        full = root / path
        digest.update(os.fsencode(path) + b"\0")
        if full.is_symlink():
            digest.update(b"symlink\0" + os.fsencode(os.readlink(full)))
        elif full.is_file():
            digest.update(str(full.stat().st_mode & 0o777).encode() + b"\0")
            digest.update(full.read_bytes())
        else:
            digest.update(b"missing")
        digest.update(b"\0")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                          capture_output=True, text=True)
    return {"sha256": digest.hexdigest(), "file_count": len(paths),
            "commit": head.stdout.strip() if head.returncode == 0 else None}
