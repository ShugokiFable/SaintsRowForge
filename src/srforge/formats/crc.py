"""Volition CRC (standard CRC-32 table, init 0, no final xor, lowercase input)."""

_TABLE = None


def _table():
    global _TABLE
    if _TABLE is None:
        tbl = []
        for i in range(256):
            c = i
            for _ in range(8):
                c = (c >> 1) ^ (0xEDB88320 if c & 1 else 0)
            tbl.append(c)
        _TABLE = tbl
    return _TABLE


def crc_volition(data) -> int:
    if isinstance(data, str):
        data = data.encode("latin-1", "replace")
    data = data.lower()
    crc = 0
    tbl = _table()
    for b in data:
        crc = tbl[(crc ^ b) & 0xFF] ^ (crc >> 8)
    return crc & 0xFFFFFFFF


if __name__ == "__main__":
    # Reference: table from ThomasJepp.SaintsRow Hashes.cs starts with
    # 0x00000000, 0x77073096 ... (standard CRC-32 table)
    assert _table()[1] == 0x77073096
    assert crc_volition("abc") == 0xC241243C  # standard crc32(b"abc") == 0xC241243C
    print("crc_volition OK")
