import threading
import sqlalchemy

from sqlalchemy.orm import sessionmaker, scoped_session
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
        self._Session = scoped_session(sessionmaker(**self._session_properties))
        self._metadata = sqlalchemy.ThreadLocalMetaData()
        self._engine = sqlalchemy.create_engine(self._url, **self._engine_properties)
        self._Session.configure(bind=self._engine)
        self._metadata.bind = self._engine
        self.tables = {}
        self.mappers = {}
        self._setup_tables(self._metadata, self.tables)
        self._setup_mappers(self.tables, self.mappers)
        
    # IConfigurableDatabase implementation - subclasses should override these
    
    @property
    def _url(self):
        raise NotImplemented("You must implement the _url property")
        
    _engine_properties = dict(strategy = 'threadlocal',
                              convert_unicode = True,
                              encoding = 'utf-8',
                              )
    
    _session_properties = dict(autoflush=True,
                               transactional=False,
                               twophase=True,
                               )
        
    def _setup_tables(self, metadata, tables):
        raise NotImplemented("You must implement the _setup_tables() method")
        
    def _setup_mappers(self, tables, mappers):
        # Mappers are not strictly necessary
        pass
    
    # If the url or engine_properties change, this must be called
    
    def invalidate(self):
        self.__init__()
        self._tx = None
        
    # IDatabase implementation - code using (not setting up) the database
    # uses this
    
    @property
    def session(self):
        """Scoped session object for the current thread
        """
        ignore = self.engine
        return self._Session()
    
    @property
    def connection(self):
        """Get a transaction-aware connection from the session
        """
        ignore = self.engine
        return self.session.connection()
    
    @property
    def engine(self):
        if not self._transaction.active:
            self._transaction.begin()
            
        return self._engine
           
    @property
    def metadata(self):
        ignore = self.engine # ensure a transaction is active
        return self._metadata
         
    @property
    def _transaction(self):
        if self._tx is None:
            self._tx = ITransactionAware(self)
        return self._tx
            
    _tx = None