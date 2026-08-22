"""le_strings reader/writer (SRTT/SRIV/GOOH language files).

Header 0x0C: id(0xA84C7F73) version(1) bucket_count(u16) string_count(u32)
Buckets 0x08 each right after header: {string_count u32, strings_offset u32}
Strings offset table per bucket -> entries {hash u32, utf16 chars..., NUL}.
Bucket count policy mirrors the reference builder.
"""
import struct

from .crc import crc_volition


class StringsFile:
    def __init__(self):
        self.strings = {}  # hash -> text

    @classmethod
    def parse(cls, data: bytes):
        f = cls()
        fid, ver, nbuckets, nstrings = struct.unpack_from("<IHHI", data, 0)
        if fid != 0xA84C7F73:
            raise ValueError("not a le_strings file")
        for i in range(nbuckets):
            base = 0x0C + i * 8
            cnt, off = struct.unpack_from("<II", data, base)
            for j in range(cnt):
                spos = off + j * 4
                (so,) = struct.unpack_from("<I", data, spos)
                (h,) = struct.unpack_from("<I", data, so)
                end = data.index(b"\x00\x00", so + 4)
                if end % 2:
                    end += 1
                text = data[so + 4:end].decode("utf-16-le")
                f.strings[h] = text
        return f

    def to_bytes(self) -> bytes:
        items = sorted(self.strings.items())
        n = len(items)
        nbuckets = n // 5
        for threshold in (32, 64, 128, 256, 512):
            if nbuckets < threshold:
                nbuckets = threshold
                break
        else:
            nbuckets = 1024
        buckets = [[] for _ in range(nbuckets)]
        mask = nbuckets - 1
        for h, t in items:
            buckets[h & mask].append((h, t))

        header_size = 0x0C + nbuckets * 8
        # layout: header, bucket array, per-bucket offset tables, then string
        # records. Bucket StringOffset points at that bucket's offset table;
        # table entries hold ABSOLUTE offsets of [hash][utf16][NUL] records.
        pos = header_size + sum(4 * len(b) for b in buckets)
        out = bytearray(pos)
        struct.pack_into("<IHHI", out, 0, 0xA84C7F73, 1, nbuckets, n)
        table_offs = []
        t = header_size
        for b in buckets:
            table_offs.append(t)
            t += 4 * len(b)
        for i, b in enumerate(buckets):
            struct.pack_into("<II", out, 0x0C + i * 8, len(b), table_offs[i])
        cursor = pos
        for i, b in enumerate(buckets):
            for k, (h, text) in enumerate(b):
                rec = struct.pack("<I", h) + text.encode("utf-16-le") + b"\x00\x00"
                struct.pack_into("<I", out, table_offs[i] + k * 4, cursor)
                need = cursor + len(rec)
                if need > len(out):
                    out.extend(b"\x00" * (need - len(out)))
                out[cursor:need] = rec
                cursor = need
                while cursor % 4:
                    if cursor >= len(out):
                        out.append(0)
                    else:
                        out[cursor] = 0
                    cursor += 1
        return bytes(out)

    @staticmethod
    def hash_text(text: str) -> int:
        return crc_volition(text.lower())


if __name__ == "__main__":
    s = StringsFile()
    s.strings[0x11111111] = "Hello Steelport"
    s.strings[0x22222222] = "Hail to the Chief, baby."
    s.strings[0x33333333] = ""
    blob = s.to_bytes()
    p = StringsFile.parse(blob)
    assert p.strings == s.strings, (p.strings, s.strings)
    print("le_strings round-trip OK")
