import math,random,numpy as np
from src.services.distances import pairwise
from src.services.energy import score as energy_score
from src.services.mmd import score as mmd_score,kernel_matrix

MAX_UNITS=200
MAX_EVALUATIONS=80000

class DegenerateBandwidth(ValueError):pass

def budget(total,permutations):
 return {'units':total,'evaluations':total*(permutations+1),'max_units':MAX_UNITS,'max_evaluations':MAX_EVALUATIONS}

def budget_message(total,permutations):
 limits=budget(total,permutations)
 reasons=[]
 if limits['units']>MAX_UNITS:reasons.append(f'色样数{total}超过上限{MAX_UNITS}')
 if limits['evaluations']>MAX_EVALUATIONS:reasons.append(f'预计共享排列计算{limits["evaluations"]}次超过上限{MAX_EVALUATIONS}（{total}个色样×（B+1），B={permutations}）')
 if not reasons:return None
 return f'逐样本留一诊断将逐个色样重新估计合并缩放与核宽，本次预计计算{limits["evaluations"]}次；{"；".join(reasons)}。为保护后台队列未创建诊断，原运行统计、排列、复核与归档均保持不变；请缩小批次或降低置换数后重新冻结研究。'

def _fit(pooled,policy):
 if policy['scaling']=='pooled_std':
  center=np.mean(pooled,axis=0);sd=np.std(pooled,axis=0,ddof=0)
  if not np.isfinite(center).all() or not np.isfinite(sd).all():raise ValueError('合并缩放溢出，无法估计合并总体均值/SD')
  constant=np.flatnonzero(sd==0).tolist();scales=np.where(sd==0,1.,sd);return (pooled-center)/scales,center,scales,constant
 if policy['scaling']=='none':return pooled,np.zeros(pooled.shape[1]),np.ones(pooled.shape[1]),[]
 raise ValueError('未知缩放口径')

def _sigma(distance,policy):
 median=float(np.median(distance[np.triu_indices(len(distance),1)]))
 if policy['bandwidth']=='pooled_median':
  if median<=0 or not math.isfinite(median):raise DegenerateBandwidth('合并样本非对角距离中位数为0或非有限，自动核宽退化，本项未估计')
  return median,median
 if policy['bandwidth']=='fixed':
  sigma=policy['sigma']
  if sigma is None or not math.isfinite(sigma) or sigma<=0:raise DegenerateBandwidth('固定sigma非正或非有限，本项未估计')
  return float(sigma),median
 raise ValueError('未知核宽策略')

def _shared_scores(distance,sigma,permutations,seed,n_a):
 n=n_a;m=len(distance)-n;N=n+m;kernel=kernel_matrix(distance,sigma);ia=list(range(n));ib=list(range(n,N))
 observed_energy=energy_score(distance,ia,ib);observed_mmd=mmd_score(kernel,ia,ib)
 rng=random.Random(seed);energy_values=[];mmd_values=[]
 for _ in range(permutations):
  order=list(range(N));rng.shuffle(order);pa=sorted(order[:n]);pb=sorted(order[n:])
  energy_values.append(energy_score(distance,pa,pb));mmd_values.append(mmd_score(kernel,pa,pb))
 def packed(observed,values):
  extreme=sum(value>=observed for value in values)
  return {'statistic':float(observed),'extreme_count':extreme,'denominator':permutations+1,'pvalue':(1+extreme)/(permutations+1)}
 return packed(observed_energy,energy_values),packed(observed_mmd,mmd_values)

def _delta(current,baseline):
 return {**current,'delta_statistic':current['statistic']-baseline['statistic'],'delta_pvalue':current['pvalue']-baseline['pvalue'],'delta_extreme_count':current['extreme_count']-baseline['extreme_count']}

def _item(batch,sample_id,index,n_a,n_b,status,reason,transform,energy=None,mmd=None):
 return {'batch':batch,'sample_id':sample_id,'index':index,'status':status,'reason':reason,'n_a':n_a,'n_b':n_b,'transform':transform,'energy':energy,'mmd':mmd}

def leave_one_out(raw_a,raw_b,policy,original,progress=None):
 a=np.asarray([[row[k] for k in ('l','a','b')] for row in raw_a],dtype=np.float64)
 b=np.asarray([[row[k] for k in ('l','a','b')] for row in raw_b],dtype=np.float64)
 if a.ndim!=2 or b.ndim!=2 or a.shape[1]!=3 or b.shape[1]!=3:raise ValueError('留一诊断需要两批完整三维读数')
 total=len(a)+len(b);permutations=original.get('B');seed=original.get('seed')
 if isinstance(permutations,bool) or not isinstance(permutations,int) or permutations<1:raise ValueError('原运行缺少有效的置换预算B，无法按原口径重跑共享排列')
 if isinstance(seed,bool) or not isinstance(seed,int) or seed<0:raise ValueError('原运行缺少有效的seed，无法按原口径重跑共享排列')
 refusal=budget_message(total,permutations)
 if refusal:raise ValueError(refusal)
 baseline={method:{key:original[method][key] for key in ('statistic','extreme_count','denominator','pvalue')} for method in ('energy','mmd')}
 baseline['sigma']=float(original['transform']['sigma']);baseline['transform']=original['transform']
 items=[]
 for label,current,other,ids in (('A',a,b,[row['sample_id'] for row in raw_a]),('B',b,a,[row['sample_id'] for row in raw_b])):
  for index,sample_id in enumerate(ids):
   kept=np.delete(current,index,axis=0)
   n_a,n_b=(len(kept),len(other)) if label=='A' else (len(other),len(kept))
   if n_a<2 or n_b<2:
    item=_item(label,sample_id,index,n_a,n_b,'insufficient_sample',f'{label}组缺席该色样后仅剩{n_a if label=="A" else n_b}条，少于每组至少2条的要求，本项未估计',None)
    items.append(item)
    if progress:progress(len(items),item)
    continue
   pooled=np.vstack([kept,other]);center=scales=constant=None;median=None;state={}
   try:
    scaled,center,scales,constant=_fit(pooled,policy)
    distance=pairwise(scaled);median=float(np.median(distance[np.triu_indices(len(pooled),1)]))
    state={'center':center.tolist(),'scales':scales.tolist(),'constant_dimensions':constant,'bandwidth':policy['bandwidth'],'pooled_median_distance':median if math.isfinite(median) else None}
    sigma,median=_sigma(distance,policy)
    state['sigma']=float(sigma)
    energy,mmd=_shared_scores(distance,sigma,permutations,seed,n_a)
    item=_item(label,sample_id,index,n_a,n_b,'ok','',state,_delta(energy,baseline['energy']),_delta(mmd,baseline['mmd']))
   except DegenerateBandwidth as error:
    state={'center':center.tolist() if center is not None else None,'scales':scales.tolist() if scales is not None else None,'constant_dimensions':constant,'bandwidth':policy['bandwidth'],'sigma':None,'pooled_median_distance':median if median is not None and math.isfinite(median) else None}
    item=_item(label,sample_id,index,n_a,n_b,'bandwidth_degenerate',str(error),state)
   except ValueError as error:
    state={'center':center.tolist() if center is not None else None,'scales':scales.tolist() if scales is not None else None,'constant_dimensions':constant,'bandwidth':policy['bandwidth'],'sigma':None,'pooled_median_distance':median if median is not None and math.isfinite(median) else None}
    item=_item(label,sample_id,index,n_a,n_b,'error',str(error),state)
   except Exception as error:
    state={'center':center.tolist() if center is not None else None,'scales':scales.tolist() if scales is not None else None,'constant_dimensions':constant,'bandwidth':policy['bandwidth'],'sigma':None,'pooled_median_distance':median if median is not None and math.isfinite(median) else None}
    item=_item(label,sample_id,index,n_a,n_b,'error',f'本项计算异常：{error}',state)
   items.append(item)
   if progress:progress(len(items),item)
 counts={status:sum(item['status']==status for item in items) for status in ('ok','insufficient_sample','bandwidth_degenerate','error')}
 return {'source_checksum':original.get('checksum',''),'baseline':baseline,'permutations':permutations,'seed':seed,'scaling':policy['scaling'],'bandwidth':policy['bandwidth'],'fixed_sigma':policy['sigma'],'budget':budget(total,permutations),'total_units':total,'counts':counts,'items':items,'comparison':'每个色样缺席时按剩余合并样本重估缩放与核宽（固定sigma保持原锁定值），使用与原始运行相同的B与seed重跑共享排列；Energy与MMD共用同一次排列；p=(1+极端次数)/(B+1)，未作多重校正。','note':'诊断只读取原运行冻结的原始读数与口径，不修改原统计、排列、复核或归档；样本不足与核宽退化的色样单独标记，不中断其余样本。'}
