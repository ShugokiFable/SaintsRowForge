"""Synthetic vanilla fixtures: valid VPP/STR2/ASM/XTBL/strings files with the
exact binary layouts of SRTT/SRIV. Lets every round-trip + failure test run
without redistributing game assets.
"""
import os
import struct

from srforge.formats import vpp
from srforge.formats.crc import crc_volition


def make_xtbl(records):
    """records: list of (name, {field: value or dict})"""
    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<root>",
             "<Table_Name>Test_Table</Table_Name>", "\t<Records>"]
    for name, fields in records:
        lines.append("\t\t<Record>")
        lines.append(f"\t\t\t<Name>{name}</Name>")

        def emit(d, depth):
            out = []
            for k, v in d.items():
                if isinstance(v, dict):
                    out.append("\t" * depth + f"<{k}>")
                    out += emit(v, depth + 1)
                    out.append("\t" * depth + f"</{k}>")
                else:
                    out.append("\t" * depth + f"<{k}>{v}</{k}>")
            return out
        lines += emit(fields, 3)
        lines.append("\t\t</Record>")
    lines.append("\t</Records>")
    lines.append("</root>")
    return "\n".join(lines) + "\n"


def make_asm(version, containers):
    """containers: [(name, container_type_byte)] -> asm_pc bytes."""
    out = bytearray()
    if version == 0x0C:
        out += struct.pack("<IHh", 0xBEEFFEED, 0x000C, len(containers))
    else:
        # 0x0B header layout is identical signature/version/count per reference impl
        out += struct.pack("<IHh", 0xBEEFFEED, 0x000B, len(containers))
    # type tables: allocator / primitive / container counts (empty is valid)
    out += struct.pack("<I", 0)  # allocators
    out += struct.pack("<I", 0)  # primitive types
    out += struct.pack("<I", 0)  # container types
    for cname, ctype in containers:
        nb = cname.encode("ascii")
        out += struct.pack("<H", len(nb)) + nb
        out += struct.pack("<B", ctype)
        out += struct.pack("<H", 0)          # flags
        out += struct.pack("<h", 1)          # primitive count
        out += struct.pack("<I", 0x50)       # packfile base offset (patched later)
        if version == 0x0C:
            out += struct.pack("<B", 0x09)   # compression type (0x0C only)
        out += struct.pack("<H", 0)          # stub parent len
        aux = b""
        out += struct.pack("<i", len(aux)) + aux
        out += struct.pack("<i", 0x1000)     # total compressed read size
        # write-time sizes for 1 primitive
        out += struct.pack("<II", 0x10, 0x20)
        # primitive: name + PrimitiveData(0x0D)
        pn = ("01.casm_pc" if ".str2_pc" in cname else cname).encode()
        out += struct.pack("<H", len(pn)) + pn
        out += struct.pack("<BBBB I I B",
                           0x01, 0x02, 0x00, 0x00, 0x10, 0x20, 0x03)
    return bytes(out)


def make_fixture_game(root, game="sriv"):
    """Creates <root>/games/<game>/ with a base vpp + patch vpp + loose file."""
    gdir = os.path.join(root, "games", game)
    os.makedirs(gdir, exist_ok=True)

    # weapons.xtbl in a base vpp; patched copy in patch_compressed (must win)
    weapons_vanilla = make_xtbl([
        ("Pump Shotgun", {"Weapon": {"Damage": "85", "Impulse": "240"}}),
        ("SMG", {"Weapon": {"Damage": "30", "Clip_Size": "40"}}),
    ]).encode()
    base = os.path.join(gdir, "tables.vpp_pc")
    vpp.write_packfile(base, {"weapons.xtbl": weapons_vanilla},
                       condensed=True, compressed=True)

    patch_weapons = make_xtbl([
        ("Pump Shotgun", {"Weapon": {"Damage": "85", "Impulse": "240"}}),
        ("SMG", {"Weapon": {"Damage": "33", "Clip_Size": "45"}}),  # patched row
    ]).encode()
    patch = os.path.join(gdir, "patch_compressed.vpp_pc")
    vpp.write_packfile(patch, {"weapons.xtbl": patch_weapons},
                       condensed=True, compressed=True)

    loose = os.path.join(gdir, "readme.txt")
    open(loose, "w").write("fixture game")

    # strings file inside misc.vpp_pc
    from srforge.formats.strings import StringsFile
    sf = StringsFile()
    sf.strings[0x1234] = "Hello Steelport"
    misc = os.path.join(gdir, "misc.vpp_pc")
    vpp.write_packfile(misc, {"test_le_strings.txt": sf.to_bytes()},
                       condensed=False, compressed=False)

    return gdir


if __name__ == "__main__":
    import tempfile
    d = tempfile.mkdtemp(prefix="srfx_")
    g = make_fixture_game(d)
    print("fixture at", g)
    print(sorted(os.listdir(g)))
