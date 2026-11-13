from pathlib import Path
import redis,traceback
from sqlalchemy import select
from src.config.settings import REDIS_URL
from src.config.database import Session
from src.models import DistributionRun,DistributionStudy,LeaveOneOutDiagnostic
from src.services.analysis import analyze
from src.services.leave_one_out import leave_one_out
from src.utils.time import now
client=redis.Redis.from_url(REDIS_URL);heartbeat=Path('/artifacts/worker-heartbeat')

def execute(id):
 with Session() as db:
  run=db.get(DistributionRun,id)
  if not run or run.status not in ('queued','running'):return
  run.status='running';db.commit()
  try:
   run.result=analyze(db.get(DistributionStudy,run.study_id).snapshot);run.status='completed'
  except Exception as e:run.error=str(e);run.status='failed';traceback.print_exc()
  db.commit()

def diagnose(id):
 with Session() as db:
  item=db.get(LeaveOneOutDiagnostic,id)
  if not item or item.status not in ('queued','running'):return
  item.status='running';item.updated_at=now();db.commit()
  try:
   run=db.get(DistributionRun,item.run_id);original=run.result
   policy=original['policy']
   def progress(completed,entry):
    item.progress={'completed':completed,'total':(item.progress or {}).get('total'),'current':f"{entry['batch']} · {entry['sample_id']}"};item.updated_at=now()
    db.commit()
   item.result=leave_one_out(original['raw_a'],original['raw_b'],policy,original,progress)
   item.progress={**(item.progress or {}),'completed':item.result['total_units'],'current':''};item.status='completed'
  except Exception as e:item.error=str(e);item.result={};item.status='failed';traceback.print_exc()
  item.updated_at=now();db.commit()

def main():
 with Session() as db:
  for id in db.scalars(select(DistributionRun.id).where(DistributionRun.status.in_(['queued','running']))):client.lpush('batch-distribution:jobs',id)
  for id in db.scalars(select(LeaveOneOutDiagnostic.id).where(LeaveOneOutDiagnostic.status.in_(['queued','running']))):client.lpush('batch-distribution:diagnostics',id)
 while True:
  heartbeat.touch();polled=client.brpop(['batch-distribution:jobs','batch-distribution:diagnostics'],timeout=1)
  if not polled:continue
  queue,payload=polled[0].decode(),polled[1].decode()
  if queue=='batch-distribution:jobs':execute(payload)
  else:diagnose(payload)
if __name__=='__main__':main()
