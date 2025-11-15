# OVNator - OVN/Neutron Troubleshooting Agent

An AI-powered troubleshooting assistant for OVN (Open Virtual Network) and OpenStack Neutron connectivity issues.

## Overview

OVNator is an intelligent agent that helps diagnose network connectivity problems in OpenStack Neutron environments using OVN. It leverages LLM reasoning to systematically investigate issues by:

- Discovering both logical (OVN) and physical (OVS) network topology
- Correlating VMs to their tap devices and network ports
- Capturing packets on relevant interfaces
- Tracing packet paths through the network
- Identifying root causes of connectivity failures

## Features

### Current Tools

1. **`get_ovn_logical_topology`** - Displays OVN logical switches, routers, ports, and NAT rules
2. **`get_ovs_topology`** - Shows OVS bridges, physical interfaces, and tap devices
3. **`get_ovs_ports`** - Lists detailed interface information (MACs, types, status)
4. **`dump_ovs_flows`** - Dumps OpenFlow rules from an OVS bridge
5. **`trace_ovs_flow`** - Traces packet processing through OVS OpenFlow tables (physical layer)
6. **`trace_ovn_packet`** - Traces packet processing through OVN logical topology (logical layer)
7. **`search_ovn_logs`** - Searches OVN controller logs for errors, warnings, or specific patterns
8. **`capture_packets`** - Captures packets on specified interfaces with BPF filters

### Planned Tools

- ACL and security group inspection
- Port binding queries
- Connection tracking (conntrack) inspection

## Prerequisites

- Python 3.8+
- OVN/OVS installed on the compute node
- LlamaStack server running with access to an LLM (e.g., Llama 3.1)
- `sudo` privileges for network commands
- Tools: `ovn-nbctl`, `ovs-vsctl`, `tcpdump`

## Installation

1. Clone or copy the repository:
   ```bash
   cd /home/ubuntu/ovnator
   ```

2. Create and activate virtual environment:
   ```bash
   python3 -m venv venv_ovnator
   source venv_ovnator/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure the LlamaStack server URL in `agent.py`:
   ```python
   LLAMASTACK_SERVER_URL = "http://your-server:8321"
   MODEL_NAME = "ollama/llama3.1:8b"
   ```

## Usage

### Starting the Agent

```bash
source venv_ovnator/bin/activate
python3 agent.py
```

### Example Queries

**Simple Informational:**
- "Do I have any routers?"
- "Show me the OVS topology"
- "List all tap devices on br-int"
- "Show me the OpenFlow flows for br-int"

**Smart IP Diagnostics (Recommended):**
Just provide the IP - the agent will automatically perform complete diagnostics:
- "Troubleshoot 10.0.0.48"
- "Why can't I reach 172.24.5.38?"
- "Diagnose connectivity for 10.0.0.1"
- "What's wrong with 192.168.1.100?"

The agent will automatically:
1. Find the logical port for that IP
2. Identify the tap device
3. Capture packets
4. Trace through OVS and OVN
5. Check logs for errors
6. Provide root cause analysis

**Manual Step-by-Step (If needed):**
- "Find the tap device for VM with IP 10.0.0.48"
- "Capture 5 ICMP packets on tap6335a75c-5c"
- "Trace an ICMP packet from 10.0.0.48 to 10.0.0.1 through both OVS and OVN"
- "Search for errors in the OVN controller logs"

**Advanced Workflows:**
- "Capture a packet, extract its details, and trace it through the entire stack"
- "Compare physical and logical packet paths for ICMP between two VMs"
- "Find all ERR or WARN messages in the last 500 log lines"

## Architecture

```
┌─────────────┐
│   User      │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌──────────────┐
│   Agent     │────▶│ LlamaStack   │
│  (agent.py) │◀────│   Server     │
└──────┬──────┘     └──────────────┘
       │
       ▼
┌─────────────┐     ┌──────────────┐
│   Tools     │────▶│  OVN/OVS     │
│ (tools.py)  │     │  Commands    │
└─────────────┘     └──────────────┘
```

### ReAct Loop

The agent follows a Reasoning and Acting (ReAct) pattern:

1. **Reason**: LLM decides what action to take
2. **Act**: Execute tool to gather information
3. **Observe**: Feed tool output back to LLM
4. **Repeat**: Continue until problem is solved or answer is found

## Code Structure

```
ovnator/
├── agent.py          # Main agent loop and LLM interaction
├── tools.py          # Tool definitions and execution
├── requirements.txt  # Python dependencies
└── README.md         # This file
```

### Key Components

#### `agent.py`
- System prompt with OVN/Neutron troubleshooting methodology
- ReAct loop implementation
- LlamaStack client integration
- Conversation history management

#### `tools.py`
- Tool schema definitions (OpenAI function calling format)
- Command execution with error handling
- Type validation and sanitization
- Common utilities for subprocess execution

## Configuration

### Constants in `tools.py`

```python
TIMEOUT_STANDARD = 10           # Standard command timeout (seconds)
TIMEOUT_PACKET_CAPTURE = 30     # Packet capture timeout (seconds)
MAX_PACKET_COUNT = 100          # Maximum packets to capture
DEFAULT_PACKET_COUNT = 10       # Default packet count
```

### Environment Variables

The agent runs commands with `sudo`. Ensure the user running the agent has passwordless sudo access for:
- `ovn-nbctl`
- `ovs-vsctl`
- `tcpdump`

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for detailed troubleshooting guide including:
- Fixing "Unknown LLM action: None" errors
- Handling JSON parse errors
- Model selection guidance
- Performance optimization

### Common Issues

#### "Unknown LLM action: None"
**Cause:** Small model (Llama 3.1 8B) overwhelmed by large tool outputs

**Solution:** Use a larger model like Gemini Pro, Claude, or Llama 3.1 70B

**Quick fix:** Enable DEBUG_MODE in agent.py to see what the LLM actually returned

#### Connection Issues

**Problem**: Cannot connect to LlamaStack server
```
FATAL: Could not create LlamaStack client...
```

**Solution**:
- Verify LlamaStack server is running
- Check LLAMASTACK_SERVER_URL in agent.py
- Test connectivity: `curl http://your-server:8321/health`

### Permission Issues

**Problem**: Permission denied errors when running tools
```
Error: Permission denied running command...
```

**Solution**:
- Ensure sudo access is configured
- Add user to required groups
- Check file permissions on OVN/OVS sockets

### Tool Not Found

**Problem**: Command not found errors
```
Error: Command not found: ovn-nbctl
```

**Solution**:
- Install OVN/OVS packages
- Add binaries to PATH
- Verify installation: `which ovn-nbctl`

## Development

### Adding New Tools

The codebase uses a **tool registry pattern** for clean, scalable tool management.

**Step 1:** Add schema to `TOOL_SCHEMAS` in `tools.py`:
```python
{
    "type": "function",
    "function": {
        "name": "your_tool_name",
        "description": "What this tool does",
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "Parameter description"
                }
            },
            "required": ["param1"]
        }
    }
}
```

**Step 2:** Implement the tool function:
```python
def _execute_your_tool(param1: str) -> str:
    """Execute your tool."""
    cmd = ["sudo", "your-command", param1]
    return _run_command(cmd)
```

**Step 3:** Create a wrapper function:
```python
def _call_your_tool(args: Dict[str, Any]) -> str:
    """Wrapper for your_tool_name."""
    param1 = args.get("param1")
    return _execute_your_tool(param1)
```

**Step 4:** Register in `TOOL_REGISTRY`:
```python
TOOL_REGISTRY = {
    "get_ovn_logical_topology": _call_ovn_logical_topology,
    "get_ovs_topology": _call_ovs_topology,
    "get_ovs_ports": _call_ovs_ports,
    "capture_packets": _call_capture_packets,
    "your_tool_name": _call_your_tool,  # Add your tool here
}
```

That's it! The registry pattern automatically handles routing without modifying `execute_tool()`.

### Testing

Test individual tools:
```python
from tools import execute_tool

result = execute_tool("get_ovn_logical_topology", {})
print(result)
```

Test the agent with specific queries:
```bash
echo "Your question here" | python3 agent.py
```

## Contributing

Improvements welcome! Areas for contribution:
- Additional OVN/OVS tools
- Better packet parsing and analysis
- Flow rule inspection
- ACL debugging capabilities
- Output formatting and visualization

## License

This project is for internal use in OpenStack environments.

## Support

For issues or questions, consult OpenStack Neutron and OVN documentation:
- [OVN Documentation](https://www.ovn.org/)
- [OpenStack Neutron](https://docs.openstack.org/neutron/)
- [OVS Manual](http://www.openvswitch.org/support/dist-docs/)
