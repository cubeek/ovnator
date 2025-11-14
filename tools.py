"""
OVN/OVS Troubleshooting Tools

This module contains all tool definitions, schemas, validation, and execution logic
for the OVN troubleshooting agent.
"""

import subprocess
from typing import Tuple, Optional, Dict, Any, List

# --- Configuration Constants ---

# Command execution timeouts (in seconds)
TIMEOUT_STANDARD = 10
TIMEOUT_PACKET_CAPTURE = 30

# Packet capture limits
MIN_PACKET_COUNT = 1
MAX_PACKET_COUNT = 100
DEFAULT_PACKET_COUNT = 10

# Debug output limits
MAX_STDERR_DISPLAY = 200

# --- Tool Schema Definitions ---

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_ovn_logical_topology",
            "description": "Get the OVN logical network topology using 'ovn-nbctl show'. This shows logical switches, logical routers, logical ports, and their relationships. Use this to understand the logical network structure before tracing packets.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_ovs_topology",
            "description": "Get the Open vSwitch topology using 'ovs-vsctl show'. This shows OVS bridges, ports, interfaces, and their connections. Use this to understand which physical interfaces are connected to which bridges and to discover tap devices for VMs.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_ovs_ports",
            "description": "List all OVS ports and their details using 'ovs-vsctl list interface'. This shows interface names, MAC addresses, types, and status. Use this to find specific interfaces like tap devices or physical ports.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "dump_ovs_flows",
            "description": "Dump OpenFlow flows from an OVS bridge using 'ovs-ofctl dump-flows'. This shows the actual flow rules that determine packet forwarding behavior. Use this to verify what flows are installed on a bridge and see if packets match expected rules. Essential for debugging packet drops or incorrect forwarding.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bridge": {
                        "type": "string",
                        "description": "OVS bridge name to dump flows from (e.g., 'br-int', 'br-ex')"
                    }
                },
                "required": ["bridge"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "capture_packets",
            "description": "Capture network packets using tcpdump on a specified interface. Use this to see actual packets arriving/leaving on physical interfaces or tap devices. Useful for verifying if packets are reaching the expected interface and to extract packet details (IPs, MACs, protocols). The capture will stop after collecting the specified number of packets or timeout.",
            "parameters": {
                "type": "object",
                "properties": {
                    "interface": {
                        "type": "string",
                        "description": "Network interface to capture on (e.g., 'eth0', 'br-int', 'tap12345678')"
                    },
                    "filter": {
                        "type": "string",
                        "description": "BPF filter expression to capture specific traffic (e.g., 'icmp', 'host 10.0.0.48', 'tcp port 80'). Leave empty to capture all traffic."
                    },
                    "count": {
                        "type": "integer",
                        "description": f"Maximum number of packets to capture (default: {DEFAULT_PACKET_COUNT}, max: {MAX_PACKET_COUNT})"
                    }
                },
                "required": ["interface"]
            }
        }
    }
]


# --- Helper Functions ---

def _run_command(cmd: List[str], timeout: int = TIMEOUT_STANDARD,
                 use_stderr_as_output: bool = False) -> str:
    """
    Execute a shell command and return its output.

    Args:
        cmd: Command and arguments as a list
        timeout: Maximum time to wait for command completion
        use_stderr_as_output: If True, prefer stderr over stdout for output
                              (useful for tools like tcpdump)

    Returns:
        Command output or error message
    """
    print(f"--- [Tool] Running command: {' '.join(cmd)} ---")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout
        )

        # Debug output
        print(f"--- [Tool] Exit code: {result.returncode} ---")
        if result.stderr and not use_stderr_as_output:
            print(f"--- [Tool] STDERR: {result.stderr[:MAX_STDERR_DISPLAY]} ---")

        # Determine output based on command behavior
        if use_stderr_as_output:
            # For commands that write to stderr by default (e.g., tcpdump)
            output = result.stderr if result.stderr else result.stdout
        else:
            # For normal commands that write to stdout
            output = result.stdout if result.stdout else None

        if output:
            return output
        elif result.stderr:
            return f"Error: {result.stderr}"
        else:
            return "Command executed but produced no output."

    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds."
    except FileNotFoundError:
        return f"Error: Command not found: {cmd[0]}"
    except PermissionError:
        return f"Error: Permission denied running command: {' '.join(cmd)}"
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"


def get_tools_description() -> str:
    """
    Generate a human-readable description of available tools from schemas.

    Returns:
        Formatted description of all available tools
    """
    description = "**AVAILABLE TOOLS:**\n\n"
    for idx, tool_schema in enumerate(TOOL_SCHEMAS, 1):
        func = tool_schema["function"]
        description += f"{idx}. `{func['name']}()`\n"
        description += f"   * {func['description']}\n"

        params = func["parameters"]["properties"]
        if params:
            description += f"   * Parameters:\n"
            for param_name, param_info in params.items():
                required = "required" if param_name in func["parameters"].get("required", []) else "optional"
                description += f"     - {param_name} ({param_info['type']}, {required}): {param_info.get('description', 'No description')}\n"
        else:
            description += f"   * No parameters required\n"
        description += "\n"

    return description


def validate_tool_call(tool_name: str, tool_args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate tool call against schema.

    Args:
        tool_name: Name of the tool to validate
        tool_args: Arguments provided for the tool

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Find the tool schema
    tool_schema = None
    for schema in TOOL_SCHEMAS:
        if schema["function"]["name"] == tool_name:
            tool_schema = schema["function"]
            break

    if not tool_schema:
        return False, f"Unknown tool: {tool_name}"

    # Check required parameters
    required_params = tool_schema["parameters"].get("required", [])
    for param in required_params:
        if param not in tool_args:
            return False, f"Missing required parameter: {param}"

    # Check for unexpected parameters
    valid_params = tool_schema["parameters"]["properties"].keys()
    for param in tool_args.keys():
        if param not in valid_params:
            return False, f"Unexpected parameter: {param}"

    # Type checking
    for param_name, param_value in tool_args.items():
        expected_type = tool_schema["parameters"]["properties"][param_name].get("type")
        if expected_type == "string" and not isinstance(param_value, str):
            return False, f"Parameter '{param_name}' must be a string"
        elif expected_type == "integer" and not isinstance(param_value, int):
            return False, f"Parameter '{param_name}' must be an integer"

    return True, None


# --- Tool Implementations ---

def _execute_ovn_logical_topology() -> str:
    """
    Execute ovn-nbctl show to get logical topology.

    Returns:
        Command output or error message
    """
    cmd = ["sudo", "ovn-nbctl", "show"]
    return _run_command(cmd)


def _execute_ovs_topology() -> str:
    """
    Execute ovs-vsctl show to get OVS topology.

    Returns:
        Command output or error message
    """
    cmd = ["sudo", "ovs-vsctl", "show"]
    return _run_command(cmd)


def _execute_ovs_ports() -> str:
    """
    Execute ovs-vsctl list interface to get OVS interface details.

    Returns:
        Command output or error message
    """
    cmd = ["sudo", "ovs-vsctl", "list", "interface"]
    return _run_command(cmd)


def _execute_dump_ovs_flows(bridge: str) -> str:
    """
    Execute ovs-ofctl dump-flows to get OpenFlow flows from a bridge.

    Args:
        bridge: OVS bridge name

    Returns:
        Flow dump output or error message
    """
    cmd = ["sudo", "ovs-ofctl", "dump-flows", bridge]
    return _run_command(cmd)


def _execute_capture_packets(interface: str, filter_expr: str = "", count: int = DEFAULT_PACKET_COUNT) -> str:
    """
    Execute tcpdump to capture packets on an interface.

    Args:
        interface: Network interface name
        filter_expr: BPF filter expression
        count: Number of packets to capture

    Returns:
        Packet capture output or error message
    """
    # Sanitize and limit count to reasonable range
    count = max(MIN_PACKET_COUNT, min(count, MAX_PACKET_COUNT))

    # Build tcpdump command
    # -n: Don't resolve hostnames
    # -v: Verbose output
    # -e: Print link-level header
    # -c: Capture count
    cmd = ["sudo", "tcpdump", "-n", "-v", "-e", "-c", str(count), "-i", interface]

    # Add filter if provided
    if filter_expr:
        cmd.append(filter_expr)

    # tcpdump writes output to stderr by default
    return _run_command(cmd, timeout=TIMEOUT_PACKET_CAPTURE, use_stderr_as_output=True)


# --- Tool Registry ---

# Wrapper functions that adapt tool implementations to a common interface
def _call_ovn_logical_topology(args: Dict[str, Any]) -> str:
    """Wrapper for get_ovn_logical_topology."""
    return _execute_ovn_logical_topology()


def _call_ovs_topology(args: Dict[str, Any]) -> str:
    """Wrapper for get_ovs_topology."""
    return _execute_ovs_topology()


def _call_ovs_ports(args: Dict[str, Any]) -> str:
    """Wrapper for get_ovs_ports."""
    return _execute_ovs_ports()


def _call_dump_ovs_flows(args: Dict[str, Any]) -> str:
    """Wrapper for dump_ovs_flows."""
    bridge = args.get("bridge")
    return _execute_dump_ovs_flows(bridge)


def _call_capture_packets(args: Dict[str, Any]) -> str:
    """Wrapper for capture_packets."""
    interface = args.get("interface")
    filter_expr = args.get("filter", "")
    count = args.get("count", DEFAULT_PACKET_COUNT)
    return _execute_capture_packets(interface, filter_expr, count)


# Map tool names to their implementation functions
TOOL_REGISTRY = {
    "get_ovn_logical_topology": _call_ovn_logical_topology,
    "get_ovs_topology": _call_ovs_topology,
    "get_ovs_ports": _call_ovs_ports,
    "dump_ovs_flows": _call_dump_ovs_flows,
    "capture_packets": _call_capture_packets,
}


# --- Main Tool Executor ---

def execute_tool(tool_name: str, tool_args: Dict[str, Any]) -> str:
    """
    Execute a tool with validation.

    Args:
        tool_name: Name of the tool to execute
        tool_args: Arguments for the tool

    Returns:
        Tool output or error message
    """
    print(f"--- [Tool] Executing: {tool_name} ---")

    # Validate the tool call
    is_valid, error = validate_tool_call(tool_name, tool_args)
    if not is_valid:
        return f"Error: Tool validation failed: {error}"

    # Look up and execute the tool
    tool_func = TOOL_REGISTRY.get(tool_name)
    if tool_func:
        return tool_func(tool_args)

    # This shouldn't happen if validation works correctly
    return f"Error: Tool '{tool_name}' is defined but not implemented"
