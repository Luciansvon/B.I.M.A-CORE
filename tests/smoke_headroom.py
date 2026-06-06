#!/usr/bin/env python3
"""Quick smoke test: verify compress_context imports and works."""
import sys
sys.path.insert(0, "/home/bima_lucian/BIMA_CORE")

from core.langgraph_nodes.llm_config import compress_context

# Test 1: short text (should return as-is, no compression)
short = "hello world"
assert compress_context(short) == short, "Short text should pass through"
print(f"OK: short text pass-through ({len(short)} chars)")

# Test 2: ENABLE_HEADROOM=false (default) should return as-is
long_text = "x" * 500
assert compress_context(long_text) == long_text, "Should no-op when ENABLE_HEADROOM=false"
print(f"OK: disabled mode pass-through ({len(long_text)} chars)")

print("\nAll smoke tests passed!")
