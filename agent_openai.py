"""
OVN/Neutron Troubleshooting Agent (OpenAI-Compatible API)

Works with any OpenAI-compatible endpoint:
- OpenAI API
- Azure OpenAI
- Red Hat AI Sandbox
- Other OpenAI-compatible services
"""

import os
import sys
import json
from openai import OpenAI
from tools import TOOL_SCHEMAS, execute_tool

# --- Configuration from Environment Variables ---

API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY")
if not API_KEY:
    print("ERROR: API key environment variable not set")
    print("Set one of: OPENAI_API_KEY or API_KEY")
    sys.exit(1)

# API endpoint - required for custom services
BASE_URL = os.getenv("OPENAI_BASE_URL") or os.getenv("BASE_URL")
if not BASE_URL:
    print("ERROR: BASE_URL environment variable not set")
    print("Example: export BASE_URL='https://your-service.com/v1'")
    sys.exit(1)

# Model name - check with your service provider
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4")

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
* **Tap Devices:** VMs connect via tap interfaces (e.g., tap12345678, tap6335a75c-5c) on br-int. The tap name is derived from the logical port UUID (first 11 chars).
* **Two-level debugging:** Always trace at BOTH levels - a packet might pass logical checks but fail at the physical level, or vice versa.

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
1. Get topology with `get_ovn_logical_topology` to find workload IPs (e.g., 10.0.0.48, 172.24.5.38)
2. Capture with: interface="any", filter="host 10.0.0.48 or host 172.24.5.38"
3. This shows ONLY workload traffic, filtering out control plane noise
"""


# --- Tool Execution ---

def execute_tool_call(tool_call):
    """
    Execute a tool call from the LLM and return the result.

    Args:
        tool_call: The tool call object from OpenAI

    Returns:
        Tool result message
    """
    tool_name = tool_call.function.name
    tool_args = json.loads(tool_call.function.arguments)

    print(f"--- [Tool] {tool_name} ---")
    print(f"    Args: {tool_args}")

    result = execute_tool(tool_name, tool_args)

    if result.startswith("Error:"):
        print(f"    ✗ {result[:150]}")
    else:
        print(f"    ✓ {len(result)} chars returned")

    return {
        "tool_call_id": tool_call.id,
        "role": "tool",
        "name": tool_name,
        "content": result
    }


# --- Main Agent Loop ---

def main():
    """Main entry point."""
    print(f"{'='*65}")
    print("OVN Troubleshooting Agent (OpenAI-Compatible API)")
    print(f"{'='*65}")
    print(f"Base URL: {BASE_URL}")
    print(f"Model: {MODEL_NAME}")
    print(f"API Key: {API_KEY[:20]}...")
    print("Type 'exit' to quit")
    print(f"{'='*65}\n")

    # Initialize OpenAI client
    try:
        client = OpenAI(
            api_key=API_KEY,
            base_url=BASE_URL
        )
        print(f"✓ Client initialized\n")
    except Exception as e:
        print(f"✗ Could not initialize client")
        print(f"Error: {e}")
        sys.exit(1)

    print(f"✓ Loaded {len(TOOL_SCHEMAS)} tools\n")

    # Message history
    messages = [
        {"role": "system", "content": INSTRUCTIONS}
    ]

    # Main conversation loop
    while True:
        user_query = input("[You] ")

        if user_query.lower() in ['exit', 'quit', 'q']:
            print("\nGoodbye!")
            break

        if not user_query.strip():
            continue

        print()  # Blank line for readability

        # Add user message
        messages.append({"role": "user", "content": user_query})

        try:
            # Call the LLM with tools
            print("--- [Agent] Thinking... ---")

            max_iterations = 10  # Prevent infinite loops
            iteration = 0

            while iteration < max_iterations:
                iteration += 1

                # Debug: Check tool schema format
                if iteration == 1:
                    print(f"[DEBUG] Number of tools: {len(TOOL_SCHEMAS)}")
                    print(f"[DEBUG] Tools type: {type(TOOL_SCHEMAS)}")
                    if TOOL_SCHEMAS:
                        print(f"[DEBUG] First tool keys: {list(TOOL_SCHEMAS[0].keys())}")

                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    tools=TOOL_SCHEMAS,
                    tool_choice="auto"
                )

                assistant_message = response.choices[0].message

                # Check if we're done (no more tool calls)
                if not assistant_message.tool_calls:
                    # Final answer
                    if assistant_message.content:
                        print(f"\n--- [Agent] ---")
                        print(assistant_message.content)
                        print()

                    # Add to history
                    messages.append({
                        "role": "assistant",
                        "content": assistant_message.content
                    })

                    # Show usage stats if available
                    if hasattr(response, 'usage') and response.usage:
                        usage = response.usage
                        print(f"--- [Tokens] Input: {usage.prompt_tokens}, "
                              f"Output: {usage.completion_tokens} ---\n")
                    break

                # Execute tool calls
                messages.append({
                    "role": "assistant",
                    "content": assistant_message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        } for tc in assistant_message.tool_calls
                    ]
                })

                # Execute each tool call
                for tool_call in assistant_message.tool_calls:
                    tool_result = execute_tool_call(tool_call)
                    messages.append(tool_result)

                print("--- [Agent] Processing results... ---")

        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
            break
        except Exception as e:
            print(f"\n✗ Error: {e}")
            print(f"Type: {type(e)}")
            import traceback
            traceback.print_exc()
            print()
            # Don't add failed message to history, let user retry


if __name__ == "__main__":
    main()
