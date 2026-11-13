import {request} from './client';import type {Diagnostic} from '../types/domain';
export const list=(runId?:string)=>request<Diagnostic[]>('/diagnostics'+(runId?`?run_id=${encodeURIComponent(runId)}`:''));
export const detail=(id:string)=>request<Diagnostic>('/diagnostics/'+encodeURIComponent(id));
export const create=(runId:string)=>request<Diagnostic>('/diagnostics',{run_id:runId});
export async function downloadCsv(id:string){const r=await fetch('/api/diagnostics/'+id+'/csv',{headers:{Authorization:'Bearer '+(localStorage.getItem('distribution-token')||'')}});if(!r.ok)throw new Error('明细导出失败，请稍后重试');const u=URL.createObjectURL(await r.blob());const a=document.createElement('a');a.href=u;a.download='qichuan-leave-one-out.csv';a.click();URL.revokeObjectURL(u)}
