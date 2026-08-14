# Q2 + Q5: CompiledSubAgent, SubAgent, SubAgentMiddleware in deepagents.middleware.subagents
import inspect
from deepagents.middleware.subagents import CompiledSubAgent, SubAgent, SubAgentMiddleware

for cls in (SubAgent, CompiledSubAgent):
    print(f"=== {cls.__module__}.{cls.__name__} ===")
    print("class file:", inspect.getsourcefile(cls))
    try:
        print("signature:", inspect.signature(cls))
    except Exception as e:
        print("signature error:", e)
    src = inspect.getsource(cls)
    print("--- source (first 60 lines) ---")
    for i, line in enumerate(src.splitlines()[:60], 1):
        print(f"{i:4d} {line}")
    print()

print("################ SubAgentMiddleware ################")
print("file:", inspect.getsourcefile(SubAgentMiddleware))
print(inspect.getsource(SubAgentMiddleware))
