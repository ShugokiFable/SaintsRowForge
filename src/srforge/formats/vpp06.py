"""VPP version 0x06 (Saints Row: The Third PC) packfile reader/writer.

Ported from ThomasJepp.SaintsRow Packfiles/Version06 (reader; its Save() is
NotImplemented - writers in the wild are Gibbed's, which produce this exact
layout, banner junk included in the unused 0x148-byte name area).

Layout facts (from Version06/Packfile.cs + PackfileFileData.cs):
- header 0x17C bytes; Descriptor 0x51890ACE, Version 6 at +0x04
- runtime junk (shortname/pathname) occupies 0x08..0x14B - ignored on read
- Flags u32 @0x14C (Compressed=1, Condensed=2 - same values as 0x0A)
- NumFiles@0x154, DirectorySize@0x15C, FilenamesSize@0x160,
  DataSize@0x164, CompressedDataSize@0x168 (Sector/DirOff/FnOff/DataOff/
  OpenCount exist but are console-era / zero on PC)
- entry table at align2048(0x180) == 0x800; entries 0x18 bytes:
  FilenameOffset u32, Sector u32, Start u32, Size u32,
  CompressedSize u32, Parent u32
- names at align2048(0x800 + DirectorySize), NUL-terminated ASCII,
  addressed by FilenameOffset from names base
- data at align2048(names_base + FilenamesSize)
- no header checksum in v06
"""
import os
import struct
import zlib

DESCRIPTOR = 0x51890ACE
VERSION = 6
HEADER_SIZE = 0x17C
ENTRIES_OFF = 0x800  # align2048(0x180)
FLAG_COMPRESSED = 0x01
FLAG_CONDENSED = 0x02


def _align(n, a):
    return (n + a - 1) // a * a


class Vpp06Entry:
    __slots__ = ("name", "filename_offset", "sector", "start", "size",
                 "compressed_size", "parent")

    def __init__(self, name="", filename_offset=0, sector=0, start=0,
                 size=0, compressed_size=0xFFFFFFFF, parent=0xFFFFFFFF):
        self.name = name
        self.filename_offset = filename_offset
        self.sector = sector
        self.start = start
        self.size = size
        self.compressed_size = compressed_size
        self.parent = parent


class Vpp06File:
    def __init__(self, raw: bytes):
        self.raw = raw
        (descriptor, version) = struct.unpack_from("<2I", raw, 0)
        if descriptor != DESCRIPTOR:
            raise ValueError("not a Volition packfile")
        if version != VERSION:
            raise ValueError(f"not a v06 packfile (version={version:#x})")
        (self.flags, _sector, self.num_files, _pksize, self.directory_size,
         self.filenames_size, self.data_size, self.compressed_data_size,
         _diroff, _fnoff, _dataoff, _opencount) = \
            struct.unpack_from("<12I", raw, 0x14C)
        self.is_compressed = bool(self.flags & FLAG_COMPRESSED)
        self.is_condensed = bool(self.flags & FLAG_CONDENSED)
        # entry table with running-position normalization (mirrors C# ctor)
        self.entries = []
        pos = ENTRIES_OFF
        running = 0
        for i in range(self.num_files):
            (fnoff, sector, start, size, csize,
             parent) = struct.unpack_from("<6I", raw, pos + i * 0x18)
            if self.is_condensed and self.is_compressed:
                start = running
                running += size
            elif self.is_condensed:
                start = running
                running += _align(size, 16)
            elif self.is_compressed:
                start = running
                running += _align(csize, 2048)
            self.entries.append(Vpp06Entry("", fnoff, sector, start, size,
                                           csize, parent))
        names_base = _align(ENTRIES_OFF + self.directory_size, 2048)
        for e in self.entries:
            p = names_base + e.filename_offset
            end = raw.index(b"\x00", p)
            e.name = raw[p:end].decode("ascii", "replace")
        self._data_offset = _align(names_base + self.filenames_size, 2048)
        self._payload = None

    @classmethod
    def from_file(cls, path):
        with open(path, "rb") as f:
            return cls(f.read())

    @classmethod
    def list_entries(cls, path):
        """Header + directory + names only; no payload inflation."""
        with open(path, "rb") as f:
            head = f.read(HEADER_SIZE)
            (flags, _s, num_files, _p, dir_size, filenames_size,
             _ds, _cds, _do, _fo, _da, _oc) = struct.unpack_from("<12I", head,
                                                                 0x14C)
            need = _align(ENTRIES_OFF + dir_size, 2048) + filenames_size
            raw = head + f.read(max(0, need - HEADER_SIZE))
        pf = cls(raw)
        return pf.entries

    def read_entry(self, entry: Vpp06Entry) -> bytes:
        if self.is_condensed and self.is_compressed:
            if self._payload is None:
                blob = self.raw[self._data_offset:
                                self._data_offset + self.compressed_data_size]
                self._payload = zlib.decompress(blob)
                if len(self._payload) != self.data_size:
                    raise ValueError("decompressed size mismatch")
            return self._payload[entry.start:entry.start + entry.size]
        off = self._data_offset + entry.start
        if self.is_compressed:
            # ponytail: vanilla v06 streams aren't always cleanly terminated;
            # tolerant inflate + exact-length check instead of strict
            # zlib.decompress (upgrade path: none needed, length-checked)
            d = zlib.decompressobj()
            out = d.decompress(self.raw[off:off + entry.compressed_size])
            out += d.flush()
            if len(out) != entry.size:
                raise ValueError(f"entry {entry.name} inflate size mismatch")
            return out
        return self.raw[off:off + entry.size]

    def get(self, name: str) -> bytes:
        low = name.lower()
        for e in self.entries:
            if e.name.lower() == low:
                return self.read_entry(e)
        raise KeyError(name)


def write_vpp06(path, files, condensed=True, compressed=True):
    """Build a v06 packfile. files: iterable[(name, bytes)].

    Modes mirror the 0x0A writer: condensed+compressed = one zlib stream;
    compressed-only = per-entry zlib blobs aligned to 2048 (matches vanilla
    SRTT misc_tables.vpp_pc layout); uncompressed = plain.
    """
    files = [(n, d) for n, d in files]
    n = len(files)
    dir_size = n * 0x18
    name_blob = bytearray()
    for name, _d in files:
        name_blob += name.encode("ascii") + b"\x00"
        while len(name_blob) % 2:
            name_blob.append(0)
    names_base = _align(ENTRIES_OFF + dir_size, 2048)
    filenames_size = len(name_blob)
    data_off = _align(names_base + filenames_size, 2048)

    entries = []
    body = bytearray()
    if condensed and compressed:
        co = zlib.compressobj(9, zlib.DEFLATED, 15)
        running = 0
        for name, data in files:
            start = running
            running += len(data)
            body += co.compress(data)
            body += co.flush(zlib.Z_SYNC_FLUSH)
            entries.append((name, 0, start, len(data)))
        body += co.flush(zlib.Z_FINISH)
        comp_total = len(body)
        entries = [(nm, fo, st, sz, 0xFFFFFFFF, 0xFFFFFFFF)
                   for nm, fo, st, sz in entries]
        flags = FLAG_COMPRESSED | FLAG_CONDENSED
        data_size = running
    elif compressed:
        running = 0
        for name, data in files:
            blob = zlib.compress(data, 9)
            pad = (-len(blob)) % 2048
            entries.append((name, 0, running, len(data), len(blob),
                            0xFFFFFFFF))
            body += blob + b"\x00" * pad
            running += len(blob) + pad
        flags = FLAG_COMPRESSED
        data_size = sum(sz for _, _, _, sz, _c, _p in entries)
        comp_total = len(body)
    else:
        running = 0
        for name, data in files:
            pad = (-len(data)) % 16
            entries.append((name, 0, running, len(data), 0xFFFFFFFF,
                            0xFFFFFFFF))
            body += data + b"\x00" * pad
            running += len(data) + pad
        flags = FLAG_CONDENSED if condensed else 0
        data_size = sum(sz for _, _, _, sz, _c, _p in entries)
        comp_total = len(body)

    header = bytearray(HEADER_SIZE)
    struct.pack_into("<2I", header, 0, DESCRIPTOR, VERSION)
    struct.pack_into("<12I", header, 0x14C, flags, 0, n, 0,
                     dir_size, filenames_size, data_size,
                     comp_total if (flags & FLAG_COMPRESSED) else 0xFFFFFFFF,
                     0, 0, 0, 0)
    ent = bytearray()
    for nm, _fo, start, size, csize, parent in entries:
        fnoff = None
        # compute filename offset within names blob
        acc = 0
        for nm2, _d in files:
            if nm2 == nm:
                fnoff = acc
                break
            acc += len(nm2.encode("ascii")) + 1
            acc += acc % 2  # padding applied above keeps names 2-aligned
        ent += struct.pack("<6I", fnoff, 0, start, size, csize, parent)
    assert len(ent) == dir_size

    with open(path, "wb") as f:
        f.write(header)
        f.write(b"\x00" * (ENTRIES_OFF - HEADER_SIZE))
        f.write(ent)
        f.write(b"\x00" * (names_base - ENTRIES_OFF - dir_size))
        f.write(name_blob)
        f.write(b"\x00" * (data_off - names_base - filenames_size))
        f.write(bytes(body))


if __name__ == "__main__":
    import tempfile
    payload = b"The quick brown fox" * 1000
    files = [("a.xtbl", b"<root/>"), ("big.bin", payload)]
    d = tempfile.mkdtemp()
    for cond in (True, False):
        for comp in (True, False):
            p = os.path.join(d, f"t{int(cond)}{int(comp)}.vpp_pc")
            write_vpp06(p, files, condensed=cond, compressed=comp)
            pf = Vpp06File.from_file(p)
            assert [e.name for e in pf.entries] == ["a.xtbl", "big.bin"]
            assert pf.get("a.xtbl") == b"<root/>"
            assert pf.get("big.bin") == payload, (cond, comp)
    print("vpp06 all four modes round-trip OK")
