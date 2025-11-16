"""
OVN/Neutron Troubleshooting Agent (Direct Gemini API)

Connects directly to Google Gemini API, bypassing LlamaStack.
"""

import os
import sys
import google.generativeai as genai
from tools import TOOL_SCHEMAS, execute_tool

# --- Configuration from Environment Variables ---

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY environment variable not set")
    print("Export it first: export GEMINI_API_KEY='your-key-here'")
    sys.exit(1)

# Model configuration
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")  # Default to Flash (faster/cheaper)

# Optional: Custom API endpoint (for sandbox services or custom deployments)
GEMINI_API_ENDPOINT = os.getenv("GEMINI_API_ENDPOINT")  # e.g., "https://your-service.com/v1"

# Configure the API
if GEMINI_API_ENDPOINT:
    # Custom endpoint (e.g., sandbox service)
    genai.configure(
        api_key=GEMINI_API_KEY,
        transport="rest",
        client_options={"api_endpoint": GEMINI_API_ENDPOINT}
    )
    print(f"Using custom endpoint: {GEMINI_API_ENDPOINT}")
else:
    # Default Google endpoint
    genai.configure(api_key=GEMINI_API_KEY)


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


# --- Convert Tool Schemas to Gemini Format ---

def convert_tools_to_gemini_format():
    """
    Convert our TOOL_SCHEMAS to Gemini's function calling format.

    Returns:
        List of tool declarations in Gemini format
    """
    gemini_tools = []

    for schema in TOOL_SCHEMAS:
        func = schema["function"]

        # Gemini expects a simpler format
        gemini_func = {
            "name": func["name"],
            "description": func["description"],
            "parameters": func["parameters"]
        }

        gemini_tools.append(gemini_func)

    return gemini_tools


# --- Tool Execution ---

def execute_function_call(function_call):
    """
    Execute a function call from Gemini and return the result.

    Args:
        function_call: The function call object from Gemini

    Returns:
        Function result as string
    """
    tool_name = function_call.name
    tool_args = dict(function_call.args)

    print(f"--- [Tool] {tool_name} ---")
    print(f"    Args: {tool_args}")

    result = execute_tool(tool_name, tool_args)

    if result.startswith("Error:"):
        print(f"    ✗ {result[:150]}")
    else:
        print(f"    ✓ {len(result)} chars returned")

    return result


# --- Main Agent Loop ---

def main():
    """Main entry point."""
    print(f"{'='*65}")
    print("OVN Troubleshooting Agent (Direct Gemini API)")
    print(f"{'='*65}")
    print(f"Model: {MODEL_NAME}")
    if GEMINI_API_ENDPOINT:
        print(f"Endpoint: {GEMINI_API_ENDPOINT}")
    else:
        print(f"Endpoint: https://generativelanguage.googleapis.com (default)")
    print(f"API Key: {GEMINI_API_KEY[:20]}...")
    print("Type 'exit' to quit")
    print(f"{'='*65}\n")

    # Convert tools to Gemini format
    gemini_tools = convert_tools_to_gemini_format()
    print(f"✓ Loaded {len(gemini_tools)} tools\n")

    # Create the model with function calling enabled
    try:
        model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            tools=gemini_tools,
            system_instruction=INSTRUCTIONS
        )
        print(f"✓ Model initialized\n")
    except Exception as e:
        print(f"✗ Could not initialize model")
        print(f"Error: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        print("\nTroubleshooting:")
        print("- Check if your endpoint is Gemini-compatible")
        print("- Try testing with curl first")
        print("- Your endpoint might need OpenAI SDK instead (see below)")
        sys.exit(1)

    # Start a chat session
    chat = model.start_chat(enable_automatic_function_calling=False)  # Manual control

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
            # Send message to Gemini
            print("--- [Agent] Thinking... ---")
            response = chat.send_message(user_query)

            # Handle function calls (tool usage)
            max_iterations = 10  # Prevent infinite loops
            iteration = 0

            while response.candidates[0].content.parts[0].function_call and iteration < max_iterations:
                iteration += 1

                # Extract function calls
                function_calls = [
                    part.function_call
                    for part in response.candidates[0].content.parts
                    if part.function_call
                ]

                # Execute each function call
                function_responses = []
                for fc in function_calls:
                    result = execute_function_call(fc)
                    function_responses.append({
                        "function_call": fc,
                        "function_response": {
                            "name": fc.name,
                            "response": {"result": result}
                        }
                    })

                # Send results back to Gemini
                print("--- [Agent] Processing results... ---")
                response = chat.send_message(
                    [fr["function_response"] for fr in function_responses]
                )

            # Extract and display final text response
            if response.text:
                print(f"\n--- [Agent] ---")
                print(response.text)
                print()

            # Show usage stats if available
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage = response.usage_metadata
                print(f"--- [Tokens] Input: {usage.prompt_token_count}, "
                      f"Output: {usage.candidates_token_count} ---\n")

        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
            break
        except Exception as e:
            print(f"\n✗ Error: {e}")
            print(f"Type: {type(e)}")
            import traceback
            traceback.print_exc()
            print()


if __name__ == "__main__":
    main()
