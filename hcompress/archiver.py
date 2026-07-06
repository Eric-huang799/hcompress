"""Directory archiver — pack/unpack folders into a single byte stream.

Format (little-endian):

    For each entry:
      [4 bytes: path_len  (uint32 LE)]    0 = end-of-archive marker
      [path_len bytes: rel_path (UTF-8)]
      [8 bytes: file_size  (uint64 LE)]
      [file_size bytes: content]

The resulting byte stream is then compressed by the standard Huffman
engine.  On decompression the flag ``FLAG_DIRECTORY`` in the HCF
header tells the engine to unpack the decoded bytes as a directory
tree.
"""

from __future__ import annotations

import os
import struct
from pathlib import Path

# HCF flags extension
FLAG_DIRECTORY = 1 << 8  # bit 8: archive contains a directory tree

_TERMINATOR = struct.pack("<I", 0)  # path_len = 0 → end


def pack_dir(dir_path: str, on_skip=None) -> tuple[bytes, int]:
    """Walk *dir_path* and produce an archive byte stream.

    Only regular files are included.  Empty directories, symlinks,
    and files that cannot be read (permission / locked) are silently
    skipped.  Returns ``(archive_bytes, skipped_count)``.
    """
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
                # skip locked / unreadable files
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
    """Extract an archive byte stream into *output_dir*.

    Returns a list of created file paths.
    """
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
    """Check whether an HCF file contains a directory archive."""
    return bool(header_flags & FLAG_DIRECTORY)
