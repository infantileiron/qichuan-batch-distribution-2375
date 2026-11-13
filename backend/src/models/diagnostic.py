from sqlalchemy import String,JSON,ForeignKey,Text
from sqlalchemy.orm import Mapped,mapped_column
from src.config.database import Base
class LeaveOneOutDiagnostic(Base):
 __tablename__='leave_one_out_diagnostics'
 id:Mapped[str]=mapped_column(String,primary_key=True)
 run_id:Mapped[str]=mapped_column(ForeignKey('distribution_runs.id'))
 status:Mapped[str]=mapped_column(String)
 options:Mapped[dict]=mapped_column(JSON,default=dict)
 progress:Mapped[dict]=mapped_column(JSON,default=dict)
 result:Mapped[dict]=mapped_column(JSON,default=dict)
 error:Mapped[str]=mapped_column(Text,default='')
 created_at:Mapped[str]=mapped_column(String)
 updated_at:Mapped[str]=mapped_column(String)
