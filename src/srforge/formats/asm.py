"""Asset Assembler (.asm_pc) reader/updater for Stream2 versions 0x0B (SRTT)
and 0x0C (SRIV/GOOH). Ported from ThomasJepp.SaintsRow AssetAssembler/.

Update semantics (from BuildPackfile.Update): when a str2_pc is rebuilt,
its container in the asm gets PackfileBaseOffset = str2 data-start offset,
TotalCompressedPackfileReadSize = str2 compressed_data_size, and per-primitive
CPUSize/GPUSize refreshed from the rebuilt str2 entries (GPU entry name =
same name with .cNNN extension swapped to .gNNN).
"""
import os
import struct

SIGNATURE = 0xBEEFFEED


class AsmPrimitive:
    __slots__ = ("name", "ptype", "allocator", "pflags", "ext_index",
                 "cpu_size", "gpu_size", "alloc_group")

    def __repr__(self):
        return f"<prim {self.name!r} cpu={self.cpu_size} gpu={self.gpu_size}>"


class AsmContainer:
    __slots__ = ("name", "ctype", "flags", "packfile_base_offset", "compression_type",
                 "stub_parent", "aux_data", "total_compressed_read_size", "primitives")

    def __repr__(self):
        return f"<container {self.name!r} prims={len(self.primitives)}>"


class AsmFile:
    def __init__(self, data: bytes):
        self.raw = data
        sig, self.version, num_containers = struct.unpack_from("<IHh", data, 0)
        if sig != SIGNATURE:
            raise ValueError(f"not an asm_pc (signature 0x{sig:08X})")
        if self.version not in (0x0B, 0x0C):
            raise NotImplementedError(f"unsupported asm version 0x{self.version:X}")
        pos = 8
        self.allocator_types = {}
        self.primitive_types = {}
        self.container_types = {}
        for dest in (self.allocator_types, self.primitive_types, self.container_types):
            (count,) = struct.unpack_from("<I", data, pos); pos += 4
            for _ in range(count):
                (slen,) = struct.unpack_from("<H", data, pos); pos += 2
                name = data[pos:pos + slen].decode("ascii"); pos += slen
                dest[data[pos]] = name; pos += 1
        self.containers: list[AsmContainer] = []
        for _ in range(num_containers):
            pos = self._read_container(data, pos)

    def _read_string(self, data, pos):
        (slen,) = struct.unpack_from("<H", data, pos); pos += 2
        s = data[pos:pos + slen].decode("ascii")
        return s, pos + slen

    def _read_container(self, data, pos):
        c = AsmContainer()
        c.name, pos = self._read_string(data, pos)
        (c.ctype,) = struct.unpack_from("<B", data, pos); pos += 1
        (c.flags,) = struct.unpack_from("<H", data, pos); pos += 2
        (prim_count,) = struct.unpack_from("<h", data, pos); pos += 2
        (c.packfile_base_offset,) = struct.unpack_from("<I", data, pos); pos += 4
        if self.version == 0x0C:
            (c.compression_type,) = struct.unpack_from("<B", data, pos); pos += 1
        else:
            c.compression_type = None
        c.stub_parent, pos = self._read_string(data, pos)
        (aux_len,) = struct.unpack_from("<i", data, pos); pos += 4
        c.aux_data = data[pos:pos + aux_len]; pos += aux_len
        (c.total_compressed_read_size,) = struct.unpack_from("<i", data, pos); pos += 4
        wt_sizes = []
        for _ in range(max(prim_count, 0)):
            cpu, gpu = struct.unpack_from("<II", data, pos); pos += 8
            wt_sizes.append((cpu, gpu))
        c.primitives = []
        for i in range(max(prim_count, 0)):
            p = AsmPrimitive()
            p.name, pos = self._read_string(data, pos)
            # PrimitiveData is 0x0D bytes: type, allocator, flags,
            # extension_index, cpu_size u32, gpu_size u32, allocation_group
            (p.ptype, p.allocator, p.pflags, p.ext_index, p.cpu_size,
             p.gpu_size, p.alloc_group) = struct.unpack_from("<4BIIB", data,
                                                             pos)
            pos += 0x0D
            p.cpu_size, p.gpu_size = wt_sizes[i]
            c.primitives.append(p)
        self.containers.append(c)
        return pos

    def save(self) -> bytes:
        out = bytearray()
        out += struct.pack("<IHh", SIGNATURE, self.version, len(self.containers))
        for types in (self.allocator_types, self.primitive_types, self.container_types):
            out += struct.pack("<I", len(types))
            for bid, name in types.items():
                nb = name.encode("ascii")
                out += struct.pack("<H", len(nb)) + nb + struct.pack("<B", bid)
        for c in self.containers:
            nb = c.name.encode("ascii")
            out += struct.pack("<H", len(nb)) + nb
            out += struct.pack("<B", c.ctype)
            out += struct.pack("<H", c.flags)
            out += struct.pack("<h", len(c.primitives))
            out += struct.pack("<I", c.packfile_base_offset)
            if self.version == 0x0C:
                out += struct.pack("<B", c.compression_type)
            sb = (c.stub_parent or "").encode("ascii")
            out += struct.pack("<H", len(sb))
            if sb:
                out += sb
            out += struct.pack("<i", len(c.aux_data)) + c.aux_data
            out += struct.pack("<i", c.total_compressed_read_size)
            for p in c.primitives:
                out += struct.pack("<II", p.cpu_size, p.gpu_size)
            for p in c.primitives:
                out += struct.pack("<H", len(p.name.encode("ascii"))) + p.name.encode("ascii")
                out += struct.pack("<4BIIB", p.ptype, p.allocator, p.pflags,
                                   p.ext_index, p.cpu_size, p.gpu_size,
                                   p.alloc_group)
        return bytes(out)

    @classmethod
    def parse(cls, data: bytes) -> "AsmFile":
        return cls(data)

    def to_bytes(self) -> bytes:
        return self.save()

    def update_container_sizes(self, str2_path: str):
        """Update one container from a rebuilt str2 on disk.

        Returns the updated AsmContainer, or None if no container matches
        (caller must fail loudly - never silently ship an un-updated ASM).
        """
        stem = os.path.splitext(os.path.basename(str2_path))[0]
        if self.get_container(stem) is None:
            return None
        with open(str2_path, "rb") as f:
            self.update_container_from_str2(stem, f.read())
        return self.get_container(stem)

    def get_container(self, name: str):
        low = name.lower()
        if low.endswith(".str2_pc"):
            low = low[:-len(".str2_pc")]
        for c in self.containers:
            cn = c.name.lower()
            if cn.endswith(".str2_pc"):
                cn = cn[:-len(".str2_pc")]
            if cn == low:
                return c
        return None

    def update_container_from_str2(self, container_name: str, str2_bytes: bytes):
        """Apply the reference BuildPackfile -asm update for one rebuilt str2."""
        from .vpp import VppFile
        pf = VppFile(str2_bytes)
        if pf.num_files == 0:
            raise ValueError("rebuilt str2 has no entries")
        stem = container_name
        if stem.lower().endswith(".str2_pc"):
            stem = stem[:-len(".str2_pc")]
        c = self.get_container(stem)
        if c is None:
            raise KeyError(f"container {container_name!r} not in asm")
        # data start: header + dir + names (verified vs vanilla SRIV items
        # .vpp_pc: 0x28 + 0x18*num_files + filename_size, e.g. 216)
        c.packfile_base_offset = (0x28 + 0x18 * pf.num_files
                                  + pf.filename_size)
        c.total_compressed_read_size = pf.compressed_data_size
        by_name = {e.name.lower(): e for e in pf.entries}
        updated = []
        for p in c.primitives:
            e = by_name.get(p.name.lower())
            if e is not None:
                p.cpu_size = e.size
                stem, dot, ext = p.name.rpartition(".")
                if dot and ext.startswith("c"):
                    gpu_name = stem + ".g" + ext[1:]
                    ge = by_name.get(gpu_name.lower())
                    if ge is not None:
                        p.gpu_size = ge.size
            updated.append(p.name)
        return {"container": c.name, "base_offset": c.packfile_base_offset,
                "total_compressed_read_size": pf.compressed_data_size,
                "primitives_updated": updated}


if __name__ == "__main__":
    # round-trip self-check on a synthetic 0x0C asm
    a = AsmFile.__new__(AsmFile)
    a.version = 0x0C
    a.allocator_types = {0: "static"}
    a.primitive_types = {1: "generic"}
    a.container_types = {2: "stream"}
    c = AsmContainer()
    c.name = "test_container"
    c.ctype = 2
    c.flags = 3
    c.packfile_base_offset = 64
    c.compression_type = 9
    c.stub_parent = ""
    c.aux_data = b"\x01\x02"
    c.total_compressed_read_size = 100
    p = AsmPrimitive()
    p.name = "cmesh.cmesh_pc"; p.ptype = 1; p.allocator = 0; p.pflags = 0
    p.ext_index = 0; p.cpu_size = 10; p.gpu_size = 20; p.alloc_group = 0
    c.primitives = [p]
    a.containers = [c]
    blob = a.save()
    b = AsmFile(blob)
    assert b.containers[0].name == "test_container"
    assert b.containers[0].primitives[0].gpu_size == 20
    assert b.save() == blob
    print("asm round-trip OK")
