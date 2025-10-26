from dataclasses import dataclass


@dataclass
class WiMAXConfig:
    # PHY
    system_bandwidth_hz: float = 10e6
    carrier_frequency_hz: float = 3.5e9
    noise_figure_db: float = 7.0
    tx_power_dbm: float = 30.0
    pathloss_exponent: float = 3.2
    shadowing_std_db: float = 6.0

    # OFDMA
    spectral_efficiency_bps_per_hz_at_snr_10db: float = 3.0
    min_snr_db: float = -5.0
    max_snr_db: float = 30.0

    # MAC
    frame_duration_s: float = 0.005  # 5 ms
    scheduling_granularity_s: float = 0.02  # 20 ms
    target_reliability: float = 0.99

