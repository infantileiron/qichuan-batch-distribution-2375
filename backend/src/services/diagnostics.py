import uuid,redis
from fastapi import HTTPException
from sqlalchemy import select
from src.models import DistributionRun,LeaveOneOutDiagnostic
from src.config.settings import REDIS_URL
from src.services.leave_one_out import budget_message
from src.utils.time import now
from src.utils.serialization import serialize

def create(db,run_id):
 run=db.get(DistributionRun,run_id)
 if not run:raise HTTPException(404,'运行不存在')
 if run.status!='completed':raise HTTPException(409,'运行尚未成功完成，逐样本留一诊断只能取自冻结的已完成运行')
 original=run.result or {}
 raw_a=original.get('raw_a') or [];raw_b=original.get('raw_b') or []
 if not raw_a or not raw_b:raise HTTPException(409,'原运行缺少冻结的原始读数快照，无法建立逐样本留一诊断')
 total=len(raw_a)+len(raw_b)
 refusal=budget_message(total,original.get('B') or 0)
 if refusal:raise HTTPException(422,refusal)
 item=LeaveOneOutDiagnostic(id=str(uuid.uuid4()),run_id=run_id,status='queued',options={'run_id':run_id},progress={'completed':0,'total':total,'current':''},result={},error='',created_at=now(),updated_at=now());db.add(item);db.commit()
 try:redis.Redis.from_url(REDIS_URL).lpush('batch-distribution:diagnostics',item.id)
 except redis.RedisError:
  item.status='failed';item.error='队列不可用，请重试';item.updated_at=now();db.commit();raise HTTPException(503,item.error)
 return serialize(item)

def summary(item):
 result=item.result or {}
 return {'id':item.id,'run_id':item.run_id,'status':item.status,'options':item.options or {},'progress':item.progress or {},'error':item.error or '','created_at':item.created_at,'updated_at':item.updated_at,'counts':result.get('counts'),'total_units':result.get('total_units'),'budget':result.get('budget'),'source_checksum':result.get('source_checksum',''),'permutations':result.get('permutations'),'seed':result.get('seed')}

def listing(db,run_id=None):
 query=select(LeaveOneOutDiagnostic).order_by(LeaveOneOutDiagnostic.created_at.desc())
 if run_id:query=query.where(LeaveOneOutDiagnostic.run_id==run_id)
 return [summary(item) for item in db.scalars(query)]

def detail(db,id):
 item=db.get(LeaveOneOutDiagnostic,id)
 if not item:raise HTTPException(404,'诊断不存在')
 return serialize(item)

def exportable(db,id):
 item=detail(db,id)
 if item['status']!='completed':raise HTTPException(409,'诊断尚未成功完成，暂无可导出的明细')
 return db.get(LeaveOneOutDiagnostic,id)
