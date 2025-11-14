"""
OVN/OVS Troubleshooting Tools

This module contains all tool definitions, schemas, validation, and execution logic
for the OVN troubleshooting agent.
"""

import subprocess

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
    }
]


def get_tools_description():
    """
    Generate a human-readable description of available tools from schemas.

    Returns:
        str: Formatted description of all available tools
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


def validate_tool_call(tool_name, tool_args):
    """
    Validate tool call against schema.

    Args:
        tool_name (str): Name of the tool to validate
        tool_args (dict): Arguments provided for the tool

    Returns:
        tuple: (is_valid: bool, error_message: str or None)
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

    # Type checking (basic)
    for param_name, param_value in tool_args.items():
        expected_type = tool_schema["parameters"]["properties"][param_name].get("type")
        if expected_type == "string" and not isinstance(param_value, str):
            return False, f"Parameter '{param_name}' must be a string"
        elif expected_type == "integer" and not isinstance(param_value, int):
            return False, f"Parameter '{param_name}' must be an integer"

    return True, None


# --- Tool Implementations ---

def _execute_ovn_logical_topology():
    """
    Execute ovn-nbctl show to get logical topology.

    Returns:
        str: Command output or error message
    """
    cmd = ["ovn-nbctl", "show"]
    print(f"--- [Tool] Running command: {' '.join(cmd)} ---")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=10
        )
        return result.stdout or "Command executed successfully (no output)."
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out."
    except Exception as e:
        return f"Error: {e}"


# --- Main Tool Executor ---

def execute_tool(tool_name, tool_args):
    """
    Execute a tool with validation.

    Args:
        tool_name (str): Name of the tool to execute
        tool_args (dict): Arguments for the tool

    Returns:
        str: Tool output or error message
    """
    print(f"--- [Tool] Executing: {tool_name} ---")

    # Validate the tool call
    is_valid, error = validate_tool_call(tool_name, tool_args)
    if not is_valid:
        return f"Error: Tool validation failed: {error}"

    # Route to the appropriate tool implementation
    if tool_name == "get_ovn_logical_topology":
        return _execute_ovn_logical_topology()

    # This shouldn't happen if validation works correctly
    return f"Error: Tool '{tool_name}' is defined but not implemented"
