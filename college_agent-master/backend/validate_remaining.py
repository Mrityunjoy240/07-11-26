"""Gather evidence for B3, B7, B8 blockers."""
import sys, inspect, asyncio
sys.path.insert(0, 'C:\\Users\\ANAMIKA\\DEV\\Temp\\college_agent-master\\college_agent-master\\backend')

# B8: DemoLogger memory leak - use file reading instead of import to avoid Unicode errors
print("=== B8: DemoLogger ===")
with open('app/services/llm/safe_point.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find class DemoLogger and its methods
in_class = False
for i, line in enumerate(lines, 1):
    if 'class DemoLogger' in line:
        print(f"DemoLogger found at line {i}")
        in_class = True
    if in_class and 'def flush' in line:
        flush_line = i
        # Print next 20 lines
        for j in range(i, min(i+20, len(lines))):
            print(f"  {j}: {lines[j-1].rstrip()}")
        # Check if clear() is called
        has_clear = any('clear' in lines[k-1] for k in range(i, min(i+20, len(lines))))
        print(f"  flush() calls clear(): {has_clear}")
    if in_class and 'def __init__' in line:
        for j in range(i, min(i+15, len(lines))):
            if 'logs' in lines[j-1] or 'deque' in lines[j-1]:
                print(f"  {j}: {lines[j-1].rstrip()}")

# Now import and test actual growth
print("\n--- Memory growth test ---")
from app.services.llm.safe_point import DemoLogger
dl = DemoLogger()
for i in range(100):
    dl.log(f"entry {i}")
print(f"After 100 appends: {len(dl.logs)}")
dl.flush()
print(f"After flush: {len(dl.logs)}")
for i in range(100):
    dl.log(f"entry {i+100}")
print(f"After 100 more appends: {len(dl.logs)}")

print("\n=== B7: BackgroundTasks ===")
import starlette
print(f"Starlette: {starlette.__version__}")
from starlette.background import BackgroundTasks, BackgroundTask

async def sample_async(x):
    pass

bt = BackgroundTasks()
try:
    bt.add_task(sample_async, "test")
    print("add_task succeeded")
    # Verify task is stored
    print(f"Tasks: {len(bt.tasks)}")
    task = bt.tasks[0]
    print(f"Task func: {task.func}, iscoroutine: {inspect.iscoroutinefunction(task.func)}")
except Exception as e:
    print(f"add_task failed: {type(e).__name__}: {e}")

# Try running bt() to see if it errors
async def test_run():
    try:
        await bt()
        print("bt() completed OK")
    except RuntimeError as e:
        print(f"bt() RuntimeError: {e}")
    except Exception as e:
        print(f"bt() other error: {type(e).__name__}: {e}")

asyncio.run(test_run())

# Check if admin.py uses BackgroundTasks with async func
print("\n--- admin.py BackgroundTasks usage ---")
with open('app/api/admin.py', 'r', encoding='utf-8') as f:
    admin_lines = f.readlines()

for i, line in enumerate(admin_lines, 1):
    if 'add_task' in line:
        # Extract the function name
        import re
        func_match = re.search(r'add_task\((\w+)', line)
        if func_match:
            func_name = func_match.group(1)
            print(f"  Line {i}: add_task({func_name}...)")

# Check if process_and_index_files is async
for i, line in enumerate(admin_lines, 1):
    if 'def process_and_index_files' in line:
        print(f"  Line {i}: {line.rstrip()}")
        is_async = 'async def' in line
        print(f"    is async: {is_async}")

print("\n=== B3: Auth route path ===")
# Don't import full app, just check routes file
with open('app/api/auth_routes.py', 'r', encoding='utf-8') as f:
    auth_lines = f.readlines()
for i, line in enumerate(auth_lines, 1):
    if '@router.post' in line or 'def login' in line or 'def token' in line:
        print(f"  Line {i}: {line.rstrip()}")
    if 'access_token' in line or 'oauth2_scheme' in line:
        print(f"  Line {i}: {line.rstrip()}")
