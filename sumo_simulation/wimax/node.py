from dataclasses import dataclass
from typing import Dict
from .config import WiMAXConfig
from .phy import WiMAXPhy
from .mac import WiMAXMac


@dataclass
class WiMAXMobileStation:
    ms_id: str
    x: float
    y: float


class WiMAXBaseStation:
    def __init__(self, bs_id: str, x: float, y: float, config: WiMAXConfig):
        self.bs_id = bs_id
        self.x = x
        self.y = y
        self.config = config
        self.phy = WiMAXPhy(config)
        self.mac = WiMAXMac(config, self.phy)
        self.mobiles: Dict[str, WiMAXMobileStation] = {}

    def attach(self, ms: WiMAXMobileStation):
        self.mobiles[ms.ms_id] = ms

    def detach(self, ms_id: str):
        self.mobiles.pop(ms_id, None)

    def _distance_to(self, x: float, y: float) -> float:
        dx = self.x - x
        dy = self.y - y
        return (dx * dx + dy * dy) ** 0.5

    def step(self):
        ms_to_distance = {ms_id: self._distance_to(ms.x, ms.y) for ms_id, ms in self.mobiles.items()}
        self.mac.schedule(ms_to_distance)

    def enqueue_beacon(self, ms_id: str, payload_bytes: int):
        self.mac.enqueue(ms_id, payload_bytes)

    def get_metrics(self):
        return {
            "bs_id": self.bs_id,
            "mobiles": list(self.mobiles.keys()),
            "kpis": self.mac.metrics(),
        }

