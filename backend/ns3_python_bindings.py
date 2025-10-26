"""
NS3 Python Bindings for VANET Integration
Provides Python interface to NS3 VANET simulations
"""

import subprocess
import os
import sys
import json
import time
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
import logging

# Add NS3 Python bindings path
NS3_PATH = "/home/shreyasdk/capstone/ns-allinone-3.39/ns-3.39"
sys.path.insert(0, os.path.join(NS3_PATH, "build", "bindings", "python"))

@dataclass
class VANETCommunicationEvent:
    """Represents a VANET communication event"""
    timestamp: float
    event_type: str  # 'beacon', 'emergency', 'traffic_info', 'v2i_update'
    sender_id: str
    receiver_id: str
    message_size: int
    channel: str  # 'wifi_80211p', 'wimax'
    success: bool
    delay_ms: float
    snr_db: Optional[float] = None
    data_rate_mbps: Optional[float] = None

class NS3PythonInterface:
    """Python interface to NS3 VANET simulations"""

    def __init__(self, ns3_path: str = NS3_PATH):
        self.ns3_path = ns3_path
        self.logger = logging.getLogger('ns3_python_interface')
        self.event_log: List[VANETCommunicationEvent] = []

    def run_vanet_scenario(self, scenario_config: Dict) -> Dict:
        """Run VANET scenario using NS3 and return results"""
        try:
            self.logger.info(f"Running VANET scenario: {scenario_config}")

            # Generate NS3 script based on scenario
            script_path = self._generate_scenario_script(scenario_config)

            # Build NS3 script
            build_cmd = f"cd {self.ns3_path} && ./ns3 build vanet-scenario"
            result = subprocess.run(build_cmd, shell=True, capture_output=True, text=True)

            if result.returncode != 0:
                self.logger.error(f"NS3 build failed: {result.stderr}")
                return {}

            # Run simulation
            run_cmd = self._build_run_command(scenario_config)
            result = subprocess.run(run_cmd, shell=True, capture_output=True, text=True)

            if result.returncode != 0:
                self.logger.error(f"NS3 simulation failed: {result.stderr}")
                return {}

            # Parse and return results
            return self._parse_simulation_results()

        except Exception as e:
            self.logger.error(f"Failed to run VANET scenario: {e}")
            return {}

    def _generate_scenario_script(self, config: Dict) -> str:
        """Generate NS3 scenario script based on configuration"""

        script_content = f'''
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/mobility-module.h"
#include "ns3/wifi-module.h"
#include "ns3/wimax-module.h"
#include "ns3/internet-module.h"
#include "ns3/applications-module.h"
#include "ns3/flow-monitor-module.h"

#include <iostream>
#include <fstream>
#include <vector>
#include <map>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("VANETScenario");

// Global variables for statistics collection
static std::vector<std::string> g_eventLog;
static std::map<std::string, uint32_t> g_packetCounts;
static double g_totalDelay = 0.0;
static uint32_t g_totalPackets = 0;

void LogCommunicationEvent(std::string eventType, std::string sender, std::string receiver,
                          uint32_t size, std::string channel, bool success, double delay)
{{
    std::string event = "{{\\"timestamp\\": " + std::to_string(Simulator::Now().GetSeconds()) +
                       ", \\"type\\": \\"{eventType}\\""
                       ", \\"sender\\": \\"{sender}\\""
                       ", \\"receiver\\": \\"{receiver}\\""
                       ", \\"size\\": " + std::to_string(size) +
                       ", \\"channel\\": \\"{channel}\\""
                       ", \\"success\\": " + (success ? "true" : "false") +
                       ", \\"delay_ms\\": " + std::to_string(delay * 1000) + "}}";

    g_eventLog.push_back(event);
    g_totalPackets++;
    g_packetCounts[eventType]++;
}}

class VANETCommunicationApp : public Application
{{
public:
    VANETCommunicationApp();
    virtual ~VANETCommunicationApp();

    void Setup(Ptr<Node> node, std::string nodeType, bool isEmergency = false);

private:
    virtual void StartApplication(void);
    virtual void StopApplication(void);

    void SendBeacon();
    void SendEmergencyAlert();
    void HandleReceivedMessage(Ptr<Socket> socket);

    Ptr<Node> m_node;
    std::string m_nodeType;
    bool m_isEmergency;
    Ptr<Socket> m_socket;
    EventId m_beaconEvent;
    EventId m_emergencyEvent;
    uint32_t m_messagesSent;
}};

VANETCommunicationApp::VANETCommunicationApp()
    : m_isEmergency(false),
      m_messagesSent(0)
{{
}}

VANETCommunicationApp::~VANETCommunicationApp()
{{
    m_socket = nullptr;
}}

void
VANETCommunicationApp::Setup(Ptr<Node> node, std::string nodeType, bool isEmergency)
{{
    m_node = node;
    m_nodeType = nodeType;
    m_isEmergency = isEmergency;
}}

void
VANETCommunicationApp::StartApplication(void)
{{
    TypeId tid = TypeId::LookupByName("ns3::UdpSocketFactory");
    m_socket = Socket::CreateSocket(m_node, tid);

    InetSocketAddress local = InetSocketAddress(Ipv4Address::GetAny(), 8080);
    m_socket->Bind(local);
    m_socket->SetRecvCallback(MakeCallback(&VANETCommunicationApp::HandleReceivedMessage, this));

    // Schedule message sending based on node type
    if (m_isEmergency) {{
        // Emergency vehicles send frequent safety messages
        m_emergencyEvent = Simulator::Schedule(Seconds(0.05), &VANETCommunicationApp::SendEmergencyAlert, this);
        m_beaconEvent = Simulator::Schedule(Seconds(0.1), &VANETCommunicationApp::SendBeacon, this);
    }} else {{
        // Regular vehicles send periodic beacons
        m_beaconEvent = Simulator::Schedule(Seconds(0.1), &VANETCommunicationApp::SendBeacon, this);
    }}
}}

void
VANETCommunicationApp::StopApplication(void)
{{
    if (m_beaconEvent.IsPending())
        Simulator::Cancel(m_beaconEvent);
    if (m_emergencyEvent.IsPending())
        Simulator::Cancel(m_emergencyEvent);
    if (m_socket)
        m_socket->Close();
}}

void
VANETCommunicationApp::SendBeacon()
{{
    // Create CAM (Cooperative Awareness Message) compatible with your Python implementation
    std::string beacon = "{{\\"type\\": \\"CAM\\", "
                        "\\"node_id\\": \\"{m_nodeType}_\\" + std::to_string(m_node->GetId()) + \\"\\", "
                        "\\"speed\\": \\"50.0\\", "
                        "\\"heading\\": \\"90.0\\", "
                        "\\"position\\": {{\\"x\\": 100.0, \\"y\\": 100.0}}, "
                        "\\"timestamp\\": \\" + std::to_string(Simulator::Now().GetSeconds()) + \\"\\", "
                        "\\"priority\\": \\"3\\"}}";

    Ptr<Packet> packet = Create<Packet>((uint8_t*)beacon.c_str(), beacon.length());

    // Simulate transmission delay and success
    double distance = 150.0; // Assume 150m to nearest neighbor
    double delay = 0.001; // 1ms transmission delay
    bool success = (rand() % 100) < 95; // 95% success rate

    m_socket->SendTo(packet, 0, InetSocketAddress(Ipv4Address("255.255.255.255"), 8080));

    LogCommunicationEvent("beacon", m_nodeType + "_" + std::to_string(m_node->GetId()),
                         "BROADCAST", beacon.length(), "wifi_80211p", success, delay);

    m_messagesSent++;

    // Schedule next beacon
    m_beaconEvent = Simulator::Schedule(Seconds(0.1), &VANETCommunicationApp::SendBeacon, this);
}}

void
VANETCommunicationApp::SendEmergencyAlert()
{{
    // Emergency alert message
    std::string emergency = "{{\\"type\\": \\"EMERGENCY\\", "
                           "\\"node_id\\": \\"emergency_\\" + std::to_string(m_node->GetId()) + \\"\\", "
                           "\\"alert_type\\": \\"AMBULANCE\\", "
                           "\\"priority\\": \\"1\\", "
                           "\\"location\\": {{\\"x\\": 500, \\"y\\": 500}}, "
                           "\\"timestamp\\": \\" + std::to_string(Simulator::Now().GetSeconds()) + \\"\\"}}";

    Ptr<Packet> packet = Create<Packet>((uint8_t*)emergency.c_str(), emergency.length());

    double delay = 0.0005; // 0.5ms for emergency (faster)
    bool success = (rand() % 100) < 98; // 98% success for emergency

    m_socket->SendTo(packet, 0, InetSocketAddress(Ipv4Address("255.255.255.255"), 8081));

    LogCommunicationEvent("emergency", m_nodeType + "_" + std::to_string(m_node->GetId()),
                         "BROADCAST", emergency.length(), "wifi_80211p", success, delay);

    m_messagesSent++;

    // Schedule next emergency message (20Hz = 50ms)
    m_emergencyEvent = Simulator::Schedule(Seconds(0.05), &VANETCommunicationApp::SendEmergencyAlert, this);
}}

void
VANETCommunicationApp::HandleReceivedMessage(Ptr<Socket> socket)
{{
    Ptr<Packet> packet;
    Address from;
    while ((packet = socket->RecvFrom(from)))
    {{
        uint32_t size = packet->GetSize();
        uint8_t* buffer = new uint8_t[size];
        packet->CopyData(buffer, size);

        std::string message((char*)buffer, size);

        // Log reception event
        LogCommunicationEvent("received", "unknown", m_nodeType + "_" + std::to_string(m_node->GetId()),
                             size, "wifi_80211p", true, 0.001);

        delete[] buffer;
    }}
}}

void setupVANETNodes(int numVehicles, int numEmergency)
{{
    NS_LOG_INFO("Setting up VANET nodes...");

    // Create node containers
    NodeContainer vehicleNodes;
    NodeContainer emergencyNodes;
    NodeContainer infrastructureNodes;

    vehicleNodes.Create(numVehicles);
    emergencyNodes.Create(numEmergency);
    infrastructureNodes.Create(4); // 4 intersections

    // Setup WiFi (802.11p) for V2V communication
    WifiHelper wifi;
    wifi.SetStandard(WIFI_STANDARD_80211p);

    YansWifiPhyHelper wifiPhy;
    wifiPhy.Set("RxGain", DoubleValue(0));
    wifiPhy.SetPcapDataLinkType(WifiPhyHelper::DLT_IEEE802_11_RADIO);

    YansWifiChannelHelper wifiChannel;
    wifiChannel.SetPropagationDelay("ns3::ConstantSpeedPropagationDelayModel");
    wifiChannel.AddPropagationLoss("ns3::RangePropagationLossModel",
                                   "MaxRange", DoubleValue(300.0));
    wifiPhy.SetChannel(wifiChannel.Create());

    WifiMacHelper wifiMac;
    wifiMac.SetType("ns3::AdhocWifiMac");
    wifi.SetRemoteStationManager("ns3::AarfWifiManager");

    // Install WiFi on vehicles and emergency vehicles
    NetDeviceContainer wifiDevices = wifi.Install(wifiPhy, wifiMac, vehicleNodes);
    NetDeviceContainer emergencyWifiDevices = wifi.Install(wifiPhy, wifiMac, emergencyNodes);

    // Setup WiMAX for V2I communication
    WimaxHelper wimax;

    NetDeviceContainer infrastructureDevices = wimax.Install(
        infrastructureNodes,
        WimaxHelper::DEVICE_TYPE_BASE_STATION,
        WimaxHelper::SIMPLE_PHY_TYPE_OFDM,
        WimaxHelper::SCHED_TYPE_SIMPLE
    );

    NetDeviceContainer vehicleWimaxDevices = wimax.Install(
        vehicleNodes,
        WimaxHelper::DEVICE_TYPE_SUBSCRIBER_STATION,
        WimaxHelper::SIMPLE_PHY_TYPE_OFDM,
        WimaxHelper::SCHED_TYPE_SIMPLE
    );

    // Setup mobility in realistic traffic pattern
    MobilityHelper mobility;

    Ptr<ListPositionAllocator> vehiclePositionAlloc = CreateObject<ListPositionAllocator>();
    Ptr<ListPositionAllocator> emergencyPositionAlloc = CreateObject<ListPositionAllocator>();
    Ptr<ListPositionAllocator> infrastructurePositionAlloc = CreateObject<ListPositionAllocator>();

    // Position vehicles in 2x2 grid with intersecting roads
    double roadLength = 1000.0;
    double laneWidth = 10.0;

    // Horizontal roads (East-West)
    for (int i = 0; i < numVehicles/2; ++i) {{
        double x = i * (roadLength / (numVehicles/4));
        vehiclePositionAlloc->Add(Vector(x, 0.0, 0.0));                    // Bottom lane
        vehiclePositionAlloc->Add(Vector(x, laneWidth, 0.0));              // Top lane (opposite direction)
    }}

    // Vertical roads (North-South)
    for (int i = 0; i < numVehicles/2; ++i) {{
        double y = i * (roadLength / (numVehicles/4));
        vehiclePositionAlloc->Add(Vector(0.0, y, 0.0));                    // Left lane
        vehiclePositionAlloc->Add(Vector(laneWidth, y, 0.0));              // Right lane (opposite direction)
    }}

    // Emergency vehicles at strategic locations
    emergencyPositionAlloc->Add(Vector(200.0, 200.0, 0.0));  // Emergency 1
    emergencyPositionAlloc->Add(Vector(800.0, 800.0, 0.0));  // Emergency 2

    // Infrastructure at intersections
    infrastructurePositionAlloc->Add(Vector(500.0, 500.0, 15.0));  // Central intersection
    infrastructurePositionAlloc->Add(Vector(500.0, 0.0, 15.0));     // South intersection
    infrastructurePositionAlloc->Add(Vector(0.0, 500.0, 15.0));     // West intersection
    infrastructurePositionAlloc->Add(Vector(1000.0, 500.0, 15.0));   // East intersection

    // Install mobility models
    mobility.SetPositionAllocator(vehiclePositionAlloc);
    mobility.SetMobilityModel("ns3::ConstantVelocityMobilityModel");
    mobility.Install(vehicleNodes);

    mobility.SetPositionAllocator(emergencyPositionAlloc);
    mobility.SetMobilityModel("ns3::ConstantVelocityMobilityModel");
    mobility.Install(emergencyNodes);

    mobility.SetPositionAllocator(infrastructurePositionAlloc);
    mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobility.Install(infrastructureNodes);

    // Setup IP networking
    InternetStackHelper internet;
    internet.Install(vehicleNodes);
    internet.Install(emergencyNodes);
    internet.Install(infrastructureNodes);

    // WiFi network (V2V)
    Ipv4AddressHelper ipv4;
    ipv4.SetBase("10.1.1.0", "255.255.255.0");
    Ipv4InterfaceContainer wifiInterfaces = ipv4.Assign(wifiDevices);
    ipv4.Assign(emergencyWifiDevices);

    // WiMAX network (V2I)
    ipv4.SetBase("10.2.1.0", "255.255.255.0");
    ipv4.Assign(infrastructureDevices);
    ipv4.Assign(vehicleWimaxDevices);

    // Install VANET applications
    for (uint32_t i = 0; i < vehicleNodes.GetN(); ++i) {{
        Ptr<Node> node = vehicleNodes.Get(i);
        Ptr<VANETCommunicationApp> app = CreateObject<VANETCommunicationApp>();
        node->AddApplication(app);
        app->Setup(node, "vehicle", false);
        app->SetStartTime(Seconds(1.0));
        app->SetStopTime(Seconds(300.0));
    }}

    for (uint32_t i = 0; i < emergencyNodes.GetN(); ++i) {{
        Ptr<Node> node = emergencyNodes.Get(i);
        Ptr<VANETCommunicationApp> emergencyApp = CreateObject<VANETCommunicationApp>();
        node->AddApplication(emergencyApp);
        app->Setup(node, "emergency", true);
        emergencyApp->SetStartTime(Seconds(1.0));
        emergencyApp->SetStopTime(Seconds(300.0));
    }}

    // Enable tracing
    wifiPhy.EnablePcapAll("vanet-scenario-wifi");
    wimax.EnablePcapAll("vanet-scenario-wimax");

    // Setup Flow Monitor for detailed statistics
    FlowMonitorHelper flowmon;
    Ptr<FlowMonitor> monitor = flowmon.InstallAll();

    NS_LOG_INFO("VANET scenario setup complete");
}}

int main(int argc, char *argv[])
{{
    int numVehicles = 20;
    int numEmergency = 2;
    double simulationTime = 60.0;
    bool enablePcap = true;

    CommandLine cmd(__FILE__);
    cmd.AddValue("numVehicles", "Number of vehicles", numVehicles);
    cmd.AddValue("numEmergency", "Number of emergency vehicles", numEmergency);
    cmd.AddValue("simulationTime", "Simulation time", simulationTime);
    cmd.AddValue("enablePcap", "Enable PCAP tracing", enablePcap);
    cmd.Parse(argc, argv);

    // Enable logging
    LogComponentEnable("VANETScenario", LOG_LEVEL_INFO);
    LogComponentEnable("UdpSocketImpl", LOG_LEVEL_WARN);

    NS_LOG_INFO("Starting VANET Scenario Simulation...");
    NS_LOG_INFO("Vehicles: " << numVehicles);
    NS_LOG_INFO("Emergency: " << numEmergency);
    NS_LOG_INFO("Duration: " << simulationTime << "s");

    // Setup VANET nodes and communication
    setupVANETNodes(numVehicles, numEmergency);

    // Run simulation
    Simulator::Stop(Seconds(simulationTime));
    Simulator::Run();

    NS_LOG_INFO("Simulation completed");
    NS_LOG_INFO("Total events logged: " << g_eventLog.size());
    NS_LOG_INFO("Total packets: " << g_totalPackets);

    // Export detailed event log
    std::ofstream eventFile("vanet_events.json");
    eventFile << "[";
    for (size_t i = 0; i < g_eventLog.size(); ++i) {{
        eventFile << g_eventLog[i];
        if (i < g_eventLog.size() - 1) eventFile << ",";
    }}
    eventFile << "]";
    eventFile.close();

    // Export summary statistics
    std::ofstream statsFile("vanet_stats.json");
    statsFile << "{{\\"simulation\\": {{\\"duration\\": " << simulationTime
              << ", \\"vehicles\\": " << numVehicles
              << ", \\"emergency\\": " << numEmergency
              << "}}, \\"statistics\\": {{\\"total_events\\": " << g_eventLog.size()
              << ", \\"total_packets\\": " << g_totalPackets
              << ", \\"packet_rate\\": " << (g_totalPackets / simulationTime);

    // Add packet type breakdown
    statsFile << ", \\"beacon_count\\": " << g_packetCounts["beacon"]
              << ", \\"emergency_count\\": " << g_packetCounts["emergency"]
              << ", \\"received_count\\": " << g_packetCounts["received"];

    statsFile << ", \\"throughput_mbps\\": " << (g_totalPackets * 1000 / simulationTime / 1e6)
              << ", \\"average_delay_ms\\": " << (g_totalDelay / max(1, (int)g_eventLog.size()) * 1000)
              << "}}";
    statsFile << "}}";
    statsFile.close();

    Simulator::Destroy();
    NS_LOG_INFO("Results exported to vanet_events.json and vanet_stats.json");
    return 0;
}}
'''

        script_path = os.path.join(self.ns3_path, "scratch", "vanet-scenario.cc")
        with open(script_path, 'w') as f:
            f.write(script_content)

        self.logger.info(f"VANET scenario script created at {script_path}")
        return script_path

    def _build_run_command(self, config: Dict) -> str:
        """Build NS3 run command with configuration parameters"""
        cmd = f"cd {self.ns3_path} && ./ns3 run vanet-scenario"

        if 'num_vehicles' in config:
            cmd += f" --numVehicles={config['num_vehicles']}"
        if 'num_emergency' in config:
            cmd += f" --numEmergency={config['num_emergency']}"
        if 'simulation_time' in config:
            cmd += f" --simulationTime={config['simulation_time']}"
        if 'enable_pcap' in config:
            cmd += f" --enablePcap={'true' if config['enable_pcap'] else 'false'}"

        return cmd

    def _parse_simulation_results(self) -> Dict:
        """Parse simulation results from NS3 output files"""
        results = {{
            'events': [],
            'statistics': {},
            'success': False
        }}

        try:
            # Parse events file
            events_file = os.path.join(self.ns3_path, "vanet_events.json")
            if os.path.exists(events_file):
                with open(events_file, 'r') as f:
                    results['events'] = json.load(f)

            # Parse statistics file
            stats_file = os.path.join(self.ns3_path, "vanet_stats.json")
            if os.path.exists(stats_file):
                with open(stats_file, 'r') as f:
                    results['statistics'] = json.load(f)

            results['success'] = True
            self.logger.info("Successfully parsed simulation results")

        except Exception as e:
            self.logger.error(f"Failed to parse simulation results: {e}")
            results['success'] = False

        return results

    def integrate_with_python_vanet(self, python_vanet_results: Dict) -> Dict:
        """Integrate NS3 results with Python VANET implementation results"""

        # This would combine results from both implementations
        integrated_results = {{
            'python_implementation': python_vanet_results,
            'ns3_validation': self._parse_simulation_results(),
            'comparison': {{
                'pdr_difference': 0.0,
                'delay_difference_ms': 0.0,
                'throughput_difference_mbps': 0.0
            }}
        }}

        # Compare metrics between Python and NS3 implementations
        if integrated_results['ns3_validation'].get('success', False):
            ns3_stats = integrated_results['ns3_validation']['statistics']
            python_stats = python_vanet_results.get('performance_metrics', {})

            if 'packet_delivery_ratio' in ns3_stats and 'packet_delivery_ratio' in python_stats:
                integrated_results['comparison']['pdr_difference'] = (
                    ns3_stats['packet_delivery_ratio'] - python_stats['packet_delivery_ratio']
                )

            if 'average_delay_ms' in ns3_stats and 'average_delay_ms' in python_stats:
                integrated_results['comparison']['delay_difference_ms'] = (
                    ns3_stats['average_delay_ms'] - python_stats['average_delay_ms']
                )

        return integrated_results

# Example usage
if __name__ == "__main__":
    # Test NS3 Python integration
    interface = NS3PythonInterface()

    # Example VANET scenario configuration
    scenario_config = {{
        'num_vehicles': 20,
        'num_emergency': 2,
        'simulation_time': 60.0,
        'enable_pcap': True
    }}

    print("\n" + "="*60)
    print("NS3 PYTHON INTERFACE TEST")
    print("="*60)

    print(f"Running VANET scenario with {scenario_config['num_vehicles']} vehicles...")
    results = interface.run_vanet_scenario(scenario_config)

    if results.get('success', False):
        print("✅ NS3 simulation completed successfully!")
        print(f"📊 Events logged: {len(results.get('events', []))}")
        print(f"📈 Statistics: {results.get('statistics', {})}")

        # Test integration with Python VANET implementation
        from ieee80211 import Complete_VANET_Protocol_Stack

        python_vanet = Complete_VANET_Protocol_Stack()
        python_results = python_vanet.get_performance_statistics()

        integrated = interface.integrate_with_python_vanet(python_results)

        print(f"\n🔗 Integration Results:")
        print(f"  Python PDR: {python_results.get('packet_delivery_ratio', 0)*100:.1f}%")
        print(f"  NS3 PDR: {integrated['ns3_validation']['statistics'].get('packet_delivery_ratio', 0)*100:.1f}%")
        print(f"  Difference: {integrated['comparison']['pdr_difference']*100:+.1f}%")

    else:
        print("❌ NS3 simulation failed")

    print("="*60)
