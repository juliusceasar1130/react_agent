# Q1: deepagents.create_deep_agent signature
import inspect
import deepagents

print("=== deepagents package file:", deepagents.__file__)
print("=== create_deep_agent module:", deepagents.create_deep_agent.__module__)
print("=== source file:", inspect.getsourcefile(deepagents.create_deep_agent))
print("=== SIGNATURE ===")
try:
    sig = inspect.signature(deepagents.create_deep_agent)
    print(sig)
except Exception as e:
    print("signature error:", e)

print()
print("=== SOURCE ===")
try:
    print(inspect.getsource(deepagents.create_deep_agent))
except Exception as e:
    print("source error:", e)
