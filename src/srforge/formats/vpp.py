"""VPP packfile v0x0A reader/writer (SRTT + SRIV .vpp_pc / .str2_pc).

Ported from ThomasJepp.SaintsRow Packfiles/Version0A (license: see
THIRD-PARTY-NOTICES.md). Layout facts verified against that source:

header (0x28 bytes, u32 LE x10):
  descriptor 0x51890ACE | version 0x0A | header_checksum | file_size |
  flags(bit0 compressed, bit1 condensed) | num_files | dir_size |
  filename_size | data_size(uncompressed) | compressed_data_size
entry (0x18 bytes x num_files at 0x28):
  filename_offset(u32) | pad u32 | start(u32) | size(u32) |
  compressed_size(u32) | flags(u16, bit0 compressed) | alignment(u16)
then name block (relative offsets, 2-aligned), then data.

Compressed+condensed archives are ONE zlib stream over all file payloads in
order (sync-flush per file in the reference writer; we reproduce that so
per-entry compressed sizes line up).
"""
import struct
import zlib

from .crc import crc_volition

DESCRIPTOR = 0x51890ACE
VERSION = 0x0A
FLAG_COMPRESSED = 0x01
FLAG_CONDENSED = 0x02


class VppEntry:
    __slots__ = ("name", "start", "size", "compressed_size", "flags",
                 "alignment", "filename_offset")

    def __init__(self, name, start=0, size=0, compressed_size=0, flags=0,
                 alignment=1, filename_offset=0):
        self.name = name
        self.start = start
        self.size = size
        self.compressed_size = compressed_size
        self.flags = flags
        self.alignment = alignment
        self.filename_offset = filename_offset


class VppFile:
    """Reader: parses an opened vpp_pc/str2_pc. Writer: build_vpp()."""

    def __init__(self, data: bytes):
        self.raw = data
        if len(data) < 0x28:
            raise ValueError("file too small to be a vpp packfile")
        (self.descriptor, self.version, self.header_checksum, self.file_size,
         self.flags, self.num_files, self.dir_size, self.filename_size,
         self.data_size, self.compressed_data_size) = struct.unpack_from("<10I", data, 0)
        if self.descriptor != DESCRIPTOR:
            raise ValueError(f"bad descriptor 0x{self.descriptor:08X} (not a vpp_pc)")
        if self.version != VERSION:
            raise ValueError(f"unsupported packfile version 0x{self.version:X}")
        self.is_compressed = bool(self.flags & FLAG_COMPRESSED)
        self.is_condensed = bool(self.flags & FLAG_CONDENSED)

        # header checksum check (CRC over bytes 0x0C..0x28)
        self.checksum_ok = (crc_bytes(data[0x0C:0x28]) == self.header_checksum)

        self.entries: list[VppEntry] = []
        off = 0x28
        running = 0
        for i in range(self.num_files):
            (fn_off, _pad, start, size, csize, eflags, align) = struct.unpack_from("<IIIIIHH", data, off)
            off += 0x18
            if self.is_condensed and self.is_compressed:
                start, size = running, size  # reference reader recomputes start
                running += size
            elif self.is_condensed:
                start = running
                running += _align(size, 16)
            entry = VppEntry("", start, size, csize, eflags, align,
                             filename_offset=fn_off)
            self.entries.append(entry)

        # names block (entries carry filename_offset; use it, don't re-scan)
        names_base = 0x28 + 0x18 * self.num_files
        for e in self.entries:
            p = names_base + e.filename_offset
            end = data.index(b"\x00", p)
            e.name = data[p:end].decode("ascii")

        # payload decompression is LAZY: listing/indexing a multi-GB vpp must
        # not inflate the data section (directory block is always plain).
        # Data starts right after the names block (verified against vanilla
        # SRIV misc_tables.vpp_pc: 0x28+dir_size+filenames_size, zlib 78da
        # on the first byte - the C# writer's align(2) walk lands there too)
        self._payload = None
        self._data_offset = names_base + self.filename_size

    @classmethod
    def list_entries(cls, path):
        """Header + directory + names only. No payload read. For indexing."""
        with open(path, "rb") as f:
            head = f.read(0x28)
            if len(head) < 0x28:
                raise ValueError(f"too small to be a vpp: {path}")
            (descriptor, version, _ck, _fsize, flags, num, _dir_size,
             fn_size, _data_size, _cdata_size) = struct.unpack("<10I", head)
            if descriptor != DESCRIPTOR or version != VERSION:
                raise ValueError(f"not a v0x0A vpp: {path}")
            compressed = bool(flags & FLAG_COMPRESSED)
            condensed = bool(flags & FLAG_CONDENSED)
            raw = f.read(0x18 * num)
            entries = []
            running = 0
            for i in range(num):
                (fn_off, _pad, start, size, csize, eflags, align) = \
                    struct.unpack_from("<IIIIIHH", raw, i * 0x18)
                if condensed and compressed:
                    start, size = running, size
                    running += size
                elif condensed:
                    start = running
                    running += _align(size, 16)
                entries.append(VppEntry("", start, size, csize, eflags, align))
            nb = f.read(fn_size + 16)
            pos = 0
            for e in entries:
                while nb[pos] == 0:
                    pos += 1
                end = nb.index(b"\x00", pos)
                e.name = nb[pos:end].decode("ascii")
                pos = end + 1
                while pos % 2:
                    pos += 1
            return entries

    @classmethod
    def from_file(cls, path):
        with open(path, "rb") as f:
            return cls(f.read())

    def files(self):
        return self.entries

    def read_entry(self, entry: VppEntry) -> bytes:
        if self.is_compressed and self.is_condensed:
            if self._payload is None:
                blob = self.raw[self._data_offset:
                                self._data_offset + self.compressed_data_size]
                # ponytail: tolerant inflate - vanilla streams can end without
                # a clean Z_FINISH; exact-length check is the real gate
                d = zlib.decompressobj()
                self._payload = d.decompress(blob) + d.flush()
                # ponytail: vanilla archives can declare a slightly larger
                # data_size than the stream actually inflates (observed: SRIV
                # items.vpp_pc str2s, -5B; reference C# Read() tolerates it
                # silently) - record it, gate real reads by bounds instead
                self.payload_truncated = len(self._payload) < self.data_size
            return self._payload[entry.start:entry.start + entry.size]
        if entry.flags & 0x01:  # individually compressed entry
            # ponytail: vanilla streams aren't always cleanly terminated;
            # tolerant inflate + exact-length check
            d = zlib.decompressobj()
            out = d.decompress(self.raw[self._data_offset + entry.start:
                                        self._data_offset + entry.start
                                        + entry.compressed_size])
            out += d.flush()
            if len(out) != entry.size:
                raise ValueError(f"entry {entry.name} inflate size mismatch")
            return out
        return self.raw[self._data_offset + entry.start:
                        self._data_offset + entry.start + entry.size]

    def get(self, name: str) -> bytes:
        low = name.lower()
        for e in self.entries:
            if e.name.lower() == low:
                return self.read_entry(e)
        raise KeyError(name)


def crc_bytes(b: bytes) -> int:
    from .crc import crc_volition
    return crc_volition(b)


def _align(v, a):
    return (v + a - 1) // a * a if a > 1 else v


def build_vpp(files: list[tuple[str, bytes]], condensed=True, compressed=True,
              is_str2=False, level=9) -> bytes:
    """Build a vpp_pc/str2_pc. Mirrors the reference Save() semantics."""
    n = len(files)
    names_blob = bytearray()
    fn_offsets = []
    for name, _ in files:
        while len(names_blob) % 2:
            names_blob.append(0)
        fn_offsets.append(len(names_blob))
        names_blob += name.encode("ascii") + b"\x00"
        while len(names_blob) % 2:
            names_blob.append(0)
    filename_size = len(names_blob)

    dir_size = 0x18 * n
    data_start = _align(0x28 + dir_size + filename_size, 2)
    # reference computes data start via per-name alignment; ours already aligned

    entries = []
    payload = bytearray()
    co = zlib.compressobj(level, zlib.DEFLATED, 15) if (compressed and condensed) else None
    comp_total = 0
    uncomp_total = 0
    file_start = 0

    for i, (name, data) in enumerate(files):
        e = VppEntry(name)
        e.size = len(data)
        e.alignment = 16 if condensed else 1
        if co is not None:
            chunk = co.compress(data) + co.flush(zlib.Z_SYNC_FLUSH)
            e.start = file_start if is_str2 else file_start
            e.compressed_size = len(chunk)
            e.flags = 1
            payload += chunk
            comp_total += len(chunk)
            if is_str2:
                file_start += _align(e.size, 16)
                uncomp_total += _align(e.size, 16)
            else:
                file_start += e.size
                uncomp_total += e.size
        elif condensed:
            e.compressed_size = 0xFFFFFFFF
            e.start = file_start
            payload += data
            pad = _align(e.size, 16) - e.size
            payload += b"\x00" * pad
            file_start += _align(e.size, 16)
            uncomp_total += _align(e.size, 16) if i < n - 1 else e.size
        else:
            e.compressed_size = 0xFFFFFFFF
            e.start = file_start
            payload += data
            file_start += e.size
            uncomp_total += e.size
        entries.append(e)

    if co is not None:
        payload += co.flush()
    comp_total = len(payload) if (compressed and condensed) else comp_total

    total_size = data_start + len(payload)
    header = bytearray(0x28)
    struct.pack_into("<10I", header, 0,
                     DESCRIPTOR, VERSION, 0, total_size,
                     (FLAG_CONDENSED if condensed else 0) | (FLAG_COMPRESSED if compressed else 0),
                     n, dir_size, filename_size, uncomp_total,
                     comp_total if compressed else 0xFFFFFFFF)
    buf = bytearray(total_size)
    buf[0:0x28] = header
    off = 0x28
    for e, fno in zip(entries, fn_offsets):
        struct.pack_into("<IIIIIHH", buf, off, fno, 0, e.start, e.size,
                         e.compressed_size, e.flags, e.alignment)
        off += 0x18
    buf[off:off + filename_size] = names_blob
    buf[data_start:data_start + len(payload)] = payload

    # header checksum: CRC over 0x1C bytes starting at 0x0C
    ck = crc_volition(bytes(buf[0x0C:0x28]))
    struct.pack_into("<I", buf, 0x08, ck)
    return bytes(buf)


def write_packfile(path, files, condensed=True, compressed=True, is_str2=False):
    """files: dict {name: bytes} or list [(name, bytes)]."""
    if isinstance(files, dict):
        files = list(files.items())
    blob = build_vpp(files, condensed=condensed, compressed=compressed, is_str2=is_str2)
    with open(path, "wb") as f:
        f.write(blob)


# canonical name used across core/games/tests
Packfile = VppFile


if __name__ == "__main__":
    # round-trip self-check
    files = [("a.xtbl", b"<table/>" * 10), ("b.txt", b"hello world"), ("c.bin", bytes(range(256)) * 4)]
    for cond, comp in [(True, True), (True, False), (False, False)]:
        blob = build_vpp(files, condensed=cond, compressed=comp)
        rf = VppFile(blob)
        assert [e.name for e in rf.entries] == ["a.xtbl", "b.txt", "c.bin"]
        assert rf.get("b.txt") == b"hello world"
        assert rf.get("c.bin") == bytes(range(256)) * 4
        assert rf.checksum_ok
    print("vpp round-trip OK")
