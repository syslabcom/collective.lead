import threading
import sqlalchemy

from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.session import SessionExtension

from zope.interface import implements

from collective.lead.interfaces import IConfigurableDatabase
from collective.lead.interfaces import ITransactionAware

_DIRTY_KEY = 'lead:dirty'


class DirtyAfterFlush(SessionExtension):
    
    def after_flush(self, session, flush_context):
        session.connection().info[_DIRTY_KEY] = True


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
        self._Session = scoped_session(sessionmaker(extension=DirtyAfterFlush(),
                                                    **self._session_properties))
        self._metadata = sqlalchemy.ThreadLocalMetaData()
        self._engine = sqlalchemy.create_engine(self._url, **self._engine_properties)
        self._Session.configure(bind=self._engine)
        self._threadlocal = threading.local()
        # bound: thread local metadata is bound
        # status: None, 'JOINED', or 'CHANGED'
        self._tables = {}
        self._mappers = {}
        self._metadata.bind = self._engine
        self._setup_tables(self._metadata, self._tables)
        self._setup_mappers(self._tables, self._mappers)
        self._threadlocal.bound = True
        
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
        """By default, reflect the metadata automatically
        """
        metadata.reflect()
        self._tables = self.metadata.tables
        
    def _setup_mappers(self, tables, mappers):
        # Mappers are not strictly necessary
        pass
    
    # If the url or engine_properties change, this must be called
    
    def invalidate(self):
        self.__init__()
        self._tx = None
        
    # IDatabase implementation - code using (not setting up) the database
    # uses this
    
    def dirty(self):
        """Call to indicate that there is work to be committed.
        
        Normal session operations will call this automatically.
        Call this if you operate on the connection directly.
        """
        self.connection.info[_DIRTY_KEY] = True
    
    changed = property()
    
    @property
    def session(self):
        """Scoped session object for the current thread
        """
        if getattr(self._threadlocal, 'active', None):
            return self._Session()
            
        if getattr(self._threadlocal, 'bound', False) is False:
            self._metadata.bind = self._engine
            self._threadlocal.bound = True
        
        session = self._Session()
        self._transaction.begin(session)
        return session
    
    @property
    def connection(self):
        """Get a transaction-aware connection from the session
        """
        return self.session.connection()
    
    @property
    def engine(self):
        ignore = self.session    
        return self._engine
    
    @property
    def tables(self):
        ignore = self.session
        return self._tables
    
    @property
    def mappers(self):
        ignore = self.session
        return self._mappers
           
    @property
    def metadata(self):
        ignore = self.session
        return self._metadata
         
    @property
    def _transaction(self):
        if self._tx is None:
            self._tx = ITransactionAware(self)
        return self._tx
            
    _tx = None