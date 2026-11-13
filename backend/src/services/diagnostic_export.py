import csv,io
from src.services.diagnostics import exportable

FIELDS=['diagnostic_id','source_run_id','source_checksum','batch','sample_id','item_index','status','reason','n_a','n_b','method','statistic','extreme_count','denominator','pvalue_unadjusted','baseline_statistic','baseline_pvalue','delta_statistic','delta_pvalue','baseline_extreme_count','delta_extreme_count','sigma','pooled_median_distance','constant_dimensions','B','seed','scaling','bandwidth','budget_units','budget_evaluations','budget_max_units','budget_max_evaluations','completed_items','total_items']

def rows(item):
 result=item.result or {};baseline=result.get('baseline',{});entries=result.get('items',[]);progress=item.progress or {};limits=result.get('budget') or {}
 for entry in entries:
  transform=entry.get('transform') or {}
  common={'diagnostic_id':item.id,'source_run_id':item.run_id,'source_checksum':result.get('source_checksum',''),'batch':entry['batch'],'sample_id':entry['sample_id'],'item_index':entry['index'],'status':entry['status'],'reason':entry['reason'],'n_a':entry['n_a'],'n_b':entry['n_b'],'sigma':transform.get('sigma'),'pooled_median_distance':transform.get('pooled_median_distance'),'constant_dimensions':'/'.join(str(x) for x in transform.get('constant_dimensions') or []),'B':result.get('permutations'),'seed':result.get('seed'),'scaling':result.get('scaling'),'bandwidth':result.get('bandwidth'),'budget_units':limits.get('units'),'budget_evaluations':limits.get('evaluations'),'budget_max_units':limits.get('max_units'),'budget_max_evaluations':limits.get('max_evaluations'),'completed_items':progress.get('completed'),'total_items':progress.get('total')}
  for method in ('energy','mmd'):
   current=entry.get(method);base=baseline.get(method,{})
   if current:
    yield {**common,'method':method,'statistic':current['statistic'],'extreme_count':current['extreme_count'],'denominator':current['denominator'],'pvalue_unadjusted':current['pvalue'],'baseline_statistic':base.get('statistic'),'baseline_pvalue':base.get('pvalue'),'delta_statistic':current.get('delta_statistic'),'delta_pvalue':current.get('delta_pvalue'),'baseline_extreme_count':base.get('extreme_count'),'delta_extreme_count':current.get('delta_extreme_count')}
   else:
    yield {**common,'method':method,'statistic':None,'extreme_count':None,'denominator':None,'pvalue_unadjusted':None,'baseline_statistic':base.get('statistic'),'baseline_pvalue':base.get('pvalue'),'delta_statistic':None,'delta_pvalue':None,'baseline_extreme_count':base.get('extreme_count'),'delta_extreme_count':None}

def export(db,id):
 item=exportable(db,id);buf=io.StringIO();writer=csv.DictWriter(buf,FIELDS);writer.writeheader()
 for row in rows(item):writer.writerow(row)
 return chr(0xfeff)+buf.getvalue()
