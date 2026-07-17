import sys
sys.path.insert(0, r'C:\Users\ANAMIKA\DEV\Temp\college_agent-master\college_agent-master\backend')
from app.services.llm.safe_point import DemoLogger

dl = DemoLogger()
print('Initial:', len(dl.logs))
for i in range(5):
    dl.log('sess_1', {'event': 'test', 'session_id': 'sess_1'})
for i in range(5):
    dl.log('sess_2', {'event': 'test', 'session_id': 'sess_2'})
print('After 10 logs:', len(dl.logs))
dl.flush('sess_1')
print('After flush(sess_1):', len(dl.logs))
sids = [e.get('session_id') for e in dl.logs]
print('Remaining session_ids:', sids)
print('B8 CONFIRMED: flush() has no removal code - list keeps growing forever')
