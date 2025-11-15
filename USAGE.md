# Quick Usage Guide

## Starting the Agent

```bash
source /home/ubuntu/venv_ovnator/bin/activate
cd /home/ubuntu/ovnator
python3 agent.py
```

## Smart IP-Based Troubleshooting (Recommended)

The agent is now **smart enough to diagnose any IP automatically**. Just give it the IP!

### Examples:

```
[You] Troubleshoot 10.0.0.48

[Agent] Will automatically:
  ✓ Find logical port for this IP in OVN topology
  ✓ Find corresponding tap device in OVS topology
  ✓ Check if port is up and enabled
  ✓ Capture packets on tap device
  ✓ Trace through OVS physical layer
  ✓ Trace through OVN logical layer
  ✓ Check logs for errors about this IP
  ✓ Provide root cause analysis
```

```
[You] Why can't I reach 172.24.5.38?

[Agent] Runs complete diagnostic automatically...
```

```
[You] Diagnose connectivity for 192.168.1.100

[Agent] Performs full workflow without prompting...
```

## How It Works

When you mention an IP address with troubleshooting intent, the agent recognizes this and automatically executes a comprehensive 8-step diagnostic workflow:

1. **Topology Discovery** → Finds the port with that IP
2. **Device Mapping** → Identifies the tap device
3. **Status Check** → Verifies port is up
4. **Traffic Capture** → Captures packets to see if traffic flows
5. **Physical Trace** → Traces through OVS OpenFlow tables
6. **Logical Trace** → Traces through OVN logical topology
7. **Log Analysis** → Searches for related errors
8. **Root Cause** → Provides diagnosis

## Manual Mode (If Needed)

You can still guide the agent step-by-step:

```
[You] Show me the logical topology
[Agent] <runs get_ovn_logical_topology>

[You] Find the port for IP 10.0.0.48
[Agent] <analyzes output, identifies port>

[You] What's the tap device for that port?
[Agent] <finds tap device>
```

## Tips for Best Results

### ✅ Good Queries:
- **"Troubleshoot 10.0.0.48"** - Clear, direct
- **"Why can't I reach 172.24.5.38?"** - Problem statement with IP
- **"Diagnose 192.168.1.100"** - Simple and effective
- **"What's wrong with 10.0.0.1?"** - Implied troubleshooting

### ⚠️ Less Effective:
- ~~"Something is broken"~~ - Too vague, no IP
- ~~"Ping doesn't work"~~ - Need to specify which IP
- ~~"Help me"~~ - No context

### 🎯 Pro Tips:
1. **Be specific**: Include the IP address
2. **Use action words**: "troubleshoot", "diagnose", "why can't I reach"
3. **Let the agent work**: Don't interrupt the workflow
4. **For complex issues**: Let it finish all 8 steps

## Model Recommendations

### Current Setup: Llama 3.1 8B
- ✅ Fast and cheap
- ⚠️ May struggle with very large outputs
- ⚠️ Occasional format errors on complex queries

### Recommended Upgrade:
- **Gemini 1.5 Pro** - Excellent balance
- **Gemini 1.5 Flash** - Faster, good quality
- **Llama 3.1 70B** - Much better reasoning
- **Claude 3.5 Sonnet** - Premium quality

### To Switch Models:
Edit `agent.py` line 23:
```python
MODEL_NAME = "ollama/llama3.1:8b"  # Change this
```

To:
```python
MODEL_NAME = "gemini-1.5-pro"  # For Gemini
# or
MODEL_NAME = "ollama/llama3.1:70b"  # For larger Llama
```

## Troubleshooting

### Agent Returns "Unknown LLM action: None"
**Cause**: Model overwhelmed by large output (common with Llama 3.1 8B)

**Solution**:
1. Use a larger model (recommended)
2. Check DEBUG_MODE output to see what model returned
3. Break query into simpler steps

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for detailed guide.

### No Traffic Captured
**Normal!** If there's no active traffic to/from the IP:
- Agent will note this
- Will still trace expected paths
- Can still check configuration and logs

## Example Session

```
$ python3 agent.py

Connected to LlamaStack server at http://10.40.128.51:8321
--- OVN Troubleshooting Agent ---
Type 'exit' to quit.

[You] Troubleshoot 10.0.0.48

--- [Agent] Asking LLM for next step... ---
--- [Tool] Executing: get_ovn_logical_topology ---
  ✓ Found port 6335a75c-5c5c-4c88-940f-dc8acd018396 with IP 10.0.0.48

--- [Tool] Executing: get_ovs_topology ---
  ✓ Found tap device: tap6335a75c-5c

--- [Tool] Executing: capture_packets ---
  ✓ Captured 3 ICMP packets

--- [Tool] Executing: trace_ovs_flow ---
  ✓ Traced through br-int, packet forwarded correctly

--- [Tool] Executing: trace_ovn_packet ---
  ✓ Logical path looks good, no ACL drops

--- [Tool] Executing: search_ovn_logs ---
  ✓ No errors found for this IP

--- [Agent's Final Answer] ---
The port 10.0.0.48 (tap6335a75c-5c) is working correctly:
- Port is UP and enabled
- Traffic flowing in both directions
- No drops in OVS or OVN layers
- No errors in logs

Configuration appears correct. If you're experiencing issues,
they may be external to this compute node.

[You] exit
```

## Getting Help

1. Check [README.md](README.md) for general information
2. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for issues
3. Enable DEBUG_MODE in agent.py to see detailed output
