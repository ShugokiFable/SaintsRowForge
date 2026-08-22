"""Per-game adapter glue: vanilla archives of interest + package naming."""
from ..core.index import GameIndex


class GameAdapter:
    key = None
    asm_version = None

    def __init__(self, install_path):
        self.install = install_path
        self.index = GameIndex(install_path, self.key)


class SRTT(GameAdapter):
    key = "srtt"
    asm_version = 0x0B
    common_tables = ["weapons.xtbl", "vehicle_records.xtbl", "npc_spawner_objects.xtbl"]


class SRIV(GameAdapter):
    key = "sriv"
    asm_version = 0x0C
    common_tables = ["weapons.xtbl", "vehicles.xtbl", "customize_items.xtbl"]


def adapter_for(game, install_path):
    if game == "srtt":
        return SRTT(install_path)
    if game == "sriv":
        return SRIV(install_path)
    raise ValueError(f"unknown game {game!r}")
