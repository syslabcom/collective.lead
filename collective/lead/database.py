import threading
import sqlalchemy

from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.session import SessionExtension

from zope.interface import implements
from zope.event import notify

from collective.lead.interfaces import IConfigurableDatabase
from collective.lead.interfaces import ITransactionAware
from collective.lead.interfaces import ISessionFlushedEvent
from collective.lead.interfaces import IBeforeSessionFlushEvent

class SessionEvent(object):
    def __init__(self, session):
        self.session = session


class SessionFlushedEvent(SessionEvent):
    implements(ISessionFlushedEvent)


class BeforeSessionFlushEvent(SessionEvent):
    implements(IBeforeSessionFlushEvent)


class SASessionExtension(SessionExtension):
    def before_flush(self, session, flush_context, objects):
        notify(BeforeSessionFlushEvent(session))

    def after_flush(self, session, flush_context):
        notify(SessionFlushedEvent(session))

    def after_commit(self, session):
        pass


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

    _Session = scoped_session(sessionmaker(autoflush=True,
                                           transactional=True,
                                           extension=SASessionExtension()))

    def __init__(self):
        self._threadlocal = threading.local()
        self._metadata = sqlalchemy.ThreadLocalMetaData()
        self.tables = {}
        self.mappers = {}
        self.ormclasses = {}
        
    # IConfigurableDatabase implementation - subclasses should override these
   
    @property
    def _url(self):
        raise NotImplemented("You must implement the _url property")
        
    @property
    def _engine_properties(self):
        return dict(strategy = 'threadlocal',
                    convert_unicode = True,
                    encoding = 'utf-8',
                    )
    
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
        """Scoped session object for the current thread
        """
        ignore = self.metadata
        return self._Session()
    
    @property
    def connection(self):
        """Get a transaction-aware connection from the session
        """
        return self.session.connection()
    
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
        if 'convert_unicode' not in kwargs:
            kwargs['convert_unicode'] = True
        if 'encoding' not in kwargs:
            kwargs['encoding'] = 'utf-8'
        
        self._engine = sqlalchemy.create_engine(self._url, **kwargs)
        self._Session.configure(bind=self._engine)
        self._metadata.bind = self._engine
        
        if not self.tables:
            self._setup_tables(self._metadata, self.tables)
            self._setup_mappers(self.tables, self.mappers)
         
    @property
    def _transaction(self):
        if self._tx is None:
            self._tx = ITransactionAware(self)
        return self._tx
           
    @property
    def metadata(self):
        if self._engine is None:
            ignore = self.engine
        elif not self._metadata.is_bound():
            self._metadata.bind = self.engine
        else:
            ignore = self.engine # ensure a transaction is active
        return self._metadata

    def assign_mapper(self, klass, *args, **kwargs):
        """Use the Session.mapper, which adds a query attribute to
           each mapped class. Tracks the mapped class, so that it
           can be referenced as an attribute.
        """
        self.ormclasses[klass.__name__] = klass
        return self._Session.mapper(klass, *args, **kwargs)

    def __getattr__(self, name):
        """Allow access to mapped classes as attributes. To work, this
           requires that the defined mappers use our assign_mapper()
           rather than 
        """
        # ensure things are set up for this thread
        ignore = self.metadata
        if name in self.ormclasses:
            return self.ormclasses[name]
        raise AttributeError, '%r object has no attribute %r' % \
            (self.__class__.__name__, name)

    _engine = None
    _tx = None
