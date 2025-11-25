"""
NS3 Protocol Adapter Module
Provides adaptation layer between VANET system and NS3 protocols
"""

import os
import sys
from typing import Dict, List, Optional, Tuple
import logging
from ns3_integration import NS3VANETSimulator

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('ns3_adapter')

class NS3ProtocolAdapter:
    """Adapter class to interface between VANET system and NS3 protocols"""
    
    def __init__(self, config: Dict):
        """Initialize the NS3 protocol adapter
        
        Args:
            config: Configuration dictionary containing simulation parameters
        """
        self.config = config
        self.simulator = NS3VANETSimulator(
            num_nodes=config.get('num_nodes', 10),
            packet_size=config.get('packet_size', 1000)
        )
        
    def configure_network(self, network_params: Dict) -> None:
        """Configure the network parameters
        
        Args:
            network_params: Dictionary containing network configuration
        """
        self.data_rate = network_params.get('data_rate', '1Mbps')
        self.distance = network_params.get('distance', 500.0)
        self.mobility_model = network_params.get('mobility_model', 'RandomWalk2d')
        
    def start_communication(self, source_id: int, target_id: int,
                          message: str) -> Tuple[bool, Dict]:
        """Start communication between nodes
        
        Args:
            source_id: ID of the source node
            target_id: ID of the target node
            message: Message to be transmitted
            
        Returns:
            Tuple of (success status, results dictionary)
        """
        try:
            # Configure simulation parameters
            sim_params = {
                'duration': self.config.get('simulation_duration', 10.0),
                'data_rate': self.data_rate,
                'distance': self.distance,
                'mobility_model': self.mobility_model
            }
            
            # Run simulation
            results = self.simulator.run_simulation(**sim_params)
            
            success = results['packet_delivery_ratio'] > 0
            
            return success, results
            
        except Exception as e:
            logger.error(f"Communication failed: {str(e)}")
            return False, {'error': str(e)}
            
    def monitor_network(self) -> Dict:
        """Monitor network status and performance
        
        Returns:
            Dictionary containing network metrics
        """
        try:
            metrics = {
                'active_nodes': self.simulator.num_nodes,
                'network_status': 'active',
                'channel_quality': 'good',  # This should be determined from NS3 metrics
                'packet_loss': 0.0  # This should be calculated from NS3 metrics
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Network monitoring failed: {str(e)}")
            return {'error': str(e)}
            
    def handle_node_failure(self, node_id: int) -> bool:
        """Handle node failure in the network
        
        Args:
            node_id: ID of the failed node
            
        Returns:
            Boolean indicating success of failure handling
        """
        try:
            # Implement node failure handling logic
            # This should be integrated with NS3's node management
            logger.info(f"Handling failure of node {node_id}")
            
            # Reconfigure network if needed
            return True
            
        except Exception as e:
            logger.error(f"Node failure handling failed: {str(e)}")
            return False
            
def main():
    """Main function for testing the NS3 protocol adapter"""
    try:
        # Test configuration
        config = {
            'num_nodes': 10,
            'packet_size': 1000,
            'simulation_duration': 10.0
        }
        
        # Create adapter instance
        adapter = NS3ProtocolAdapter(config)
        
        # Configure network
        network_params = {
            'data_rate': '2Mbps',
            'distance': 400.0,
            'mobility_model': 'RandomWalk2d'
        }
        adapter.configure_network(network_params)
        
        # Test communication
        success, results = adapter.start_communication(0, 1, "Test message")
        
        if success:
            print("\nCommunication successful!")
            print("Results:", results)
        else:
            print("\nCommunication failed!")
            print("Error:", results.get('error', 'Unknown error'))
            
    except Exception as e:
        logger.error(f"Error testing NS3 protocol adapter: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()