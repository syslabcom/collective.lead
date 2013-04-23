from collective.lead.interfaces import IConfigurableDatabase
from sqlalchemy import create_engine
from sqlalchemy import MetaData
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker
from zope.interface import implements
from zope.sqlalchemy import ZopeTransactionExtension

import logging

logger = logging.getLogger('collective.lead.database')


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
        self.tables = {}
        self.mappers = {}
        self._initialize_engine()

    # IConfigurableDatabase implementation - subclasses should override these

    @property
    def _url(self):
        raise NotImplemented("You must implement the _url property")

    @property
    def _engine_properties(self):
        return dict(convert_unicode=True)

    @property
    def _session_properties(self):
        return dict(
            extension=ZopeTransactionExtension(),
            autocommit=False,
            autoflush=True,
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
        return self._Session()

    @property
    def connection(self):
        return self.session.connection()

    @property
    def engine(self):
        return self.session.bind

    # Helper methods

    def _initialize_engine(self):
        try:
            engine = create_engine(self._url, **self._engine_properties)
        except SQLAlchemyError:
            logger.exception('Error creating db engine:')
            return

        metadata = MetaData(engine)  # be bound only for setup

        for mapper in self.mappers.values():
            mapper.dispose()
        self.tables = {}
        self.mappers = {}
        self._setup_tables(metadata, self.tables)
        self._setup_mappers(self.tables, self.mappers)

        metadata.bind = None  # unbind the metadata after setup
        self._metadata = metadata

        try:
            self._Session = scoped_session(
                sessionmaker(bind=engine, **self._session_properties))
        except SQLAlchemyError:
            logger.exception('Error creating a session:')

    _metadata = None
    _Session = None
