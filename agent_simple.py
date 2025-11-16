"""
OVN/Neutron Troubleshooting Agent (Simplified with LlamaStack Agent)

Uses the built-in Agent class from llama_stack_client instead of manual protocol.
"""

import sys
import logging
from llama_stack_client import LlamaStackClient, Agent
from tools import TOOL_SCHEMAS, execute_tool

# Suppress noisy HTTP logs
logging.getLogger("httpx").setLevel(logging.WARNING)

# --- Configuration ---

LLAMASTACK_SERVER_URL = "http://10.40.128.51:8321"
MODEL_NAME = "ollama/llama3.1:70b"  # Using 70B for better reasoning (slower on CPU)


# --- System Instructions ---

INSTRUCTIONS = """
You are a senior network engineer specializing in OVN (Open Virtual Network) and OVS (Open vSwitch) in an OpenStack Neutron environment. Your mission is to help analyze and troubleshoot network configurations on this compute node.

**YOUR ROLE:**
- Answer questions about the network topology, configuration, and connectivity
- **ALWAYS use available tools to gather current information** - do not make assumptions
- When asked to troubleshoot, follow a systematic approach to find root causes
- Recognize when configurations are correct and working as expected
- Provide clear, accurate information based on tool outputs

**AUTOMATIC IP DIAGNOSTICS:**
When troubleshooting an IP, ALWAYS start by calling `get_ovn_logical_topology` FIRST to find the port UUID.
Then call `get_ovs_topology` to find the tap device.
Then use other tools based on what you find.

NEVER guess interface names - always get topology first!

**KEY OVN/NEUTRON CONCEPTS:**
* **br-int:** The main OVS integration bridge on the compute node. All VM tap devices connect here.
* **Logical Topology:** Neutron networks map to OVN logical switches, routers map to logical routers.
* **Port Bindings:** Map logical ports to physical compute nodes and interfaces.
* **Tap Devices:** VMs connect via tap interfaces on br-int. Tap names are derived from logical port UUIDs (first 11 chars of UUID = tap device suffix).
* **Localnet Ports:** Physical network connections in OVN. Each provider/external network has a "localnet" port that connects to an OVS bridge.
* **Two-level debugging:** Always trace at BOTH levels - a packet might pass logical checks but fail at the physical level, or vice versa.

**HOW TO USE ovn-trace CORRECTLY:**
You must determine the correct logical datapath and inport by analyzing packet flow:

**STEP 1: Identify packet source from tcpdump:**
- Physical NIC (enp*, eth*, etc.)? → External/provider network traffic
- Geneve tunnel (genev_sys_*)? → Inter-node traffic (from another compute)
- Tap device (tap*)? → Local VM traffic
- Bridge (br-*)? → Check which physical interfaces are attached

**STEP 2: Map source to logical ingress point:**

**A) From Physical NIC:**
  1. In OVS topology: Find which bridge the NIC connects to
  2. In OVN topology: Find logical switch with a "localnet" port whose name contains that bridge name
  3. Use: datapath = that logical switch, inport = that localnet port name

**B) From Geneve Tunnel:**
  1. Traffic already traversed OVN on the source node
  2. Find destination VM's IP in OVN topology to get its logical port and switch
  3. Use: datapath = destination VM's logical switch, inport = destination VM's logical port

**C) From VM Tap Device:**
  1. Match tap device name to logical port UUID (first 11 chars)
  2. Find that port's logical switch in OVN topology
  3. Use: datapath = source VM's logical switch, inport = source VM's logical port

**KEY PRINCIPLE:** datapath and inport represent WHERE packets ENTER the logical topology, not their destination.
Always trace from the ingress point forward through the logical network.

**TROUBLESHOOTING WORKFLOW:**
  1. Find the VM's IP in `ovn-nbctl show` to get its logical port UUID and switch
  2. Find the corresponding tap device (first 11 chars of UUID) in `ovs-vsctl show`
  3. **CHECK TRAFFIC AT MULTIPLE LAYERS** to identify where packets are dropped:
     a. **Broad capture FIRST:** Capture on ALL interfaces (`-i any`) filtered by workload IP to see if traffic exists anywhere on the node
     b. **Physical layer:** If traffic found, capture on specific physical NICs to verify ingress/egress
     c. **VM layer:** Capture on specific tap devices to see if traffic reaches the VM
  4. **Compare traffic:** If traffic appears on physical NICs but not on tap devices, packets are being dropped in OVS/OVN
  5. Use extracted packet details to trace through both OVS (`trace_ovs_flow`) and OVN (`trace_ovn_packet`)
  6. Analyze traces to find where packet is dropped or incorrectly handled

**CRITICAL: When checking for traffic, start with `-i any` filtered by workload IPs!**
Traffic flow: Physical NIC → OVS/OVN Processing → Tap Device → VM
- When checking for general workload traffic, FIRST get topology to identify all workload IPs on this node
- Build a tcpdump filter for workload IPs only: "host IP1 or host IP2 or host IP3" to avoid control plane traffic
- Use `capture_packets` with interface="any" and the workload IP filter
- If traffic appears on physical interfaces but NOT on tap devices, packets are being dropped in OVS/OVN
- NOTE: Do NOT capture on OVS bridges (br-int, br-ex) - unicast traffic is not observable there

**EXAMPLE: Checking for workload traffic**
1. Get topology with `get_ovn_logical_topology` to find all workload IPs on this node
2. Build tcpdump filter: interface="any", filter="host <IP1> or host <IP2> or host <IP3>"
3. This shows ONLY workload traffic, filtering out control plane noise (OVN tunnels, APIs, etc.)
"""


# --- Tool Wrapper Functions ---

def create_tool_wrappers():
    """
    Create Python callable wrappers for each tool.
    LlamaStack Agent can use these directly.
    """
    from llama_stack_client.lib.agents.client_tool import ClientTool

    tools = []

    for schema in TOOL_SCHEMAS:
        func_def = schema["function"]
        tool_name = func_def["name"]
        tool_desc = func_def["description"]
        tool_params = func_def["parameters"]

        # Create a ClientTool subclass for each tool
        class CustomTool(ClientTool):
            def __init__(self, name, description, parameters):
                self._name = name
                self._description = description
                self._parameters = parameters

            def get_name(self):
                return self._name

            def get_description(self):
                return self._description

            def get_input_schema(self):
                return self._parameters

            def run_impl(self, **kwargs):
                """Execute the tool and return result."""
                print(f"--- [Tool] {self._name} ---")
                result = execute_tool(self._name, kwargs)
                if result.startswith("Error:"):
                    print(f"    ✗ {result[:150]}")
                else:
                    print(f"    ✓ {len(result)} chars returned")
                return result

        tools.append(CustomTool(tool_name, tool_desc, tool_params))

    return tools


def main():
    """Main entry point."""
    print(f"{'='*65}")
    print("OVN Troubleshooting Agent (Using LlamaStack Agent)")
    print(f"{'='*65}")
    print(f"Server: {LLAMASTACK_SERVER_URL}")
    print(f"Model: {MODEL_NAME}")
    print("Type 'exit' to quit")
    print(f"{'='*65}\n")

    # Initialize client with longer timeout for 70B model on CPU
    try:
        client = LlamaStackClient(base_url=LLAMASTACK_SERVER_URL, timeout=1200.0)  # 20 minutes
        print(f"✓ Connected to LlamaStack server\n")
    except Exception as e:
        print(f"✗ Could not connect to LlamaStack server")
        print(f"Error: {e}")
        sys.exit(1)

    # Create tool wrappers (ClientTool instances that can execute locally)
    tools = create_tool_wrappers()

    # Create agent with executable tool wrappers
    try:
        agent = Agent(
            client=client,
            model=MODEL_NAME,
            instructions=INSTRUCTIONS,
            tools=tools
        )
        print(f"✓ Agent ready with {len(tools)} tools\n")
    except Exception as e:
        print(f"✗ Could not create agent")
        print(f"Error: {e}")
        sys.exit(1)

    # Create a session
    try:
        session_id = agent.create_session(session_name="ovn-troubleshooting")
        print(f"✓ Session created: {session_id}\n")
    except Exception as e:
        print(f"✗ Could not create session")
        print(f"Error: {e}")
        sys.exit(1)

    # Main conversation loop
    while True:
        user_query = input("[You] ")

        if user_query.lower() in ['exit', 'quit', 'q']:
            print("\nGoodbye!")
            break

        if not user_query.strip():
            continue

        print()  # Blank line for readability

        try:
            # Create a turn (handles tool calling automatically!)
            print("--- [Agent] Thinking... ---")
            response = agent.create_turn(
                session_id=session_id,
                messages=[{"role": "user", "content": user_query}],
                stream=False  # Use non-streaming mode (simpler and works reliably)
            )

            # Extract the final answer from the response
            if hasattr(response, 'output') and response.output:
                for output_item in response.output:
                    if hasattr(output_item, 'content'):
                        # Extract text from content
                        for content_item in output_item.content:
                            if hasattr(content_item, 'text'):
                                print(f"\n--- [Agent] ---")
                                print(content_item.text)
                                print()

            # Show usage stats if available
            if hasattr(response, 'usage'):
                usage = response.usage
                print(f"--- [Tokens] Input: {usage.input_tokens}, Output: {usage.output_tokens} ---\n")

        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
            break
        except Exception as e:
            print(f"\n✗ Error: {e}")
            print(f"Type: {type(e)}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
