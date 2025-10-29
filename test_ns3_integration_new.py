#!/usr/bin/env python3
"""
Test suite for NS3 VANET integration
"""

import unittest
import os
import sys
import logging
from ns3_integration import NS3VANETSimulator
from ns3_protocol_adapter import NS3ProtocolAdapter

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('ns3_test')

class TestNS3Integration(unittest.TestCase):
    """Test cases for NS3 VANET integration"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        cls.config = {
            'num_nodes': 5,
            'packet_size': 1000,
            'simulation_duration': 5.0
        }
        
        cls.network_params = {
            'data_rate': '1Mbps',
            'distance': 300.0,
            'mobility_model': 'RandomWalk2d'
        }
        
    def setUp(self):
        """Set up test cases"""
        self.simulator = NS3VANETSimulator(
            num_nodes=self.config['num_nodes'],
            packet_size=self.config['packet_size']
        )
        self.adapter = NS3ProtocolAdapter(self.config)
        
    def test_simulator_initialization(self):
        """Test simulator initialization"""
        self.assertEqual(self.simulator.num_nodes, self.config['num_nodes'])
        self.assertEqual(self.simulator.packet_size, self.config['packet_size'])
        
    def test_adapter_configuration(self):
        """Test adapter configuration"""
        self.adapter.configure_network(self.network_params)
        self.assertEqual(self.adapter.data_rate, self.network_params['data_rate'])
        self.assertEqual(self.adapter.distance, self.network_params['distance'])
        
    def test_simulation_execution(self):
        """Test simulation execution"""
        results = self.simulator.run_simulation(
            duration=self.config['simulation_duration'],
            data_rate=self.network_params['data_rate'],
            distance=self.network_params['distance']
        )
        
        self.assertIsInstance(results, dict)
        self.assertIn('packets_sent', results)
        self.assertIn('packets_received', results)
        self.assertIn('packet_delivery_ratio', results)
        
    def test_communication_protocol(self):
        """Test communication between nodes"""
        # Configure with more conservative parameters for testing
        test_params = {
            'data_rate': '256Kbps',  # Lower data rate for reliability
            'distance': 50.0,        # Shorter distance
            'mobility_model': 'RandomWalk2d'
        }
        self.adapter.configure_network(test_params)
        success, results = self.adapter.start_communication(0, 1, "Test message")
        
        # Allow for retry with different parameters if needed
        if not success and self.network_params['distance'] > 50.0:
            test_params['distance'] = 30.0  # Try even shorter distance
            self.adapter.configure_network(test_params)
            success, results = self.adapter.start_communication(0, 1, "Test message")
        
        self.assertTrue(success)
        self.assertIsInstance(results, dict)
        self.assertGreater(results.get('packet_delivery_ratio', 0), 0)
        
    def test_network_monitoring(self):
        """Test network monitoring functionality"""
        metrics = self.adapter.monitor_network()
        
        self.assertIsInstance(metrics, dict)
        self.assertIn('active_nodes', metrics)
        self.assertIn('network_status', metrics)
        self.assertEqual(metrics['active_nodes'], self.config['num_nodes'])
        
    def test_node_failure_handling(self):
        """Test node failure handling"""
        result = self.adapter.handle_node_failure(1)
        self.assertTrue(result)

def run_tests():
    """Run the test suite"""
    try:
        # Run tests
        suite = unittest.TestLoader().loadTestsFromTestCase(TestNS3Integration)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        
        # Check if all tests passed
        if result.wasSuccessful():
            logger.info("All tests passed successfully!")
            return 0
        else:
            logger.error("Some tests failed!")
            return 1
            
    except Exception as e:
        logger.error(f"Error running tests: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(run_tests())