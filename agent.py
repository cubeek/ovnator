import json
import sys
import uuid
from llama_stack_client import LlamaStackClient, LlamaStackClientError

# Import tool functionality
from tools import get_tools_description, execute_tool

# --- 1. Agent Configuration ---

# The URL of your LlamaStack server (the container we just ran)
LLAMASTACK_SERVER_URL = "http://10.40.128.51:8321"

# The model to use (the one you pulled on the host)
MODEL_NAME = "ollama/llama3.1:8b"

# --- 2. System Prompt ---

def build_system_prompt():
    """Build the system prompt dynamically including tool schemas."""
    return f"""
You are a senior network engineer specializing in OVN (Open Virtual Network) and OVS (Open vSwitch) in an OpenStack Neutron environment. Your mission is to help analyze and troubleshoot network configurations on this compute node.

**YOUR ROLE:**
- Answer questions about the network topology, configuration, and connectivity
- **ALWAYS use available tools to gather current information** - do not make assumptions
- When asked to troubleshoot, follow a systematic approach to find root causes
- Recognize when configurations are correct and working as expected
- Provide clear, accurate information based on tool outputs

**WHEN TROUBLESHOOTING, USE THIS METHODOLOGY:**
1.  **DISCOVER TOPOLOGY:** First, understand the logical network topology (switches, routers, ports).
2.  **IDENTIFY:** Get the OVN/OVS context for the components (VMs, IPs, ports).
3.  **TRACE:** Trace the logical packet path to see where it *should* go.
4.  **VERIFY:** Check the local OpenFlow rules to see what is *actually* happening.
5.  **CONCLUDE:** State the root cause and the specific rule (ACL, flow, etc.) causing the issue.

---
**KEY OVN/NEUTRON CONCEPTS:**
* **br-int:** The main OVS integration bridge on the compute node.
* **Logical Topology:** Neutron networks map to OVN logical switches, routers map to logical routers.
* **ovn-trace:** Simulates a packet's path through the *logical* topology. A failed trace will end in `drop` and show the *exact* logical ACL that caused it.
* **Port Bindings:** Map logical ports to physical compute nodes and interfaces.
* **Tap Devices:** VMs connect via tap interfaces (e.g., tap12345678) on br-int.

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

# --- 3. Main Agent Loop ---

def main():
    try:
        client = LlamaStackClient(base_url=LLAMASTACK_SERVER_URL)
        print(f"Connected to LlamaStack server at {LLAMASTACK_SERVER_URL}")
    except Exception as e:
        print(f"FATAL: Could not create LlamaStack client. Is the server running at {LLAMASTACK_SERVER_URL}?")
        print(f"Error details: {e}")
        sys.exit(1)

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

        # This is the "Reason-Act" loop
        while True:
            try:
                print("--- [Agent] Asking LLM for next step... ---")

                # 1. REASON: Call the LLM (MCP Server)
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    response_format={"type": "json_object"}, # Ask for JSON
                )

                assistant_message = response.choices[0].message

                # 2. PARSE: Decode the LLM's JSON instruction
                try:
                    llm_decision = json.loads(assistant_message.content)
                except json.JSONDecodeError:
                    print(f"--- [Agent] Error: LLM returned invalid JSON. Retrying. ---")
                    messages.append({"role": "assistant", "content": assistant_message.content})
                    messages.append({"role": "user", "content": "That was not valid JSON. Please respond *only* with the JSON format specified."})
                    continue # Ask the LLM to try again

                # 3. ACT: Decide what to do based on the JSON
                if llm_decision.get("action") == "call_tool":
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

                    # Run the tool
                    tool_output = execute_tool(tool_name, tool_args)

                    # 4. OBSERVE: Add the tool's output to history
                    messages.append({
                        "role": "tool",
                        "content": tool_output,
                        "tool_call_id": tool_call_id
                    })
                    # Loop continues, sending the new tool output to the LLM

                elif llm_decision.get("action") == "final_answer":
                    # Add the assistant message to history for final answer too
                    messages.append({"role": "assistant", "content": assistant_message.content})
                    # 5. FINISH: LLM has the answer
                    answer = llm_decision.get("content", "No content provided.")
                    print(f"\n--- [Agent's Final Answer] ---\n{answer}")
                    break # Break the *inner* loop to ask for a new query

                else:
                    # Add the assistant message to history even for unknown actions
                    messages.append({"role": "assistant", "content": assistant_message.content})
                    print(f"--- [Agent] Error: Unknown LLM action: {llm_decision.get('action')} ---")
                    break # Break inner loop

            except LlamaStackClientError as e:
                print(f"--- [Agent] Error communicating with LlamaStack server: {e} ---")
                break
            except Exception as e:
                print(f"--- [Agent] An unexpected error occurred in the main loop: {e} ---")
                break

if __name__ == "__main__":
    main()
