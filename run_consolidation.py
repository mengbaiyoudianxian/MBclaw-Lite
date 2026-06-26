import sys, os
sys.path.insert(0, '/opt/mbclaw')
os.environ['MBCLAW_DB_PATH'] = '/opt/mbclaw/data/mbclaw.db'

from app.phase3_consolidation import ConsolidationEngine
from app.db import SessionLocal

db = SessionLocal()
engine = ConsolidationEngine(db)

print('Daily consolidation...')
r1 = engine.daily(1)
print(f'  daily: {r1}')

print('Weekly check...')
r2 = engine.weekly(1)
print(f'  weekly: {r2}')

print('Decay check...')
r3 = engine.decay_importance(1)
print(f'  decay: {r3}')

db.close()
print('Done')
