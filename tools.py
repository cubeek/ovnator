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

# Log search limits
DEFAULT_LOG_LINES = 100
MAX_LOG_LINES = 1000

# Debug output limits
MAX_STDERR_DISPLAY = 200

# OVN log file locations (try in order)
OVN_CONTROLLER_LOG_PATHS = [
    "/var/log/openvswitch/ovn-controller.log",
    "/var/log/ovn/ovn-controller.log",
    "/var/log/syslog",  # Fallback for systemd
]

# --- Tool Schema Definitions ---

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_ovn_logical_topology",
            "description": "Get the OVN logical network topology using 'ovn-nbctl show'. This shows logical switches, logical routers, logical ports, and their relationships. Use this to understand the logical network structure before tracing packets.",
            "parameters": {
                "type": "object"
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_ovs_topology",
            "description": "Get the Open vSwitch topology using 'ovs-vsctl show'. This shows OVS bridges, ports, interfaces, and their connections. Use this to understand which physical interfaces are connected to which bridges and to discover tap devices for VMs.",
            "parameters": {
                "type": "object"
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_ovs_ports",
            "description": "List all OVS ports and their details using 'ovs-vsctl list interface'. This shows interface names, MAC addresses, types, and status. Use this to find specific interfaces like tap devices or physical ports.",
            "parameters": {
                "type": "object"
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
            "name": "trace_ovs_flow",
            "description": "Trace a packet through OVS OpenFlow tables using 'ovs-appctl ofproto/trace'. This simulates packet processing through the physical datapath, showing which flows match and what actions are taken. Use this to debug why packets are dropped or forwarded incorrectly at the OVS level. The flow parameter should specify packet characteristics extracted from captured traffic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bridge": {
                        "type": "string",
                        "description": "OVS bridge name to trace on (e.g., 'br-int')"
                    },
                    "flow": {
                        "type": "string",
                        "description": "Flow specification describing the packet to trace. Format: 'in_port=X,dl_src=MAC,dl_dst=MAC,dl_type=0x0800,nw_src=IP,nw_dst=IP,nw_proto=1' (for ICMP) or similar. Extract these values from captured packets."
                    }
                },
                "required": ["bridge", "flow"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "trace_ovn_packet",
            "description": "Trace a packet through OVN logical topology using 'ovn-trace'. This simulates packet processing through the logical network (switches, routers, ACLs) and shows the logical path and any drops. Essential for finding which logical ACL or router rule is blocking traffic. The datapath is the logical switch/router name, and inport is the logical port name (both visible in 'ovn-nbctl show').",
            "parameters": {
                "type": "object",
                "properties": {
                    "datapath": {
                        "type": "string",
                        "description": "Logical datapath (switch or router name/UUID) from 'ovn-nbctl show'. Example: 'neutron-20e32985-7621-419b-b602-de90bae0ef73'"
                    },
                    "inport": {
                        "type": "string",
                        "description": "Ingress logical port name/UUID from 'ovn-nbctl show'. Example: '6335a75c-5c5c-4c88-940f-dc8acd018396'"
                    },
                    "packet": {
                        "type": "string",
                        "description": "Packet specification in OVN format. Example: 'inport==\"PORT_NAME\" && eth.src==MAC && eth.dst==MAC && ip4.src==IP && ip4.dst==IP && ip.ttl==64 && icmp4' for ICMP packets. Adapt based on protocol."
                    }
                },
                "required": ["datapath", "inport", "packet"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_ovn_logs",
            "description": "Search OVN controller logs for errors, warnings, or specific patterns. OVN logs use specific tags: 'ERR' for errors, 'WARN' for warnings, 'INFO' for informational messages. The ovn-controller runs on compute nodes and its logs contain critical information about packet processing issues, flow installation failures, and connectivity problems. Use this to find error messages that explain why traffic is failing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Pattern to search for in logs. Common patterns: 'ERR' (errors), 'WARN' (warnings), 'drop', 'failed', 'ERR|WARN' (errors or warnings), or specific port/IP/MAC addresses. Case-insensitive grep pattern."
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Number of recent log lines to search (default: 100, max: 1000). Use larger values for historical issues."
                    }
                },
                "required": ["pattern"]
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
            # For commands like tcpdump that write to both stdout and stderr
            # Combine both (packet details in stdout, summary in stderr)
            parts = []
            if result.stdout:
                parts.append(result.stdout)
            if result.stderr:
                parts.append(result.stderr)
            output = '\n'.join(parts) if parts else None
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

    # Get properties (may not exist for parameter-less tools)
    properties = tool_schema["parameters"].get("properties", {})

    # Check required parameters
    required_params = tool_schema["parameters"].get("required", [])
    for param in required_params:
        if param not in tool_args:
            return False, f"Missing required parameter: {param}"

    # Check for unexpected parameters (only if properties are defined)
    if properties:
        valid_params = properties.keys()
        for param in tool_args.keys():
            if param not in valid_params:
                return False, f"Unexpected parameter: {param}"

        # Type checking with auto-conversion for common LLM mistakes
        for param_name, param_value in tool_args.items():
            expected_type = properties[param_name].get("type")

            if expected_type == "string":
                if not isinstance(param_value, str):
                    # Try to convert to string
                    tool_args[param_name] = str(param_value)

            elif expected_type == "integer":
                if not isinstance(param_value, int):
                    # Try to convert string to int (common LLM mistake)
                    try:
                        tool_args[param_name] = int(param_value)
                    except (ValueError, TypeError):
                        return False, f"Parameter '{param_name}' must be an integer (got: {param_value})"

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


def _execute_trace_ovs_flow(bridge: str, flow: str) -> str:
    """
    Execute ovs-appctl ofproto/trace to trace a packet through OVS.

    Args:
        bridge: OVS bridge name
        flow: Flow specification (e.g., "in_port=1,icmp,nw_src=10.0.0.1,nw_dst=10.0.0.2")

    Returns:
        Trace output or error message
    """
    cmd = ["sudo", "ovs-appctl", "ofproto/trace", bridge, flow]
    return _run_command(cmd)


def _execute_trace_ovn_packet(datapath: str, inport: str, packet: str) -> str:
    """
    Execute ovn-trace to trace a packet through OVN logical topology.

    Args:
        datapath: Logical datapath (switch/router name or UUID)
        inport: Ingress logical port name or UUID
        packet: Packet specification in OVN match format

    Returns:
        Trace output or error message
    """
    # Build ovn-trace command
    # --minimal: Show minimal output without full details
    # Use full packet specification format
    cmd = ["sudo", "ovn-trace", "--minimal", datapath, packet]
    return _run_command(cmd)


def _execute_search_ovn_logs(pattern: str, lines: int = DEFAULT_LOG_LINES) -> str:
    """
    Search OVN controller logs for specific patterns.

    Args:
        pattern: Pattern to search for (grep syntax)
        lines: Number of recent log lines to search

    Returns:
        Matching log lines or error message
    """
    import os

    # Sanitize and limit lines to reasonable range
    lines = max(1, min(lines, MAX_LOG_LINES))

    # Find the log file (try different locations)
    log_file = None
    for path in OVN_CONTROLLER_LOG_PATHS:
        if os.path.exists(path):
            log_file = path
            break

    if not log_file:
        # Try journalctl as fallback
        cmd = ["sudo", "journalctl", "-u", "ovn-controller", "-n", str(lines), "--no-pager"]
        print(f"--- [Tool] Log file not found, using journalctl ---")
        result = _run_command(cmd)

        # Now grep the result for the pattern
        if result and not result.startswith("Error:"):
            matching_lines = []
            for line in result.split('\n'):
                if pattern.lower() in line.lower():
                    matching_lines.append(line)

            if matching_lines:
                return '\n'.join(matching_lines)
            else:
                return f"No matches found for pattern '{pattern}' in recent {lines} log entries."
        return result

    # Use tail + grep on log file
    # tail -n <lines> <file> | grep -i <pattern>
    print(f"--- [Tool] Searching {log_file} for '{pattern}' ---")
    cmd = f"sudo tail -n {lines} {log_file} | grep -i '{pattern}'"

    try:
        result = subprocess.run(
            cmd,
            shell=True,  # Need shell for pipe
            capture_output=True,
            text=True,
            check=False,
            timeout=TIMEOUT_STANDARD
        )

        print(f"--- [Tool] Exit code: {result.returncode} ---")

        if result.stdout:
            return result.stdout
        elif result.returncode == 1:
            # grep returns 1 when no matches found
            return f"No matches found for pattern '{pattern}' in recent {lines} log lines from {log_file}."
        else:
            return f"Error searching logs: {result.stderr or 'Unknown error'}"

    except subprocess.TimeoutExpired:
        return f"Error: Log search timed out after {TIMEOUT_STANDARD} seconds."
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"


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
    # -l: Line buffered output (important for subprocess capture)
    # -n: Don't resolve hostnames
    # -v: Verbose output
    # -e: Print link-level header
    # -c: Capture count
    cmd = ["sudo", "tcpdump", "-l", "-n", "-v", "-e", "-c", str(count), "-i", interface]

    # Add filter if provided - split into separate args like a shell would
    if filter_expr:
        # Split filter expression into separate arguments
        # This ensures proper parsing by tcpdump (e.g., "host 10.0.0.1 and icmp" -> ["host", "10.0.0.1", "and", "icmp"])
        cmd.extend(filter_expr.split())

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


def _call_trace_ovs_flow(args: Dict[str, Any]) -> str:
    """Wrapper for trace_ovs_flow."""
    bridge = args.get("bridge")
    flow = args.get("flow")
    return _execute_trace_ovs_flow(bridge, flow)


def _call_trace_ovn_packet(args: Dict[str, Any]) -> str:
    """Wrapper for trace_ovn_packet."""
    datapath = args.get("datapath")
    inport = args.get("inport")
    packet = args.get("packet")
    return _execute_trace_ovn_packet(datapath, inport, packet)


def _call_search_ovn_logs(args: Dict[str, Any]) -> str:
    """Wrapper for search_ovn_logs."""
    pattern = args.get("pattern")
    lines = args.get("lines", DEFAULT_LOG_LINES)
    return _execute_search_ovn_logs(pattern, lines)


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
    "trace_ovs_flow": _call_trace_ovs_flow,
    "trace_ovn_packet": _call_trace_ovn_packet,
    "search_ovn_logs": _call_search_ovn_logs,
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
