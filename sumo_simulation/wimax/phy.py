import math
import random
from dataclasses import dataclass
from .config import WiMAXConfig


@dataclass
class PhyLinkState:
    distance_m: float
    snr_db: float
    capacity_bps: float


class WiMAXPhy:
    def __init__(self, config: WiMAXConfig):
        self.config = config

    def _dbm_to_watts(self, dbm: float) -> float:
        return 10 ** ((dbm - 30) / 10)

    def _watts_to_db(self, w: float) -> float:
        return 10 * math.log10(max(w, 1e-15))

    def _thermal_noise_watts(self, bandwidth_hz: float) -> float:
        k = 1.38064852e-23
        T = 290.0
        return k * T * bandwidth_hz

    def _shadowing_db(self) -> float:
        return random.gauss(0.0, self.config.shadowing_std_db)

    def compute_snr_db(self, distance_m: float) -> float:
        if distance_m <= 1.0:
            distance_m = 1.0

        tx_w = self._dbm_to_watts(self.config.tx_power_dbm)
        # Simplified pathloss model: PL ~ d^{-n}
        pathloss_linear = distance_m ** (-self.config.pathloss_exponent)
        rx_w_nominal = tx_w * pathloss_linear

        # Apply log-normal shadowing
        rx_db = self._watts_to_db(rx_w_nominal) + self._shadowing_db()
        rx_w = 10 ** (rx_db / 10)

        noise_w = self._thermal_noise_watts(self.config.system_bandwidth_hz)
        noise_db = self._watts_to_db(noise_w) + self.config.noise_figure_db
        noise_w_eff = 10 ** (noise_db / 10)

        snr_linear = max(rx_w / max(noise_w_eff, 1e-15), 1e-6)
        snr_db = 10 * math.log10(snr_linear)
        return max(self.config.min_snr_db, min(snr_db, self.config.max_snr_db))

    def estimate_capacity_bps(self, snr_db: float) -> float:
        # Map SNR to spectral efficiency; use a simple linear ramp around 10 dB
        eff_at_10 = self.config.spectral_efficiency_bps_per_hz_at_snr_10db
        eff = max(0.0, (snr_db + 5.0) / (10.0) * eff_at_10)
        return eff * self.config.system_bandwidth_hz

    def evaluate_link(self, distance_m: float) -> PhyLinkState:
        snr_db = self.compute_snr_db(distance_m)
        capacity_bps = self.estimate_capacity_bps(snr_db)
        return PhyLinkState(distance_m=distance_m, snr_db=snr_db, capacity_bps=capacity_bps)

