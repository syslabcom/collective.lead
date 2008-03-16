import sqlalchemy

from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.session import SessionExtension

from zope.interface import implements

from collective.lead.interfaces import IConfigurableDatabase
from collective.lead import tx


class DirtyAfterFlush(SessionExtension):
    """Record that a flush has occurred on a session's connection. This allows
    the DataManager to rollback rather than commit on read only transactions.
    """
    
    def after_flush(self, session, flush_context):
        tx.dirty_session(session)
        

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
        self._engine = sqlalchemy.create_engine(self._url, **self._engine_properties)
        # as the engine is ThreadLocal we do not need ThreadLocalMetaData
        if self.metadata is None:
            self.metadata = sqlalchemy.MetaData() # metadata is not bound, as it may be shared between databases
        self._Session = scoped_session(sessionmaker(
            bind=self._engine, extension=DirtyAfterFlush(), **self._session_properties))
        self._tables = {}
        self._mappers = {}
        self._setup_tables(self.metadata, self._tables)
        self._setup_mappers(self._tables, self._mappers)
        
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
    
    _mapper_properties = dict()
    
    # For backward compatibility set to tx.STATUS_DIRTY
    # For a readonly databse set to tx.STATUS_READONLY
    _initial_transaction_status = tx.STATUS_ACTIVE
        
    def _setup_tables(self, metadata, tables):
        """By default, reflect the metadata automatically
        """
        metadata.reflect(bind=self._engine)
        self._tables = metadata.tables
        
    def _setup_mappers(self, tables, mappers):
        # Mappers are not strictly necessary
        pass
        
    # If the url or engine_properties change, this must be called
    # XXX can this really be made to work in a multithreaded environment
    # without putting locks everywhere?
    def invalidate(self):
        self.__init__()
        
    # IDatabase implementation - code using (not setting up) the database
    # uses this
    
    def dirty(self):
        """Call to indicate that there is work to be committed.
        
        Normal session operations will call this automatically.
        Call this if you operate on the connection directly.
        """
        tx.dirty_session(self.session)
    
    def _join_transaction(self):
        """Call to ensure that the session is joined to the zope transaction.
        """
        tx.join_transaction(self._Session(), self._initial_transaction_status)
    
    @property
    def session(self):
        """Scoped session object for the current thread
        """
        self._join_transaction()
        return self._Session()
    
    @property
    def connection(self):
        """Get a transaction-aware connection from the session
        """
        return self.session.connection()
    
    @property
    def engine(self):
        self._join_transaction()   
        return self._engine
    
    #XXX Deprecate?
    @property
    def tables(self):
        self._join_transaction()
        return self._tables
    
    @property
    def mappers(self):
        self._join_transaction()
        return self._mappers
           
    metadata = None
