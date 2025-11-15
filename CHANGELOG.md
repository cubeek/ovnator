# Changelog

## Log Search Tool (Latest)

### Features Added

**OVN Controller Log Analysis**
- Added `search_ovn_logs` tool to search ovn-controller logs for errors, warnings, and specific patterns
- Supports multiple log locations: `/var/log/ovn/ovn-controller.log`, systemd journal fallback
- Understands OVN log format with ERR, WARN, INFO tags

**Key Capabilities:**
- Search for errors: `search_ovn_logs("ERR")`
- Search for warnings: `search_ovn_logs("WARN")`
- Combined search: `search_ovn_logs("ERR|WARN")`
- Search for specific IPs/MACs/ports in logs
- Configurable search window (default: 100 lines, max: 1000)

**Usage Examples:**
```
"Search for errors in OVN logs"
"Check if there are warnings about port 10.0.0.48"
"Find all ERR or WARN messages in last 500 lines"
```

**Integration:**
- Updated troubleshooting methodology to include log checking (Step 7)
- Helps correlate errors with packet drops and connectivity issues
- Essential for finding flow installation failures and ACL misconfigurations

**Registry Count:** Now 8 tools total

## Packet Tracing Tools

### Major Features Added

**Complete Packet Tracing Capability**
Added two critical tracing tools that enable end-to-end packet path analysis:

**1. `trace_ovs_flow` - Physical Layer Tracing**
- Command: `ovs-appctl ofproto/trace <bridge> <flow>`
- Simulates packet processing through OVS OpenFlow tables
- Shows which flows match, what actions are taken
- Identifies drops, rewrites, and forwarding decisions at the physical layer
- Example: `trace_ovs_flow br-int "in_port=1,icmp,nw_src=10.0.0.48,nw_dst=10.0.0.1"`

**2. `trace_ovn_packet` - Logical Layer Tracing**
- Command: `ovn-trace <datapath> <packet-spec>`
- Simulates packet processing through OVN logical topology
- Shows ACL evaluations, routing decisions, logical forwarding
- Identifies which logical ACL or router rule causes drops
- Example: `trace_ovn_packet neutron-xxx 'inport=="port-uuid" && ip4.src==10.0.0.48 && icmp4'`

**Enhanced Troubleshooting Methodology**
- Updated agent system prompt with comprehensive 7-step troubleshooting workflow
- Includes detailed guidance on extracting packet info and building trace specifications
- Emphasizes two-level debugging (physical AND logical)

**Usage Pattern:**
1. Capture packet with `capture_packets` to get MAC/IP details
2. Trace physical path with `trace_ovs_flow` using captured packet details
3. Trace logical path with `trace_ovn_packet` using logical port info
4. Compare both traces to find discrepancies

**Registry Count:** Now 7 tools total

## New Tool: dump_ovs_flows

### Features Added

**OpenFlow Flow Inspection**
- Added `dump_ovs_flows` tool to dump OpenFlow rules from OVS bridges
- Command: `ovs-ofctl dump-flows <bridge>`
- Essential for understanding packet processing and debugging drops
- Shows flow tables, match criteria, actions, and statistics

**Usage:**
```python
# Ask the agent:
"Show me the OpenFlow flows for br-int"
"Dump flows on br-ex bridge"
```

**Implementation:**
- Schema defined in `TOOL_SCHEMAS`
- Implementation in `_execute_dump_ovs_flows()`
- Wrapper in `_call_dump_ovs_flows()`
- Registered in `TOOL_REGISTRY`

**Registry Count:** Now 5 tools total

## Tool Registry Pattern

### Architecture Improvements

**Eliminated If-Elif Chain**
- Replaced long if-elif chain in `execute_tool()` with a clean registry pattern
- Created `TOOL_REGISTRY` dictionary mapping tool names to functions
- Tool routing now uses: `TOOL_REGISTRY[tool_name](tool_args)`

**Benefits:**
- ✅ More scalable - adding new tools requires only registry update
- ✅ Cleaner code - no modification to `execute_tool()` function
- ✅ Better maintainability - single place to see all tools
- ✅ Easier testing - can iterate over registry to test all tools

**Implementation:**
```python
TOOL_REGISTRY = {
    "get_ovn_logical_topology": _call_ovn_logical_topology,
    "get_ovs_topology": _call_ovs_topology,
    "get_ovs_ports": _call_ovs_ports,
    "capture_packets": _call_capture_packets,
}
```

## Refactoring and Polish

### Code Quality Improvements

#### `tools.py`
**Eliminated Code Duplication**
- Extracted common subprocess execution logic into `_run_command()` helper function
- Reduced 3 nearly-identical functions to use a single shared implementation
- Removed ~100 lines of duplicated code

**Added Type Hints**
- Added type annotations for all functions
- Improved IDE support and code documentation
- Better error detection during development

**Configuration Management**
- Extracted magic numbers into named constants at module level:
  - `TIMEOUT_STANDARD = 10`
  - `TIMEOUT_PACKET_CAPTURE = 30`
  - `MIN_PACKET_COUNT = 1`
  - `MAX_PACKET_COUNT = 100`
  - `DEFAULT_PACKET_COUNT = 10`
  - `MAX_STDERR_DISPLAY = 200`

**Better Error Handling**
- Added specific exception handling for `FileNotFoundError` and `PermissionError`
- More descriptive error messages with context
- Consistent error formatting across all tools

**Improved Documentation**
- Added comprehensive module docstring
- Documented all function parameters and return values
- Clear separation of concerns with section comments

#### `agent.py`
**Improved Structure**
- Extracted helper functions for better modularity:
  - `initialize_client()` - Client setup with error handling
  - `handle_tool_call()` - Tool execution logic
  - `handle_final_answer()` - Answer presentation
  - `process_llm_response()` - Response routing
  - `run_agent_loop()` - ReAct loop implementation

**Added Type Hints**
- Full type annotations for all functions
- Better code clarity and maintainability

**Configuration Management**
- Extracted constants:
  - `LLAMASTACK_SERVER_URL`
  - `MODEL_NAME`
  - `JSON_RESPONSE_FORMAT`

**Better Error Handling**
- Separated client initialization errors
- More graceful handling of LLM errors
- Clear error messages for debugging

**Improved Documentation**
- Added comprehensive module docstring
- Documented ReAct pattern implementation
- Clear function responsibilities

#### `README.md`
**Created Comprehensive Documentation**
- Project overview and features
- Installation instructions
- Usage examples
- Architecture diagrams
- Code structure explanation
- Configuration guide
- Troubleshooting section
- Development guide for adding new tools

### Functional Improvements

**Tools Added**
- `get_ovn_logical_topology` - OVN logical network topology
- `get_ovs_topology` - OVS physical topology
- `get_ovs_ports` - Detailed interface information
- `capture_packets` - Packet capture with filters

**Enhanced System Prompt**
- Added systematic troubleshooting methodology
- Included key OVN/Neutron concepts
- Better guidance on tool usage
- Clear correlation between logical and physical topology

**Better Tool Descriptions**
- More detailed parameter descriptions
- Usage examples in descriptions
- Clear requirements and constraints

### Testing Improvements

**Verified Functionality**
- All tools execute correctly
- Agent responds appropriately to queries
- Error handling works as expected
- LlamaStack integration maintained

## Initial Implementation

### Core Features
- ReAct loop for reasoning and acting
- LlamaStack integration
- Basic OVN/OVS tool support
- JSON-based tool calling
- Conversation history management

### Tools
- Initial implementation of `get_ovn_logical_topology`
- Basic subprocess execution
- Simple error handling

### Integration
- LlamaStack client setup
- Message formatting for tool calls
- Tool call ID generation for proper message threading
