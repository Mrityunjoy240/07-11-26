import sys, inspect, asyncio
sys.path.insert(0, r'C:\Users\ANAMIKA\DEV\Temp\college_agent-master\college_agent-master\backend')

import starlette
print('Starlette:', starlette.__version__)
from starlette.background import BackgroundTasks, BackgroundTask

# Reproduce the exact pattern from admin.py
async def process_and_index_files(files):
    pass

bt = BackgroundTasks()
try:
    bt.add_task(process_and_index_files, [])
    print('add_task succeeded')
except Exception as e:
    print('add_task error:', type(e).__name__, str(e))

print('Tasks count:', len(bt.tasks))

# Check if the task function is a coroutine function
if bt.tasks:
    task = bt.tasks[0]
    print('Task func:', task.func)
    print('iscoroutinefunction:', inspect.iscoroutinefunction(task.func))
    
    # Run it - the key question
    async def run():
        try:
            await bt()
            print('bt() completed OK')
        except RuntimeError as e:
            print('bt() RuntimeError:', e)
        except Exception as e:
            print('bt() error:', type(e).__name__, str(e))
    
    asyncio.run(run())

# Check admin.py for actual async background usage
with open(r'C:\Users\ANAMIKA\DEV\Temp\college_agent-master\college_agent-master\backend\app\api\admin.py', encoding='utf-8') as f:
    src = f.read()

# Find if add_task is called with an async function
import re
for m in re.finditer(r'add_task\((\w+)', src):
    func_name = m.group(1)
    # Find the function definition
    def_match = re.search(r'(async\s+)?def\s+' + func_name + r'\s*\(', src)
    if def_match:
        is_async = 'async' in def_match.group(0) if def_match.group(1) else False
        print(f'admin.py: add_task({func_name}) -> async={is_async}')
    else:
        print(f'admin.py: add_task({func_name}) (std lib function)')
