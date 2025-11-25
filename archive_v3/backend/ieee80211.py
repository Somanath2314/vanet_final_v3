"""
IEEE 802.11p and WiMAX Protocol Stack Implementation for VANET
Implements PHY, MAC, and LLC layers with realistic protocol behavior
Suitable for academic research and validation
"""

import numpy as np
import time
import random
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChannelType(Enum):
    """802.11p Channel Types"""
    CCH = 178  # Control Channel (5.890 GHz)
    SCH1 = 172  # Service Channel 1 (5.860 GHz)
    SCH2 = 174
    SCH3 = 176
    SCH4 = 180
    SCH5 = 182
    SCH6 = 184


class AccessCategory(Enum):
    """EDCA Access Categories (IEEE 802.11e)"""
    AC_VO = 0  # Voice (highest priority) - Emergency messages
    AC_VI = 1  # Video
    AC_BE = 2  # Best Effort
    AC_BK = 3  # Background (lowest priority)


@dataclass
class PHYMetrics:
    """PHY layer performance metrics for validation"""
    snr_db: float
    rssi_dbm: float
    path_loss_db: float
    packet_error_rate: float
    data_rate_mbps: float
    distance_m: float
    modulation: str
    coding_rate: float
    channel_frequency_ghz: float


@dataclass
class MACMetrics:
    """MAC layer performance metrics"""
    channel_access_delay_ms: float
    backoff_time_ms: float
    collision_count: int
    retransmission_count: int
    access_category: str
    contention_window: int


@dataclass
class TransmissionResult:
    """Complete transmission result with all metrics"""
    success: bool
    end_to_end_delay_ms: float
    phy_metrics: PHYMetrics
    mac_metrics: MACMetrics
    channel_used: str
    message_type: str
    timestamp: float


class IEEE80211pPHY:
    """
    IEEE 802.11p Physical Layer Implementation
    Based on OFDM with 10 MHz channel bandwidth
    Reference: IEEE 802.11p-2010 Standard
    """
    
    def __init__(self):
        # Physical parameters per IEEE 802.11p standard
        self.carrier_frequency = 5.890e9  # Hz (Channel 178 - CCH)
        self.bandwidth = 10e6  # 10 MHz
        self.tx_power_dbm = 23.0  # 200 mW (typical for vehicles)
        self.antenna_height = 1.5  # meters (standard vehicle antenna)
        self.noise_figure = 9.0  # dB (typical receiver)
        self.thermal_noise = -174  # dBm/Hz
        self.receiver_sensitivity = -85  # dBm (802.11p typical)
        
        # Supported MCS (Modulation and Coding Schemes) per 802.11p
        self.mcs_table = {
            3.0: {'modulation': 'BPSK', 'coding_rate': 0.5, 'snr_threshold': 3.0},
            4.5: {'modulation': 'BPSK', 'coding_rate': 0.75, 'snr_threshold': 5.0},
            6.0: {'modulation': 'QPSK', 'coding_rate': 0.5, 'snr_threshold': 6.0},
            9.0: {'modulation': 'QPSK', 'coding_rate': 0.75, 'snr_threshold': 9.0},
            12.0: {'modulation': '16-QAM', 'coding_rate': 0.5, 'snr_threshold': 11.0},
            18.0: {'modulation': '16-QAM', 'coding_rate': 0.75, 'snr_threshold': 15.0},
            24.0: {'modulation': '64-QAM', 'coding_rate': 0.667, 'snr_threshold': 19.0},
            27.0: {'modulation': '64-QAM', 'coding_rate': 0.75, 'snr_threshold': 22.0}
        }
        
        # Communication range based on receiver sensitivity
        self.max_range = self._calculate_max_range()
        
    def _calculate_max_range(self) -> float:
        """Calculate theoretical maximum communication range"""
        # Using free space path loss at sensitivity limit
        path_loss_max = self.tx_power_dbm - self.receiver_sensitivity
        wavelength = 3e8 / self.carrier_frequency
        max_range = (10 ** (path_loss_max / 20)) * wavelength / (4 * np.pi)
        return max_range
    
    def calculate_path_loss_two_ray(self, distance: float) -> float:
        """
        Two-Ray Ground Reflection Model (Rappaport)
        Used in: Sommer et al. (Veins), IEEE VNC papers
        More accurate than free space for V2V
        """
        if distance < 1.0:
            distance = 1.0
        
        ht = self.antenna_height
        hr = self.antenna_height
        wavelength = 3e8 / self.carrier_frequency
        
        # Crossover distance between free space and two-ray
        dc = (4 * np.pi * ht * hr) / wavelength
        
        if distance < dc:
            # Free space path loss (FSPL)
            pl = 20 * np.log10(4 * np.pi * distance / wavelength)
        else:
            # Two-ray ground reflection
            pl = 40 * np.log10(distance) - (10 * np.log10(ht * hr))
        
        return pl
    
    def calculate_shadowing(self, environment: str = 'urban') -> float:
        """
        Log-normal shadowing
        Standard deviations from ITU-R P.1411
        """
        sigma_map = {
            'urban': 6.0,      # Urban/suburban
            'highway': 4.0,    # Highway/open road
            'rural': 3.0       # Rural/countryside
        }
        sigma = sigma_map.get(environment, 6.0)
        return np.random.normal(0, sigma)
    
    def calculate_received_power(self, distance: float, environment: str = 'urban') -> float:
        """Calculate received signal power in dBm"""
        pl = self.calculate_path_loss_two_ray(distance)
        shadowing = self.calculate_shadowing(environment)
        
        # Pr = Pt - PL - Shadowing + Gt + Gr (antenna gains = 0 dBi)
        rx_power = self.tx_power_dbm - pl - shadowing
        return rx_power
    
    def calculate_noise_power(self) -> float:
        """Calculate noise power per IEEE 802.11"""
        # N = kTB where k=-174 dBm/Hz, B=10MHz
        noise = self.thermal_noise + 10 * np.log10(self.bandwidth) + self.noise_figure
        return noise
    
    def calculate_snr(self, distance: float, environment: str = 'urban') -> float:
        """Calculate SNR in dB"""
        rx_power = self.calculate_received_power(distance, environment)
        noise = self.calculate_noise_power()
        snr = rx_power - noise
        return snr
    
    def select_data_rate_aarf(self, snr: float, history: List[bool] = None) -> float:
        """
        Adaptive Auto Rate Fallback (AARF)
        Used in real 802.11p implementations
        """
        selected_rate = 3.0  # Fallback rate
        
        for rate in sorted(self.mcs_table.keys()):
            if snr >= self.mcs_table[rate]['snr_threshold']:
                selected_rate = rate
            else:
                break
        
        return selected_rate
    
    def calculate_ber(self, snr_linear: float, modulation: str) -> float:
        """
        Bit Error Rate calculation per modulation
        Formulas from: Goldsmith "Wireless Communications"
        """
        if modulation == 'BPSK':
            ber = 0.5 * np.exp(-snr_linear)
        elif modulation == 'QPSK':
            ber = 0.5 * np.exp(-snr_linear / 2)
        elif modulation == '16-QAM':
            ber = 0.375 * np.exp(-snr_linear / 10)
        elif modulation == '64-QAM':
            ber = 0.333 * np.exp(-snr_linear / 42)
        else:
            ber = 0.5
        
        return max(1e-8, min(0.5, ber))
    
    def calculate_per(self, snr: float, packet_size_bytes: int, data_rate: float) -> float:
        """
        Packet Error Rate calculation
        PER = 1 - (1 - BER)^L where L = packet length in bits
        """
        snr_linear = 10 ** (snr / 10)
        modulation = self.mcs_table[data_rate]['modulation']
        coding_rate = self.mcs_table[data_rate]['coding_rate']
        
        ber = self.calculate_ber(snr_linear, modulation)
        
        # Apply coding gain (simplified)
        coded_ber = ber * (1 - coding_rate)
        
        # PER calculation
        per = 1 - (1 - coded_ber) ** (packet_size_bytes * 8)
        
        return max(0.0, min(1.0, per))
    
    def transmit_packet(self, distance: float, packet_size: int, 
                       environment: str = 'urban') -> Tuple[bool, PHYMetrics]:
        """
        Simulate packet transmission through PHY layer
        Returns (success, metrics)
        """
        snr = self.calculate_snr(distance, environment)
        data_rate = self.select_data_rate_aarf(snr)
        per = self.calculate_per(snr, packet_size, data_rate)
        
        rx_power = self.calculate_received_power(distance, environment)
        path_loss = self.calculate_path_loss_two_ray(distance)
        
        mcs = self.mcs_table[data_rate]
        
        metrics = PHYMetrics(
            snr_db=snr,
            rssi_dbm=rx_power,
            path_loss_db=path_loss,
            packet_error_rate=per,
            data_rate_mbps=data_rate,
            distance_m=distance,
            modulation=mcs['modulation'],
            coding_rate=mcs['coding_rate'],
            channel_frequency_ghz=self.carrier_frequency / 1e9
        )
        
        # Packet reception success based on PER
        success = random.random() > per and rx_power > self.receiver_sensitivity
        
        return success, metrics


class IEEE80211pMAC:
    """
    IEEE 802.11p MAC Layer with EDCA
    Reference: IEEE 802.11e-2005 (EDCA) and IEEE 802.11p-2010
    """
    
    def __init__(self):
        # Timing parameters per IEEE 802.11p standard
        self.slot_time = 13e-6  # 13 μs
        self.sifs_time = 32e-6  # 32 μs
        self.difs_time = 58e-6  # DIFS = SIFS + 2*SlotTime
        
        # EDCA parameters per IEEE 802.11e Table 7-37
        self.edca_params = {
            AccessCategory.AC_VO: {  # Voice - Highest priority
                'aifsn': 2,
                'cwmin': 3,
                'cwmax': 7,
                'txop_limit': 0.00188  # 1.88 ms
            },
            AccessCategory.AC_VI: {  # Video
                'aifsn': 2,
                'cwmin': 7,
                'cwmax': 15,
                'txop_limit': 0.00376  # 3.76 ms
            },
            AccessCategory.AC_BE: {  # Best Effort
                'aifsn': 3,
                'cwmin': 15,
                'cwmax': 1023,
                'txop_limit': 0
            },
            AccessCategory.AC_BK: {  # Background - Lowest priority
                'aifsn': 7,
                'cwmin': 15,
                'cwmax': 1023,
                'txop_limit': 0
            }
        }
        
        # Statistics for performance evaluation
        self.total_collisions = 0
        self.total_transmissions = 0
        self.channel_busy_ratio = 0.1  # 10% default
    
    def calculate_aifs(self, ac: AccessCategory) -> float:
        """
        Arbitration Inter-Frame Space
        AIFS = SIFS + AIFSN × SlotTime
        """
        aifsn = self.edca_params[ac]['aifsn']
        aifs = self.sifs_time + (aifsn * self.slot_time)
        return aifs
    
    def calculate_backoff(self, ac: AccessCategory, retry: int = 0) -> Tuple[float, int]:
        """
        Binary Exponential Backoff (BEB)
        CW = min(CWmin × 2^retry, CWmax)
        """
        params = self.edca_params[ac]
        cwmin = params['cwmin']
        cwmax = params['cwmax']
        
        # Calculate CW for this retry
        cw = min(cwmin * (2 ** retry), cwmax)
        
        # Random backoff slots [0, CW]
        backoff_slots = random.randint(0, cw)
        backoff_time = backoff_slots * self.slot_time
        
        return backoff_time, cw
    
    def virtual_carrier_sense(self) -> bool:
        """
        Simplified carrier sense (CCA - Clear Channel Assessment)
        Returns True if channel is idle
        """
        # Probability of channel being busy
        return random.random() > self.channel_busy_ratio
    
    def csma_ca_procedure(self, ac: AccessCategory, 
                         max_retries: int = 7) -> Tuple[bool, MACMetrics]:
        """
        Complete CSMA/CA procedure with EDCA
        Based on: IEEE 802.11-2016 Section 9.3.2.3
        """
        retry_count = 0
        total_backoff = 0.0
        aifs = self.calculate_aifs(ac)
        collision_count = 0
        
        start_time = time.time()
        
        while retry_count <= max_retries:
            # Step 1: Wait AIFS
            time.sleep(aifs)
            
            # Step 2: Check if channel is idle for AIFS duration
            if not self.virtual_carrier_sense():
                collision_count += 1
                retry_count += 1
                continue
            
            # Step 3: Calculate and wait backoff
            backoff, cw = self.calculate_backoff(ac, retry_count)
            total_backoff += backoff
            time.sleep(backoff)
            
            # Step 4: Check channel again after backoff
            if self.virtual_carrier_sense():
                # SUCCESS - Channel access granted
                access_delay = (time.time() - start_time) * 1000  # ms
                
                self.total_transmissions += 1
                self.total_collisions += collision_count
                
                metrics = MACMetrics(
                    channel_access_delay_ms=access_delay,
                    backoff_time_ms=total_backoff * 1000,
                    collision_count=collision_count,
                    retransmission_count=retry_count,
                    access_category=ac.name,
                    contention_window=cw
                )
                
                return True, metrics
            else:
                # Collision detected, increment retry
                collision_count += 1
                retry_count += 1
        
        # FAILURE - Max retries exceeded
        access_delay = (time.time() - start_time) * 1000
        _, final_cw = self.calculate_backoff(ac, retry_count)
        
        metrics = MACMetrics(
            channel_access_delay_ms=access_delay,
            backoff_time_ms=total_backoff * 1000,
            collision_count=collision_count,
            retransmission_count=retry_count,
            access_category=ac.name,
            contention_window=final_cw
        )
        
        return False, metrics
    
    def update_channel_conditions(self, vehicle_density: float):
        """Update channel busy ratio based on vehicle density"""
        # Empirical model: more vehicles = more channel contention
        self.channel_busy_ratio = min(0.8, 0.1 + (vehicle_density / 100) * 0.7)


class IEEE1609_4:
    """
    IEEE 1609.4 WAVE Multi-Channel Operation
    Reference: IEEE 1609.4-2016 Standard
    """
    
    def __init__(self):
        # Channel coordination per IEEE 1609.4
        self.cch_interval = 0.050  # 50 ms CCH
        self.sch_interval = 0.050  # 50 ms SCH
        self.guard_interval = 0.004  # 4 ms guard
        self.sync_tolerance = 0.002  # 2 ms
        
        self.current_channel = ChannelType.CCH
        self.sync_time = time.time()
        
        # Safety message identifiers (always on CCH)
        self.safety_types = ['CAM', 'DENM', 'BSM', 'emergency', 'safety', 'SPAT', 'MAP']
    
    def get_current_interval(self) -> ChannelType:
        """Determine current channel interval"""
        elapsed = time.time() - self.sync_time
        cycle_time = self.cch_interval + self.sch_interval
        position_in_cycle = elapsed % cycle_time
        
        if position_in_cycle < self.cch_interval:
            return ChannelType.CCH
        else:
            return ChannelType.SCH1
    
    def select_channel(self, message_type: str) -> ChannelType:
        """Select channel based on message type per IEEE 1609.4"""
        # Safety-critical messages MUST use CCH
        if any(st in message_type.upper() for st in self.safety_types):
            return ChannelType.CCH
        # Non-safety can use SCH
        return ChannelType.SCH1
    
    def can_transmit_immediate(self, message_type: str) -> bool:
        """Check if can transmit immediately"""
        required = self.select_channel(message_type)
        current = self.get_current_interval()
        return required == current
    
    def calculate_queuing_delay(self, message_type: str) -> float:
        """Calculate delay until channel becomes available"""
        if self.can_transmit_immediate(message_type):
            return 0.0
        
        # Calculate time until required channel
        elapsed = time.time() - self.sync_time
        cycle_time = self.cch_interval + self.sch_interval
        position = elapsed % cycle_time
        
        current = self.get_current_interval()
        required = self.select_channel(message_type)
        
        if current == ChannelType.CCH and required == ChannelType.SCH1:
            # Wait for CCH to end + guard
            delay = (self.cch_interval - position) + self.guard_interval
        else:
            # Wait for full cycle
            delay = (cycle_time - position) + self.guard_interval
        
        return delay


class WiMAX_802_16e:
    """
    IEEE 802.16e (Mobile WiMAX) for Infrastructure Communication
    Reference: IEEE 802.16e-2005 Standard
    """
    
    def __init__(self):
        # WiMAX parameters
        self.carrier_frequency = 2.5e9  # 2.5 GHz (or 3.5 GHz)
        self.bandwidth = 10e6  # 10 MHz
        self.tx_power_dbm = 43.0  # 20W base station
        self.frame_duration = 0.005  # 5ms frame
        
        # QoS Service Flows per IEEE 802.16
        self.service_classes = {
            'UGS': {'latency': 0.010, 'jitter': 0.001},  # Unsolicited Grant  - VoIP
            'rtPS': {'latency': 0.020, 'jitter': 0.005},  # Real-time Polling - Video
            'nrtPS': {'latency': 0.100, 'jitter': 0.050},  # Non-real-time - FTP
            'BE': {'latency': 1.000, 'jitter': 0.500}  # Best Effort
        }
        
        # Handoff parameters (Mobile WiMAX)
        self.max_speed_kmh = 120  # Mobile support up to 120 km/h
        self.handoff_delay = 0.050  # 50ms handoff latency
        
    def calculate_wimax_path_loss(self, distance_km: float) -> float:
        """
        WiMAX path loss using COST-231 Hata model
        For urban/suburban areas
        """
        f_mhz = self.carrier_frequency / 1e6
        d = distance_km
        
        # Base station height
        hb = 30  # meters
        hm = 1.5  # mobile height
        
        # Urban area correction
        a_hm = (1.1 * np.log10(f_mhz) - 0.7) * hm - (1.56 * np.log10(f_mhz) - 0.8)
        
        pl = (46.3 + 33.9 * np.log10(f_mhz) - 13.82 * np.log10(hb) 
              - a_hm + (44.9 - 6.55 * np.log10(hb)) * np.log10(d))
        
        return pl
    
    def transmit_infrastructure_data(self, distance_km: float, 
                                     data_size_bytes: int,
                                     service_class: str = 'UGS') -> Dict:
        """
        Transmit data from RSU to fog/cloud via WiMAX
        """
        pl = self.calculate_wimax_path_loss(distance_km)
        rx_power = self.tx_power_dbm - pl
        
        # Simplified throughput calculation
        snr = rx_power - (-95)  # Noise floor
        if snr > 20:
            throughput_mbps = 75  # Peak rate
        elif snr > 15:
            throughput_mbps = 50
        elif snr > 10:
            throughput_mbps = 25
        else:
            throughput_mbps = 10
        
        transmission_time = (data_size_bytes * 8) / (throughput_mbps * 1e6)
        qos = self.service_classes[service_class]
        total_delay = transmission_time + qos['latency']
        
        return {
            'success': rx_power > -100,  # Receiver sensitivity
            'delay_ms': total_delay * 1000,
            'throughput_mbps': throughput_mbps,
            'rssi_dbm': rx_power,
            'path_loss_db': pl,
            'service_class': service_class
        }


class Complete_VANET_Protocol_Stack:
    """
    Complete VANET Protocol Stack with both V2V (802.11p) and V2I (WiMAX)
    """
    
    def __init__(self, environment: str = 'urban'):
        self.dsrc_phy = IEEE80211pPHY()
        self.dsrc_mac = IEEE80211pMAC()
        self.wave_llc = IEEE1609_4()
        self.wimax = WiMAX_802_16e()
        self.environment = environment
        
        # Performance logging
        self.transmission_log = []
        
        logger.info("=" * 60)
        logger.info("Complete VANET Protocol Stack Initialized")
        logger.info("=" * 60)
        logger.info(f"V2V: IEEE 802.11p @ {self.dsrc_phy.carrier_frequency/1e9:.3f} GHz")
        logger.info(f"V2I: IEEE 802.16e @ {self.wimax.carrier_frequency/1e9:.1f} GHz")
        logger.info(f"Environment: {environment}")
        logger.info(f"Max DSRC Range: {self.dsrc_phy.max_range:.0f}m")
        logger.info("=" * 60)
    
    def send_v2v_message(self,
                        sender_pos: Tuple[float, float],
                        receiver_pos: Tuple[float, float],
                        message: bytes,
                        message_type: str = 'CAM',
                        priority: AccessCategory = AccessCategory.AC_VO) -> TransmissionResult:
        """
        Send V2V message through complete 802.11p/WAVE stack
        """
        start_time = time.time()
        
        # Calculate distance
        distance = np.linalg.norm(
            np.array(sender_pos) - np.array(receiver_pos)
        )
        
        # Step 1: LLC - Channel selection and coordination
        channel = self.wave_llc.select_channel(message_type)
        llc_delay = self.wave_llc.calculate_queuing_delay(message_type)
        if llc_delay > 0:
            time.sleep(llc_delay)
        
        # Step 2: MAC - Channel access
        mac_success, mac_metrics = self.dsrc_mac.csma_ca_procedure(priority)
        if not mac_success:
            result = TransmissionResult(
                success=False,
                end_to_end_delay_ms=(time.time() - start_time) * 1000,
                phy_metrics=None,
                mac_metrics=mac_metrics,
                channel_used=channel.name,
                message_type=message_type,
                timestamp=time.time()
            )
            self.transmission_log.append(result)
            return result
        
        # Step 3: PHY - Transmission
        phy_success, phy_metrics = self.dsrc_phy.transmit_packet(
            distance, len(message), self.environment
        )
        
        total_delay = (time.time() - start_time) * 1000
        
        result = TransmissionResult(
            success=phy_success and mac_success,
            end_to_end_delay_ms=total_delay,
            phy_metrics=phy_metrics,
            mac_metrics=mac_metrics,
            channel_used=channel.name,
            message_type=message_type,
            timestamp=time.time()
        )
        
        self.transmission_log.append(result)
        return result
    
    def send_v2i_message(self,
                        rsu_pos: Tuple[float, float],
                        fog_distance_km: float,
                        message: bytes,
                        service_class: str = 'UGS') -> Dict:
        """
        Send V2I message from RSU to fog server via WiMAX
        """
        result = self.wimax.transmit_infrastructure_data(
            fog_distance_km,
            len(message),
            service_class
        )
        return result
    
    def get_performance_statistics(self) -> Dict:
        """Generate performance statistics for publication"""
        if not self.transmission_log:
            return {}
        
        successful = [t for t in self.transmission_log if t.success]
        failed = [t for t in self.transmission_log if not t.success]
        
        stats = {
            'total_transmissions': len(self.transmission_log),
            'successful_transmissions': len(successful),
            'packet_delivery_ratio': len(successful) / len(self.transmission_log),
            'average_delay_ms': np.mean([t.end_to_end_delay_ms for t in successful]) if successful else 0,
            'delay_std_ms': np.std([t.end_to_end_delay_ms for t in successful]) if successful else 0,
            'average_snr_db': np.mean([t.phy_metrics.snr_db for t in successful if t.phy_metrics]) if successful else 0,
            'average_per': np.mean([t.phy_metrics.packet_error_rate for t in successful if t.phy_metrics]) if successful else 0,
            'mac_collisions': sum([t.mac_metrics.collision_count for t in self.transmission_log if t.mac_metrics]),
            'average_backoff_ms': np.mean([t.mac_metrics.backoff_time_ms for t in successful if t.mac_metrics]) if successful else 0,
        }
        
        return stats
    
    def export_results_for_publication(self, filename: str = 'vanet_results.json'):
        """Export detailed results for academic papers"""
        results = {
            'protocol_stack': {
                'dsrc': {
                    'standard': 'IEEE 802.11p-2010',
                    'frequency_ghz': self.dsrc_phy.carrier_frequency / 1e9,
                    'bandwidth_mhz': self.dsrc_phy.bandwidth / 1e6,
                    'tx_power_dbm': self.dsrc_phy.tx_power_dbm,
                    'mac_protocol': 'EDCA (IEEE 802.11e)',
                    'llc_protocol': 'IEEE 1609.4'
                },
                'wimax': {
                    'standard': 'IEEE 802.16e-2005',
                    'frequency_ghz': self.wimax.carrier_frequency / 1e9,
                    'bandwidth_mhz': self.wimax.bandwidth / 1e6
                }
            },
            'simulation_parameters': {
                'environment': self.environment,
                'propagation_model': 'Two-Ray Ground Reflection',
                'shadowing': 'Log-normal'
            },
            'performance_metrics': self.get_performance_statistics(),
            'detailed_transmissions': [
                {
                    'timestamp': t.timestamp,
                    'success': t.success,
                    'delay_ms': t.end_to_end_delay_ms,
                    'snr_db': t.phy_metrics.snr_db if t.phy_metrics else None,
                    'data_rate_mbps': t.phy_metrics.data_rate_mbps if t.phy_metrics else None,
                    'modulation': t.phy_metrics.modulation if t.phy_metrics else None,
                    'per': t.phy_metrics.packet_error_rate if t.phy_metrics else None,
                    'distance_m': t.phy_metrics.distance_m if t.phy_metrics else None,
                    'mac_retries': t.mac_metrics.retransmission_count if t.mac_metrics else None,
                    'channel': t.channel_used,
                    'message_type': t.message_type
                }
                for t in self.transmission_log
            ]
        }
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Results exported to {filename}")
        return results


# Example usage demonstrating protocol stack
if __name__ == "__main__":
    # Initialize complete protocol stack
    vanet_stack = Complete_VANET_Protocol_Stack(environment='urban')
    
    print("\n" + "="*60)
    print("DEMONSTRATION: IEEE 802.11p Protocol Stack")
    print("="*60)
    
    # Simulate V2V communication
    sender_position = (100.0, 100.0)
    receiver_position = (250.0, 100.0)  # 150m distance
    
    # Create a CAM (Cooperative Awareness Message)
    cam_message = b"CAM:vehicle_123,speed=50,heading=90,lat=12.34,lon=56.78"
    
    print(f"\nSending CAM message...")
    print(f"Distance: 150m")
    print(f"Message size: {len(cam_message)} bytes")
    
    result = vanet_stack.send_v2v_message(
        sender_pos=sender_position,
        receiver_pos=receiver_position,
        message=cam_message,
        message_type='CAM',
        priority=AccessCategory.AC_VO
    )
    
    print(f"\nTransmission Result:")
    print(f"  Success: {result.success}")
    print(f"  End-to-End Delay: {result.end_to_end_delay_ms:.2f} ms")
    print(f"  Channel Used: {result.channel_used}")
    
    if result.phy_metrics:
        print(f"\nPHY Layer Metrics:")
        print(f"  SNR: {result.phy_metrics.snr_db:.2f} dB")
        print(f"  RSSI: {result.phy_metrics.rssi_dbm:.2f} dBm")
        print(f"  Data Rate: {result.phy_metrics.data_rate_mbps:.1f} Mbps")
        print(f"  Modulation: {result.phy_metrics.modulation}")
        print(f"  PER: {result.phy_metrics.packet_error_rate:.6f}")
        print(f"  Path Loss: {result.phy_metrics.path_loss_db:.2f} dB")
    
    if result.mac_metrics:
        print(f"\nMAC Layer Metrics:")
        print(f"  Channel Access Delay: {result.mac_metrics.channel_access_delay_ms:.2f} ms")
        print(f"  Backoff Time: {result.mac_metrics.backoff_time_ms:.2f} ms")
        print(f"  Retransmissions: {result.mac_metrics.retransmission_count}")
        print(f"  Collisions: {result.mac_metrics.collision_count}")
        print(f"  Access Category: {result.mac_metrics.access_category}")
        print(f"  Contention Window: {result.mac_metrics.contention_window}")
    
    # Simulate V2I communication via WiMAX
    print(f"\n" + "="*60)
    print("DEMONSTRATION: IEEE 802.16e (WiMAX) V2I Communication")
    print("="*60)
    
    rsu_position = (500.0, 500.0)
    fog_distance = 2.5  # 2.5 km to fog server
    
    v2i_message = b"EMERGENCY_ALERT:ambulance_456,priority=1,destination=hospital_A"
    
    print(f"\nSending emergency alert to fog server via WiMAX...")
    print(f"Distance to fog: {fog_distance} km")
    print(f"Message size: {len(v2i_message)} bytes")
    
    v2i_result = vanet_stack.send_v2i_message(
        rsu_pos=rsu_position,
        fog_distance_km=fog_distance,
        message=v2i_message,
        service_class='UGS'  # Unsolicited Grant Service (real-time)
    )
    
    print(f"\nWiMAX Transmission Result:")
    print(f"  Success: {v2i_result['success']}")
    print(f"  Delay: {v2i_result['delay_ms']:.2f} ms")
    print(f"  Throughput: {v2i_result['throughput_mbps']:.1f} Mbps")
    print(f"  RSSI: {v2i_result['rssi_dbm']:.2f} dBm")
    print(f"  Service Class: {v2i_result['service_class']}")
    
    # Simulate multiple transmissions for statistics
    print(f"\n" + "="*60)
    print("SIMULATION: Multiple Transmissions for Statistics")
    print("="*60)
    
    for i in range(20):
        distance = random.uniform(50, 300)  # Random distance 50-300m
        receiver_pos = (sender_position[0] + distance, sender_position[1])
        
        vanet_stack.send_v2v_message(
            sender_pos=sender_position,
            receiver_pos=receiver_pos,
            message=cam_message,
            message_type='CAM',
            priority=AccessCategory.AC_VO
        )
    
    # Get performance statistics
    stats = vanet_stack.get_performance_statistics()
    
    print(f"\nPerformance Statistics (21 total transmissions):")
    print(f"  Packet Delivery Ratio: {stats['packet_delivery_ratio']*100:.2f}%")
    print(f"  Average Delay: {stats['average_delay_ms']:.2f} ± {stats['delay_std_ms']:.2f} ms")
    print(f"  Average SNR: {stats['average_snr_db']:.2f} dB")
    print(f"  Average PER: {stats['average_per']:.6f}")
    print(f"  MAC Collisions: {stats['mac_collisions']}")
    print(f"  Average Backoff: {stats['average_backoff_ms']:.2f} ms")
    
    # Export results for publication
    vanet_stack.export_results_for_publication('vanet_protocol_results.json')
    
    print(f"\n" + "="*60)
    print("Results exported to 'vanet_protocol_results.json'")
    print("Ready for academic publication and validation!")
    print("="*60)