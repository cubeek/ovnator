"""
OVN/Neutron Troubleshooting Agent

This agent uses LlamaStack to interact with OVN/OVS tools and diagnose
network connectivity issues in OpenStack Neutron environments.
"""

import json
import sys
import uuid
from typing import List, Dict, Any
from llama_stack_client import LlamaStackClient, LlamaStackClientError

# Import tool functionality
from tools import get_tools_description, execute_tool

# --- Configuration ---

# The URL of your LlamaStack server
LLAMASTACK_SERVER_URL = "http://10.40.128.51:8321"

# The model to use
MODEL_NAME = "ollama/llama3.1:8b"

# JSON response format requirement
JSON_RESPONSE_FORMAT = {"type": "json_object"}


# --- System Prompt ---

def build_system_prompt() -> str:
    """
    Build the system prompt dynamically including tool schemas.

    Returns:
        System prompt string with embedded tool descriptions
    """
    return f"""
You are a senior network engineer specializing in OVN (Open Virtual Network) and OVS (Open vSwitch) in an OpenStack Neutron environment. Your mission is to help analyze and troubleshoot network configurations on this compute node.

**YOUR ROLE:**
- Answer questions about the network topology, configuration, and connectivity
- **ALWAYS use available tools to gather current information** - do not make assumptions
- When asked to troubleshoot, follow a systematic approach to find root causes
- Recognize when configurations are correct and working as expected
- Provide clear, accurate information based on tool outputs

**WHEN TROUBLESHOOTING, USE THIS METHODOLOGY:**
1.  **DISCOVER TOPOLOGY:** First, understand both logical (OVN) and physical (OVS) topology:
    - Use `get_ovn_logical_topology` to see logical switches, routers, and ports
    - Use `get_ovs_topology` to see OVS bridges, interfaces, and tap devices
    - Use `get_ovs_ports` to get detailed interface information
2.  **IDENTIFY:** Map the problem to specific components (VMs, IPs, ports, interfaces).
3.  **CAPTURE:** Use `capture_packets` on relevant interfaces (tap devices, physical ports) to see actual traffic.
4.  **TRACE:** Trace the logical packet path to see where it *should* go.
5.  **VERIFY:** Check the local OpenFlow rules to see what is *actually* happening.
6.  **CONCLUDE:** State the root cause and the specific rule (ACL, flow, etc.) causing the issue.

---
**KEY OVN/NEUTRON CONCEPTS:**
* **br-int:** The main OVS integration bridge on the compute node. All VM tap devices connect here.
* **Logical Topology:** Neutron networks map to OVN logical switches, routers map to logical routers.
* **ovn-trace:** Simulates a packet's path through the *logical* topology. A failed trace will end in `drop` and show the *exact* logical ACL that caused it.
* **Port Bindings:** Map logical ports to physical compute nodes and interfaces.
* **Tap Devices:** VMs connect via tap interfaces (e.g., tap12345678, tap6335a75c-5c) on br-int. The tap name is derived from the logical port UUID.
* **Correlation:** To troubleshoot a VM's connectivity:
  1. Find the VM's IP in `ovn-nbctl show` to get its logical port UUID
  2. Find the corresponding tap device (first 11 chars of UUID) in `ovs-vsctl show`
  3. Capture packets on that tap device to see actual traffic

---
{get_tools_description()}
---
**IMPORTANT:** Before answering any question about the current state of the system, you MUST first call the appropriate tool to gather real-time information. Do not rely on assumptions or prior knowledge.

**RESPONSE FORMAT:**
You MUST respond in one of two valid JSON formats. Do not add any other text.

1.  **To call a tool:**
    {{"action": "call_tool", "tool_name": "tool_name", "tool_args": {{"arg1": "value1"}}}}

2.  **To give the final answer:**
    - For informational queries or when everything is working correctly:
      {{"action": "final_answer", "content": "Clear explanation of what was found/analyzed"}}

    - For troubleshooting when an issue is found:
      {{"action": "final_answer", "content": "Root Cause: [specific issue found]\\n\\nRecommendation: [how to fix it]"}}
"""


# --- Agent Logic ---

def initialize_client() -> LlamaStackClient:
    """
    Initialize the LlamaStack client.

    Returns:
        Initialized LlamaStackClient

    Raises:
        SystemExit: If client initialization fails
    """
    try:
        client = LlamaStackClient(base_url=LLAMASTACK_SERVER_URL)
        print(f"Connected to LlamaStack server at {LLAMASTACK_SERVER_URL}")
        return client
    except Exception as e:
        print(f"FATAL: Could not create LlamaStack client. Is the server running at {LLAMASTACK_SERVER_URL}?")
        print(f"Error details: {e}")
        sys.exit(1)


def handle_tool_call(messages: List[Dict[str, Any]], assistant_message: Any,
                     llm_decision: Dict[str, Any]) -> None:
    """
    Handle a tool call from the LLM.

    Args:
        messages: Conversation history
        assistant_message: Raw assistant message from LLM
        llm_decision: Parsed JSON decision from LLM
    """
    tool_name = llm_decision.get("tool_name")
    tool_args = llm_decision.get("tool_args", {})

    # Generate a unique tool_call_id for this execution
    tool_call_id = f"call_{uuid.uuid4().hex[:24]}"

    # Convert assistant message to dict and add tool_calls metadata
    # This ensures the message history is properly formatted for LlamaStack
    assistant_msg_dict = {
        "role": "assistant",
        "content": assistant_message.content,
        "tool_calls": [{
            "id": tool_call_id,
            "type": "function",
            "function": {
                "name": tool_name,
                "arguments": json.dumps(tool_args)
            }
        }]
    }
    messages.append(assistant_msg_dict)

    # Execute the tool
    tool_output = execute_tool(tool_name, tool_args)

    # Add the tool's output to history
    messages.append({
        "role": "tool",
        "content": tool_output,
        "tool_call_id": tool_call_id
    })


def handle_final_answer(messages: List[Dict[str, Any]], assistant_message: Any,
                       llm_decision: Dict[str, Any]) -> bool:
    """
    Handle a final answer from the LLM.

    Args:
        messages: Conversation history
        assistant_message: Raw assistant message from LLM
        llm_decision: Parsed JSON decision from LLM

    Returns:
        True to indicate the conversation turn is complete
    """
    messages.append({"role": "assistant", "content": assistant_message.content})
    answer = llm_decision.get("content", "No content provided.")
    print(f"\n--- [Agent's Final Answer] ---\n{answer}")
    return True


def process_llm_response(messages: List[Dict[str, Any]], assistant_message: Any) -> bool:
    """
    Process the LLM response and take appropriate action.

    Args:
        messages: Conversation history
        assistant_message: Raw assistant message from LLM

    Returns:
        True if conversation turn is complete, False to continue
    """
    # Parse the LLM's JSON instruction
    try:
        llm_decision = json.loads(assistant_message.content)
    except json.JSONDecodeError:
        print(f"--- [Agent] Error: LLM returned invalid JSON. Retrying. ---")
        messages.append({"role": "assistant", "content": assistant_message.content})
        messages.append({"role": "user", "content": "That was not valid JSON. Please respond *only* with the JSON format specified."})
        return False

    # Route based on action
    action = llm_decision.get("action")

    if action == "call_tool":
        handle_tool_call(messages, assistant_message, llm_decision)
        return False  # Continue the loop

    elif action == "final_answer":
        return handle_final_answer(messages, assistant_message, llm_decision)

    else:
        # Unknown action
        messages.append({"role": "assistant", "content": assistant_message.content})
        print(f"--- [Agent] Error: Unknown LLM action: {action} ---")
        return True  # End this conversation turn


def run_agent_loop(client: LlamaStackClient, messages: List[Dict[str, Any]]) -> None:
    """
    Run the main agent reasoning loop (ReAct pattern).

    Args:
        client: LlamaStack client
        messages: Conversation history
    """
    while True:
        try:
            print("--- [Agent] Asking LLM for next step... ---")

            # Call the LLM
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                response_format=JSON_RESPONSE_FORMAT
            )

            assistant_message = response.choices[0].message

            # Process the response and determine if we should continue
            should_break = process_llm_response(messages, assistant_message)
            if should_break:
                break

        except LlamaStackClientError as e:
            print(f"--- [Agent] Error communicating with LlamaStack server: {e} ---")
            break
        except Exception as e:
            print(f"--- [Agent] An unexpected error occurred in the main loop: {e} ---")
            break


def main() -> None:
    """Main entry point for the agent."""
    client = initialize_client()

    # Initialize the conversation history with the system prompt
    messages = [{"role": "system", "content": build_system_prompt()}]

    # Start the conversation
    print("--- OVN Troubleshooting Agent ---")
    print("Type 'exit' to quit.")

    while True:
        user_query = input("\n[You] ")
        if user_query.lower() == 'exit':
            break

        messages.append({"role": "user", "content": user_query})
        run_agent_loop(client, messages)


if __name__ == "__main__":
    main()
