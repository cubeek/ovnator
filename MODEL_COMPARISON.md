# Model Comparison Guide

## Performance Testing Results

We tested the OVN troubleshooting agent with different models to find the best balance of speed and accuracy.

### Test Query
**Simple:** "Do I have any routers?"
**Complex:** "Troubleshoot 10.0.0.48" (requires 7-step workflow)

---

## Results

### Llama 3.1 8B (GPU)

**Hardware:** GPU acceleration
**Response Time:** ⚡ 5-10 seconds per turn
**Simple Queries:** ✅ Excellent
**Complex Workflows:** ⚠️ Struggles

#### Example - Simple Query ✅
```
[You] Do I have any routers?
[Agent]
  - Correctly identifies 3 routers
  - Provides accurate names and UUIDs
  - Fast and reliable
```

#### Example - Complex Troubleshooting ⚠️
```
[You] Troubleshoot 10.0.0.48
[Agent]
  ✅ Starts correctly with get_ovn_logical_topology
  ❌ Hallucinates interface names (tap12345678)
  ❌ Makes up commands
  ❌ Doesn't follow multi-step workflow reliably
```

**Verdict:** Great for simple queries, unreliable for complex troubleshooting.

---

### Llama 3.1 70B (CPU)

**Hardware:** CPU only (no GPU)
**Response Time:** 🐌 10+ minutes per turn
**Simple Queries:** ✅ Excellent
**Complex Workflows:** ✅ Excellent (but too slow)

#### Example - Simple Query ✅
```
[You] Do I have any routers?
[Agent]
  - Correctly identifies all routers
  - Detailed analysis
  - Accurate reasoning
  [Takes 10+ minutes]
```

#### Example - Complex Troubleshooting ✅
```
[You] Troubleshoot 10.0.0.48
[Agent]
  ✅ Calls get_ovn_logical_topology
  ✅ Correctly identifies port UUID
  ✅ Correctly infers tap device name (tap6335a75c-5c)
  ✅ Logical reasoning
  [Takes 10+ minutes per step, timeout issues]
```

**Verdict:** Excellent reasoning but impractical for interactive use on CPU.

---

### Gemini 1.5 Pro (Recommended)

**Hardware:** Cloud API
**Response Time:** ⚡ 2-5 seconds per turn
**Simple Queries:** ✅ Excellent
**Complex Workflows:** ✅ Excellent
**Cost:** ~$0.001-0.005 per query

**Verdict:** ⭐ **Best overall** - fast, accurate, handles complex workflows.

#### To Use:
```python
# In agent_simple.py line 18:
MODEL_NAME = "gemini-1.5-pro"
```

---

### Gemini 1.5 Flash

**Hardware:** Cloud API
**Response Time:** ⚡ 1-3 seconds per turn
**Simple Queries:** ✅ Excellent
**Complex Workflows:** ✅ Very good
**Cost:** ~$0.0001-0.0005 per query (10x cheaper)

**Verdict:** ⭐ **Best for production** - very fast, good accuracy, very affordable.

#### To Use:
```python
# In agent_simple.py line 18:
MODEL_NAME = "gemini-1.5-flash"
```

---

## Recommendations by Use Case

### For Testing/Development
**Use:** Llama 3.1 8B (GPU)
- ✅ Free (local)
- ✅ Fast enough
- ⚠️ Test only simple queries
- ⚠️ Complex troubleshooting will hallucinate

### For Production/Complex Workflows
**Use:** Gemini 1.5 Flash or Pro
- ✅ Fast (1-5 seconds)
- ✅ Reliable multi-step reasoning
- ✅ No local infrastructure needed
- ✅ Very affordable
- ✅ Handles all troubleshooting scenarios

### If You Have 70B on GPU
**Use:** Llama 3.1 70B
- ✅ Free (local)
- ✅ Excellent reasoning
- ✅ Fast on GPU
- ✅ Best of both worlds

---

## Configuration

Edit `agent_simple.py` line 18:

```python
# Option 1: Fast local (simple queries only)
MODEL_NAME = "ollama/llama3.1:8b"

# Option 2: Cloud - Recommended for production
MODEL_NAME = "gemini-1.5-pro"  # Best accuracy
MODEL_NAME = "gemini-1.5-flash"  # Best speed/cost

# Option 3: Local - If you have GPU for 70B
MODEL_NAME = "ollama/llama3.1:70b"

# Option 4: Other cloud providers
MODEL_NAME = "claude-3-5-sonnet"  # Excellent reasoning
MODEL_NAME = "gpt-4o"  # Good all-around
```

---

## Performance Matrix

| Model | Hardware | Speed | Simple Queries | Complex Troubleshooting | Cost | Recommendation |
|-------|----------|-------|----------------|------------------------|------|----------------|
| Llama 8B | GPU | ⚡⚡⚡ | ✅ | ⚠️ | Free | Testing only |
| Llama 70B | CPU | 🐌 | ✅ | ✅ (too slow) | Free | Not practical |
| Llama 70B | GPU | ⚡⚡ | ✅ | ✅ | Free | ⭐ Best if available |
| Gemini Flash | Cloud | ⚡⚡⚡ | ✅ | ✅ | $ | ⭐ Production |
| Gemini Pro | Cloud | ⚡⚡ | ✅ | ✅ | $$ | Production |
| Claude 3.5 | Cloud | ⚡⚡ | ✅ | ✅ | $$$ | Premium |

---

## Next Steps

1. **For quick testing:** Keep using 8B for simple queries
2. **For production:** Switch to Gemini 1.5 Flash
3. **If you get GPU access:** Upgrade to 70B local model

The agent code works identically with all models - just change the `MODEL_NAME` variable!
