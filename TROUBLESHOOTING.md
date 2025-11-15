# Troubleshooting Guide

## Common Issues

### Issue: "Unknown LLM action: None"

**Symptoms:**
```
--- [Agent] Error: Unknown LLM action: None ---
```

**Causes:**
1. **Large tool output overwhelming small models** (most common)
   - OVN topology can be 1000+ lines
   - Llama 3.1 8B struggles with very large contexts
   - Model forgets to include "action" field in JSON

2. **Malformed JSON response**
   - JSON is valid but missing required fields
   - Model output got truncated

3. **Model confusion**
   - Complex troubleshooting task overwhelms model reasoning

**Solutions:**

#### Solution 1: Use a Larger Model (Recommended)
Switch to a more capable model:
```python
# In agent.py, change:
MODEL_NAME = "ollama/llama3.1:8b"

# To:
MODEL_NAME = "ollama/llama3.1:70b"  # Much better reasoning
# Or use Gemini/Claude/GPT-4 via API
```

#### Solution 2: Enable Debug Mode
Already enabled by default. Check what the LLM actually returned:
```python
DEBUG_MODE = True  # In agent.py
```

This will show:
- LLM response length
- First 200 characters
- Full response keys and structure when action is None

#### Solution 3: Simplify the Question
Instead of:
```
"Why can't I ping 172.24.5.38?"
```

Try step-by-step:
```
1. "Show me the logical topology"
2. "Find the port for IP 172.24.5.38"
3. "Show flows for br-int"
```

#### Solution 4: Reduce Tool Output (Advanced)
Modify tools to summarize output for small models:
```python
# In tools.py, truncate large outputs:
if len(result.stdout) > 5000:
    return result.stdout[:5000] + "\n... (truncated, use larger model for full output)"
```

### Issue: JSON Parse Errors

**Symptoms:**
```
--- [Agent] Error: LLM returned invalid JSON ---
```

**Solution:**
- Usually recovers automatically with retry
- If persistent, use a larger/better model
- Check DEBUG output to see malformed JSON

### Issue: LLM Not Using Tools

**Symptoms:**
- Agent responds without calling tools
- Makes up information instead of checking

**Causes:**
- Small model doesn't follow instructions well
- System prompt not emphasized enough

**Solution:**
Use Gemini, Claude, or GPT-4 which follow tool-calling instructions better.

### Issue: Slow Responses

**Causes:**
1. Large context (many tools + long outputs)
2. Small model server overloaded
3. Network latency

**Solutions:**
- Use faster model (Gemini Flash)
- Reduce tool output sizes
- Use local model with GPU acceleration

## Best Practices

### For Small Models (Llama 3.1 8B)
✅ **Works Well:**
- Simple queries: "Do I have routers?"
- Single tool calls: "Show topology"
- Short outputs

❌ **Struggles With:**
- Complex multi-step troubleshooting
- Very large tool outputs (>2000 lines)
- Reasoning about multiple layers simultaneously

### For Large Models (Gemini/Claude/GPT-4)
✅ **Excellent At:**
- Complex troubleshooting workflows
- Multi-step reasoning
- Large context handling
- Error recovery

### General Tips
1. **Start simple, then go deeper**
   - First get topology
   - Then trace specific paths
   - Finally analyze logs

2. **Be specific in queries**
   - Good: "Find errors about port 10.0.0.48"
   - Bad: "Why doesn't it work?"

3. **Use step-by-step for complex issues**
   - Let agent build context gradually
   - Small models especially benefit from this

## Debug Output Explanation

When you see:
```
--- [DEBUG] LLM Response Length: 45 chars ---
--- [DEBUG] LLM Response Start: {"action":"call_tool","tool_name":"get_o... ---
```

This means:
- Response is working (short, includes action)

When you see:
```
--- [Agent] Error: Unknown LLM action: None ---
--- [Agent] LLM Response Keys: ['analysis', 'reasoning'] ---
```

This means:
- LLM returned JSON but forgot the "action" field
- Likely overwhelmed by large context
- Agent will retry with reminder

## Model Recommendations

### For Development/Testing
- **Llama 3.1 8B**: Fast, cheap, good for basic queries
- Expect occasional failures on complex tasks

### For Production Use
- **Gemini Pro 1.5**: Best balance of speed/cost/quality
- **Gemini Flash 1.5**: Faster, slightly less capable
- **Claude 3.5 Sonnet**: Excellent reasoning, higher cost
- **GPT-4 Turbo**: Very capable, highest cost

### Switching to Gemini Example

1. Get Gemini API key from Google AI Studio

2. Update agent.py:
```python
LLAMASTACK_SERVER_URL = "https://generativelanguage.googleapis.com/v1beta"
MODEL_NAME = "gemini-1.5-pro"  # or gemini-1.5-flash
```

3. Configure authentication (depends on LlamaStack setup)

## Getting Help

If issues persist:
1. Check DEBUG output
2. Try with a larger model
3. Simplify your query
4. Check that all tools are registered: run `python3 -c "from tools import TOOL_REGISTRY; print(list(TOOL_REGISTRY.keys()))"`
