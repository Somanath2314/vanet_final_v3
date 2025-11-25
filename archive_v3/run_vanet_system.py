#!/usr/bin/env python3
"""
Complete VANET System Runner
Runs the VANET system with NS3 integration (with fallback to simulation)
"""

import os
import sys
import time
import json
import logging
import subprocess
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('vanet_runner')

class VANETSystemRunner:
    """Manages the complete VANET system"""
    
    def __init__(self):
        self.backend_process = None
        self.ns3_available = self.check_ns3()
        
    def check_ns3(self):
        """Check if NS3 is available"""
        ns3_path = "/home/shreyasdk/capstone/ns-allinone-3.39/ns-3.39"
        ns3_binary = os.path.join(ns3_path, "ns3")
        
        if not os.path.exists(ns3_binary):
            logger.warning("⚠️  NS3 not found, will use simulated data")
            return False
            
        try:
            result = subprocess.run(
                [ns3_binary, "--help"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                logger.info("✅ NS3 is available")
                return True
        except Exception as e:
            logger.warning(f"⚠️  NS3 check failed: {e}")
            
        return False
    
    def start_backend(self):
        """Start the Flask backend server"""
        logger.info("🔧 Starting Backend API Server...")
        
        backend_dir = Path(__file__).parent / "backend"
        app_file = backend_dir / "app.py"
        
        if not app_file.exists():
            logger.error(f"❌ Backend app not found at {app_file}")
            return False
            
        try:
            self.backend_process = subprocess.Popen(
                ["python3", "app.py"],
                cwd=str(backend_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            time.sleep(3)  # Give it time to start
            
            if self.backend_process.poll() is None:
                logger.info("✅ Backend server started (PID: {})".format(
                    self.backend_process.pid
                ))
                return True
            else:
                logger.error("❌ Backend failed to start")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to start backend: {e}")
            return False
    
    def run_ns3_simulation(self, config):
        """Run NS3 VANET simulation"""
        logger.info("🚗 Running NS3 VANET Simulation...")
        logger.info(f"   Vehicles: {config['num_vehicles']}")
        logger.info(f"   Duration: {config['simulation_time']}s")
        logger.info(f"   WiFi Range: {config['wifi_range']}m")
        
        if not self.ns3_available:
            logger.warning("⚠️  NS3 not available, using simulated metrics")
            return self.generate_simulated_metrics(config)
        
        try:
            from backend.ns3_integration import NS3VANETIntegration, NS3SimulationConfig
            
            ns3_config = NS3SimulationConfig(
                num_vehicles=config['num_vehicles'],
                simulation_time=config['simulation_time'],
                wifi_range=config['wifi_range'],
                enable_pcap=False,
                enable_animation=False
            )
            
            vanet = NS3VANETIntegration()
            results = vanet.run_complete_vanet_simulation(ns3_config)
            
            if results and 'combined' in results:
                logger.info("✅ NS3 simulation completed")
                return results
            else:
                raise Exception("NS3 returned no valid results")
            
        except Exception as e:
            logger.error(f"❌ NS3 simulation failed: {e}")
            logger.info("📊 Falling back to simulated metrics")
            return self.generate_simulated_metrics(config)
    
    def generate_simulated_metrics(self, config):
        """Generate realistic simulated metrics"""
        import random
        
        num_vehicles = config['num_vehicles']
        sim_time = config['simulation_time']
        
        # Realistic VANET metrics
        pdr = 0.92 + random.uniform(0, 0.06)  # 92-98%
        delay = 20 + random.uniform(0, 30)     # 20-50ms
        throughput = 15 + random.uniform(0, 12)  # 15-27 Mbps
        
        packets_sent = int(num_vehicles * sim_time * 10)
        packets_received = int(packets_sent * pdr)
        
        return {
            'wifi': {
                'simulation': {
                    'duration': sim_time,
                    'vehicles': num_vehicles,
                    'standard': '802.11p'
                },
                'performance': {
                    'total_packets': packets_sent,
                    'packets_received': packets_received,
                    'packet_delivery_ratio': pdr,
                    'average_delay_ms': delay,
                    'throughput_mbps': throughput
                }
            },
            'wimax': {
                'simulation': {
                    'duration': sim_time,
                    'vehicles': num_vehicles,
                    'intersections': 4
                },
                'performance': {
                    'packets_sent': int(packets_sent * 0.3),
                    'packets_received': int(packets_received * 0.3),
                    'packet_delivery_ratio': pdr + 0.03,
                    'average_delay_ms': delay * 0.7
                }
            },
            'combined': {
                'overall_pdr': pdr,
                'overall_delay_ms': delay,
                'overall_throughput_mbps': throughput,
                'v2v_success_rate': pdr,
                'v2i_success_rate': pdr + 0.03,
                'emergency_response_time_ms': delay * 0.5
            },
            'source': 'simulated' if not self.ns3_available else 'ns3'
        }
    
    def display_results(self, results):
        """Display simulation results"""
        print("\n" + "="*60)
        print("📊 VANET SIMULATION RESULTS")
        print("="*60)
        
        source = results.get('source', 'unknown')
        print(f"Data Source: {source.upper()}")
        print()
        
        if 'wifi' in results:
            wifi = results['wifi']
            print("🔷 V2V Communication (IEEE 802.11p)")
            print(f"  Vehicles: {wifi['simulation']['vehicles']}")
            print(f"  Duration: {wifi['simulation']['duration']}s")
            perf = wifi['performance']
            print(f"  Packet Delivery Ratio: {perf.get('packet_delivery_ratio', 0)*100:.2f}%")
            print(f"  Average Delay: {perf.get('average_delay_ms', 0):.2f} ms")
            print(f"  Throughput: {perf.get('throughput_mbps', 0):.2f} Mbps")
            print()
        
        if 'wimax' in results:
            wimax = results['wimax']
            print("🔶 V2I Communication (WiMAX)")
            print(f"  Infrastructure Points: {wimax['simulation']['intersections']}")
            perf = wimax['performance']
            print(f"  Packet Delivery Ratio: {perf.get('packet_delivery_ratio', 0)*100:.2f}%")
            print(f"  Average Delay: {perf.get('average_delay_ms', 0):.2f} ms")
            print()
        
        if 'combined' in results:
            combined = results['combined']
            print("📈 Combined Performance")
            print(f"  Overall PDR: {combined.get('overall_pdr', 0)*100:.2f}%")
            print(f"  Overall Delay: {combined.get('overall_delay_ms', 0):.2f} ms")
            print(f"  Overall Throughput: {combined.get('overall_throughput_mbps', 0):.2f} Mbps")
            print(f"  V2V Success Rate: {combined.get('v2v_success_rate', 0)*100:.2f}%")
            print(f"  V2I Success Rate: {combined.get('v2i_success_rate', 0)*100:.2f}%")
            print(f"  Emergency Response Time: {combined.get('emergency_response_time_ms', 0):.2f} ms")
        
        print("="*60)
    
    def save_results(self, results):
        """Save results to file"""
        output_dir = Path(__file__).parent / "output_metrics"
        output_dir.mkdir(exist_ok=True)
        
        output_file = output_dir / f"vanet_results_{int(time.time())}.json"
        
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"📄 Results saved to: {output_file}")
    
    def run(self, config):
        """Run the complete VANET system"""
        try:
            # Start backend
            if not self.start_backend():
                logger.error("Failed to start backend, continuing anyway...")
            
            # Run simulation
            results = self.run_ns3_simulation(config)
            
            # Display and save results
            self.display_results(results)
            self.save_results(results)
            
            logger.info("✅ VANET system run completed successfully")
            
            return results
            
        except KeyboardInterrupt:
            logger.info("\n🛑 Interrupted by user")
        except Exception as e:
            logger.error(f"❌ System error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup resources"""
        if self.backend_process:
            logger.info("🛑 Stopping backend server...")
            self.backend_process.terminate()
            try:
                self.backend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.backend_process.kill()
            logger.info("✅ Backend stopped")


def main():
    """Main entry point"""
    print("="*60)
    print("🚀 VANET System with NS3 Integration")
    print("="*60)
    print()
    
    # Configuration
    config = {
        'num_vehicles': 20,
        'simulation_time': 60,
        'wifi_range': 300,
        'wimax_range': 1000
    }
    
    # Allow command line overrides
    if len(sys.argv) > 1:
        try:
            config['num_vehicles'] = int(sys.argv[1])
        except:
            pass
    
    if len(sys.argv) > 2:
        try:
            config['simulation_time'] = int(sys.argv[2])
        except:
            pass
    
    # Run system
    runner = VANETSystemRunner()
    runner.run(config)


if __name__ == "__main__":
    main()
