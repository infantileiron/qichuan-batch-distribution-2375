from pydantic import BaseModel,ConfigDict
class DiagnosticInput(BaseModel):
 model_config=ConfigDict(extra='forbid')
 run_id:str
