from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base

from models import 

engine = create_engine([])

Base = declarative_base
Base.metadata.create_all(engine)