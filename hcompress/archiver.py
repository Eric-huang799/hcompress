"""Directory archiver — pack/unpack folders into a single byte stream.

Format: [path_len:u32][rel_path:UTF-8][file_size:u64][content] per entry, terminated by path_len=0.
"""

from __future__ import annotations

import os
import struct
from pathlib import Path

# HCF flags extension
FLAG_DIRECTORY = 1 << 8

_TERMINATOR = struct.pack("<I", 0)


def list_archive(data: bytes) -> list[dict]:
    """Parse archive metadata without extracting files. Returns [{name, size}, ...]."""
    entries = []
    offset = 0
    while offset < len(data):
        if offset + 4 > len(data):
            break
        path_len = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        if path_len == 0:
            break
        if offset + path_len + 8 > len(data):
            break
        rel_path = data[offset:offset + path_len].decode("utf-8")
        offset += path_len
        file_size = struct.unpack_from("<Q", data, offset)[0]
        offset += 8
        if offset + file_size > len(data):
            break
        entries.append({"name": rel_path, "size": file_size})
        offset += file_size
    return entries


def pack_dir(dir_path: str, on_skip=None) -> tuple[bytes, int]:
    buf = bytearray()
    base = Path(dir_path).resolve()
    skipped = 0

    # os.walk itself can raise PermissionError on inaccessible subdirs
    def safe_walk(path):
        try:
            for root, dirs, files in os.walk(path):
                # Remove dirs we can't access so os.walk doesn't descend into them
                accessible = []
                for d in dirs:
                    try:
                        os.listdir(os.path.join(root, d))
                        accessible.append(d)
                    except (OSError, PermissionError):
                        if on_skip:
                            on_skip(os.path.join(root, d), PermissionError("cannot list directory"))
                dirs[:] = accessible
                yield root, dirs, files
        except (OSError, PermissionError) as exc:
            if on_skip:
                on_skip(path, exc)

    for root, dirs, files in safe_walk(dir_path):
        for name in sorted(files):
            full = os.path.join(root, name)
            try:
                if not os.access(full, os.R_OK):
                    skipped += 1
                    if on_skip:
                        on_skip(full, PermissionError("no read permission"))
                    continue
                rel = str(Path(full).resolve().relative_to(base)).replace("\\", "/")
                with open(full, "rb") as f:
                    content = f.read()
            except Exception as exc:
                skipped += 1
                if on_skip:
                    on_skip(full, exc)
                continue
            path_enc = rel.encode("utf-8")
            buf += struct.pack("<I", len(path_enc))
            buf += path_enc
            buf += struct.pack("<Q", len(content))
            buf += content

    buf += _TERMINATOR
    return bytes(buf), skipped


def unpack_dir(data: bytes, output_dir: str) -> list[str]:
    os.makedirs(output_dir, exist_ok=True)
    created: list[str] = []
    offset = 0

    while offset < len(data):
        if offset + 4 > len(data):
            break  # truncated
        path_len = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        if path_len == 0:
            break  # end-of-archive

        if offset + path_len + 8 > len(data):
            break
        rel_path = data[offset:offset + path_len].decode("utf-8")
        offset += path_len

        file_size = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        if offset + file_size > len(data):
            break
        content = data[offset:offset + file_size]
        offset += file_size

        dest = os.path.join(output_dir, rel_path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(content)
        created.append(dest)

    return created


def is_dir_archive(header_flags: int) -> bool:
    return bool(header_flags & FLAG_DIRECTORY)
