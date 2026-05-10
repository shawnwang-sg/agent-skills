"""Smarter parser: scan for pinyin table start by looking for 'a' entry."""
import struct
from pathlib import Path

def read_utf16(data, length):
    return data[:length].decode('utf-16-le', errors='replace')

def parse(path):
    raw = Path(path).read_bytes()
    print(f"file size: {len(raw):,} bytes")

    # Scan for pinyin table: looking for pattern (idx)(len=2)(a)
    # which is 6 bytes: XX XX 02 00 61 00 where XX XX is small index (0 or 1)
    target = b'\x02\x00\x61\x00'  # len=2, "a"
    candidates = []
    i = 0
    while i < len(raw) - 4:
        idx = raw.find(target, i)
        if idx == -1:
            break
        # check the byte 2 before this -- should be a small index
        if idx >= 2:
            prev_idx = struct.unpack_from('<H', raw, idx - 2)[0]
            if prev_idx < 10:
                candidates.append(idx - 2)
        i = idx + 1

    print(f"pinyin table candidate offsets: {[hex(c) for c in candidates]}")

    for start in candidates:
        print(f"\n--- trying offset 0x{start:x} ---")
        pos = start
        pinyins = []
        while pos + 4 <= len(raw):
            idx, pylen = struct.unpack_from('<HH', raw, pos)
            pos += 4
            if pylen == 0 or pylen > 20 or pylen % 2 != 0:
                pos -= 4
                break
            py = read_utf16(raw[pos:pos+pylen], pylen)
            pos += pylen
            if not all(c.isascii() and c.isalpha() for c in py):
                pos -= (4 + pylen)
                break
            pinyins.append(py)
        print(f"  parsed {len(pinyins)} pinyins")
        if pinyins:
            print(f"  first 8: {pinyins[:8]}")
            print(f"  last 5: {pinyins[-5:]}")

        if len(pinyins) > 200:
            word_start = pos
            return parse_words(raw, pinyins, word_start, path)

    print("could not parse pinyin table")

def parse_words(raw, pinyins, start, path):
    print(f"\n--- words from 0x{start:x} ---")
    words = []
    pos = start
    while pos + 4 <= len(raw):
        try:
            same_count, py_index_byte_len = struct.unpack_from('<HH', raw, pos)
            if same_count == 0 or same_count > 1000 or py_index_byte_len == 0 or py_index_byte_len > 200 or py_index_byte_len % 2 != 0:
                pos += 1
                continue
            pos += 4
            py_indices = []
            for _ in range(py_index_byte_len // 2):
                if pos + 2 > len(raw): break
                pi = struct.unpack_from('<H', raw, pos)[0]
                pos += 2
                py_indices.append(pi)
            py_str = "'".join(pinyins[i] if i < len(pinyins) else '?' for i in py_indices)
            for _ in range(same_count):
                if pos + 2 > len(raw): break
                wlen = struct.unpack_from('<H', raw, pos)[0]
                pos += 2
                if wlen == 0 or wlen > 200 or wlen % 2 != 0:
                    break
                w = read_utf16(raw[pos:pos+wlen], wlen)
                pos += wlen
                if pos + 2 > len(raw): break
                ext_len = struct.unpack_from('<H', raw, pos)[0]
                pos += 2 + ext_len
                words.append((py_str, w))
        except Exception:
            pos += 1
    print(f"parsed {len(words)} words")
    for py, w in words[:25]:
        print(f"  {py:30s}  {w}")
    print("...")
    for py, w in words[-10:]:
        print(f"  {py:30s}  {w}")

    out = Path(path).with_suffix('.glossary.txt')
    seen = set()
    with out.open('w', encoding='utf-8') as f:
        for py, w in words:
            if w in seen: continue
            seen.add(w)
            f.write(f"{w}\t{py}\n")
    print(f"\nwrote {out} ({len(seen)} unique entries)")

if __name__ == '__main__':
    parse(r"C:\Users\Shugu\Desktop\f840fb925ff5e563ad060fb7c21f2512.qcel")
