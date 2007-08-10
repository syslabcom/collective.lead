import threading
import sqlalchemy

from sqlalchemy.orm.session import Session

from zope.interface import implements

from collective.lead.interfaces import IConfigurableDatabase
from collective.lead.interfaces import ITransactionAware

class Database(object):
    """Base class for database utilities. You are supposed to subclass
    this class, and implement the _url and (optionally) _engine_properties
    properties to configure the database connection. You must also implement
    _setup_tables() and, optionally, _setup_mappers() to set up tables and
    mappers. 
    
    Register your subclass as a named utility providing IDatabase. Calling
    code can then use getUtility() to get a database connection.
    """

    implements(IConfigurableDatabase)

    def __init__(self):
        self._threadlocal = threading.local()
        self.tables = {}
        self.mappers = {}
        
    # IConfigurableDatabase implementation - subclasses should override these
    
    @property
    def _url(self):
        raise NotImplemented("You must implement the _url property")
        
    @property
    def _engine_properties(self):
        return {}
        
    def _setup_tables(self, metadata, tables):
        raise NotImplemented("You must implement the _setup_tables() method")
        
    def _setup_mappers(self, tables, mappers):
        # Mappers are not strictly necessary
        pass
    
    # If the url or engine_properties change, this must be called
    
    def invalidate(self):
        self._initialize_engine()
        
    # IDatabase implementation - code using (not setting up) the database
    # uses this
    
    @property
    def session(self):
        if getattr(self._threadlocal, 'session', None) is None:
            # Without this, we may not have mapped things properly, nor
            # will we necessarily start a transaction when the client
            # code begins to use the session.
            ignore = self.engine
            self._threadlocal.session = Session()
        return self._threadlocal.session
    
    @property
    def connection(self):
        return self.engine.contextual_connect()
    
    @property
    def engine(self):

        if self._engine is None:
            self._initialize_engine()
            
        if not self._transaction.active:
             self._transaction.begin()

        return self._engine

    # Helper methods
    
    def _initialize_engine(self):
        kwargs = dict(self._engine_properties).copy()
        if 'strategy' not in kwargs:
            kwargs['strategy'] = 'threadlocal'
        
        engine = sqlalchemy.create_engine(self._url, **kwargs)
        metadata = sqlalchemy.MetaData(engine)
        
        # We will only initialize once, but we may rebind metadata if
        # necessary

        if not self.tables:
            self._setup_tables(metadata, self.tables)
            self._setup_mappers(self.tables, self.mappers)
        else:
            for name, table in self.tables.items():
                self.tables[name] = table.tometadata(self._metadata)
        
        self._engine = engine
        self._metadata = metadata

         
    @property
    def _transaction(self):
        if self._tx is None:
            self._tx = ITransactionAware(self)
        return self._tx
            
    _engine = None
    _metadata = None
    _tx = None