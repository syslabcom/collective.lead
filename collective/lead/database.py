import threading, thread
import sqlalchemy

from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.session import SessionExtension, Session
from sqlalchemy.orm.interfaces import MapperExtension, EXT_CONTINUE
from sqlalchemy.util import to_list

from zope.interface import implements

from collective.lead.interfaces import IConfigurableDatabase
from collective.lead.interfaces import ITransactionAware

_DIRTY_KEY = 'lead:dirty'


class _DirtyAfterFlush(SessionExtension):
    """Record that a flush has occurred on a session's connection. This allows
    the DataManager to rollback rather than commit on read only transactions.
    """
    
    def after_flush(self, session, flush_context):
        session.connection().info[_DIRTY_KEY] = True


class _JoinZopeTransaction(MapperExtension):
    """Join the zope transaction when session is retrieved.
    
    This is so that when you use the magical Class.query attribute everything works
    correctly.
    """
    
    def __init__(self, context, db):
        self.context = context # the ScopedSession
        self.db = db
    
    def init_instance(self, mapper, class_, oldinit, instance, args, kwargs):
        """_ScopedExt automatically saves new instances. This ensures that the
        Zope transaction is started. To switch off this behaviour supply
        save_on_init=False in _session_properties.
        """
        self.db._join_transaction()
        return EXT_CONTINUE
    
    def instrument_class(self, mapper, class_):
        """This trumps the _ScopedExt version, automatically starting the Zope
        transaction on access.
        """
        class query(object):
            def __getattr__(s, key):
                self.db._join_transaction()
                return getattr(self.context.registry().query(class_), key)
            def __call__(s):
                self.db._join_transaction()
                return self.context.registry().query(class_)

        if not 'query' in class_.__dict__: 
            class_.query = query()
        

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
        self._metadata = sqlalchemy.MetaData(bind=self._engine)
        self._Session = scoped_session(sessionmaker(
            bind=self._engine, extension=_DirtyAfterFlush(), **self._session_properties))
        self._threadlocal = threading.local()
        # active: session has joined transaction
        self._mapper_extension = _JoinZopeTransaction(self._Session, self)
        self._tables = {}
        self._mappers = {}
        self._setup_tables(self._metadata, self._tables)
        self._setup_mappers(self._metadata.tables, self._mappers)
        
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
        
    def _setup_mappers(self, tables, mappers):
        # Mappers are not strictly necessary
        pass
    
    def mapper(self, class_, *args, **kwargs):
        """Use the Session.mapper, which adds a query attribute to
        each mapped class. Tracks the mapped class, so that it
        can be referenced as an attribute.
        """
        kwargs['extension'] = extension = to_list(kwargs.get('extension', []))
        extension.append(self._mapper_extension)
        return self._Session.mapper(class_, *args, **kwargs)
        
    # If the url or engine_properties change, this must be called
    # XXX can this really be made to work in a multithreaded environment
    # without putting locks everywhere?
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
    
    def _join_transaction(self):
        """Call to ensure that the session is joined to the zope transaction.
        """
        if getattr(self._threadlocal, 'active', False):
            return
        
        self._transaction.begin(self._Session())
    
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
        return self.metadata.tables
    
    @property
    def mappers(self):
        self._join_transaction()
        return self._mappers
           
    @property
    def metadata(self):
        self._join_transaction()
        return self._metadata
         
    @property
    def _transaction(self):
        if self._tx is None:
            self._tx = ITransactionAware(self)
        return self._tx
            
    _tx = None