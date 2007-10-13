# This, and .interfaces.IDatabase, is really all you care about
try:
    from sqlalchemy.orm import sessionmaker
except ImportError:
    raise ImportError('collective.lead requires SQLAlchemy 0.4 or higher')
 
from collective.lead.database import Database
