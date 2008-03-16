# Area for experimental feature support. Please experiment with this, but features
# here may be dropped in future versions if they don't work out well.
#
# Beware the dancing polar bears...

import sqlalchemy
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.interfaces import MapperExtension, EXT_CONTINUE
from sqlalchemy.util import to_list

from collective.lead.database import Database, DirtyAfterFlush


class JoinZopeTransaction(MapperExtension):
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
            

class ExtenedMapperDatabase(Database):
    """Database with extended mapper support.
    
    I'm not yet sure this is a good idea. The implications of having classes mapped
    to multiple databases needs to be thought through.
    """
    
    _mapper_properties = dict()
    
    def __init__(self):
        self._engine = sqlalchemy.create_engine(self._url, **self._engine_properties)
        # as the engine is ThreadLocal we do not need ThreadLocalMetaData
        self.metadata = sqlalchemy.MetaData(bind=self._engine)
        self._Session = scoped_session(sessionmaker(
            bind=self._engine, extension=DirtyAfterFlush(), **self._session_properties))
        self._mapper_extension = JoinZopeTransaction(self._Session, self)
        self._tables = {}
        self._mappers = {}
        self._setup_tables(self.metadata, self._tables)
        self._setup_mappers(self.metadata.tables, self._mappers)
        
    def mapper(self, class_, *args, **kwargs):
        """Use the Session.mapper, which adds a query attribute to
        each mapped class. Tracks the mapped class, so that it
        can be referenced as an attribute.
        """
        for k, v in self._mapper_properties.items():
            kwargs.setdefault(k, v)
            
        kwargs['extension'] = extension = to_list(kwargs.get('extension', []))
        extension.append(self._mapper_extension)
        return self._Session.mapper(class_, *args, **kwargs)
        