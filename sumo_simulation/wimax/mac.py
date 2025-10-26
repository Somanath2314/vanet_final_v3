from dataclasses import dataclass, field
from typing import Dict, List
import time
from .config import WiMAXConfig
from .phy import WiMAXPhy, PhyLinkState


@dataclass
class FlowKPI:
    bytes_sent: int = 0
    bytes_dropped: int = 0
    latency_samples_ms: List[float] = field(default_factory=list)

    def to_dict(self):
        avg_latency = sum(self.latency_samples_ms) / len(self.latency_samples_ms) if self.latency_samples_ms else 0.0
        return {
            "bytes_sent": self.bytes_sent,
            "bytes_dropped": self.bytes_dropped,
            "avg_latency_ms": round(avg_latency, 2),
        }


class WiMAXMac:
    def __init__(self, config: WiMAXConfig, phy: WiMAXPhy):
        self.config = config
        self.phy = phy
        self.ms_to_buffer_bytes: Dict[str, int] = {}
        self.ms_to_last_update_s: Dict[str, float] = {}
        self.ms_to_kpi: Dict[str, FlowKPI] = {}
        self.last_schedule_time_s = time.time()

    def enqueue(self, ms_id: str, bytes_count: int):
        self.ms_to_buffer_bytes[ms_id] = self.ms_to_buffer_bytes.get(ms_id, 0) + bytes_count
        self.ms_to_kpi.setdefault(ms_id, FlowKPI())

    def schedule(self, ms_id_to_distance_m: Dict[str, float]):
        now = time.time()
        if now - self.last_schedule_time_s < self.config.scheduling_granularity_s:
            return

        capacities_bps: Dict[str, float] = {}
        for ms_id, dist in ms_id_to_distance_m.items():
            link: PhyLinkState = self.phy.evaluate_link(dist)
            capacities_bps[ms_id] = link.capacity_bps

        total_capacity_bps = sum(capacities_bps.values())
        if total_capacity_bps <= 0:
            # drop oldest bytes based on target reliability
            for ms_id, buf in list(self.ms_to_buffer_bytes.items()):
                drop = int(buf * (1.0 - self.config.target_reliability))
                if drop > 0:
                    self.ms_to_buffer_bytes[ms_id] -= drop
                    self.ms_to_kpi.setdefault(ms_id, FlowKPI()).bytes_dropped += drop
            self.last_schedule_time_s = now
            return

        frame_bytes = int(total_capacity_bps * self.config.frame_duration_s / 8.0)
        if frame_bytes <= 0:
            self.last_schedule_time_s = now
            return

        # proportional fair: allocate by capacity weight
        for ms_id, capacity in capacities_bps.items():
            share = capacity / total_capacity_bps if total_capacity_bps > 0 else 0.0
            alloc = int(frame_bytes * share)
            if alloc <= 0:
                continue
            buf = self.ms_to_buffer_bytes.get(ms_id, 0)
            sent = min(buf, alloc)
            self.ms_to_buffer_bytes[ms_id] = max(0, buf - sent)
            kpi = self.ms_to_kpi.setdefault(ms_id, FlowKPI())
            kpi.bytes_sent += sent
            # rough latency approximation: time since last update
            last = self.ms_to_last_update_s.get(ms_id, now)
            kpi.latency_samples_ms.append((now - last) * 1000.0)
            self.ms_to_last_update_s[ms_id] = now

        self.last_schedule_time_s = now

    def metrics(self):
        return {ms_id: kpi.to_dict() for ms_id, kpi in self.ms_to_kpi.items()}

