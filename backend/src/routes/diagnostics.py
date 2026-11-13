from fastapi import APIRouter,Depends,Response,Query
from src.config.database import db_session
from src.controllers.auth import current_user,writer
from src.schemas.diagnostic import DiagnosticInput
from src.services import diagnostics as service
from src.services import diagnostic_export
router=APIRouter(prefix='/diagnostics')

@router.get('')
def listing(run_id:str|None=Query(default=None),db=Depends(db_session),user=Depends(current_user)):return service.listing(db,run_id)

@router.post('')
def create(payload:DiagnosticInput,db=Depends(db_session),user=Depends(writer)):return service.create(db,payload.run_id)

@router.get('/{id}')
def detail(id:str,db=Depends(db_session),user=Depends(current_user)):return service.detail(db,id)

@router.get('/{id}/csv')
def export(id:str,db=Depends(db_session),user=Depends(current_user)):
 return Response(diagnostic_export.export(db,id),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename=qichuan-leave-one-out.csv'})