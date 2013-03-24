from zope.interface import Attribute
from zope.interface import Interface


# Used by general application code

class IDatabase(Interface):
    """A database connection, lazily instantiating an SQLAlchemy engine.
    The engine is threadlocal, and its transactions are tied to Zope
    transactions.
    """

    # Most application code will use only these two properties

    session = Attribute(
        "An SQLAlchemy session. Use this for ORM session operations.")

    connection = Attribute(
        "An SQLAlchemy connection. Use this to execute SQL.")

    # These properties give more finely grained access to the database

    engine = Attribute(
        "The underlying engine object. This uses a threadlocal strategy.")

    tables = Attribute(
        "A dictionary of SQLAlchemy Table's, keyed by table name, for this "
        "database"
    )

    mappers = Attribute(
        "A dictionary of SQLAlchemy Mapper's, keyed by entity name, for this "
        "database"
    )


# Used to set up the database utility - See also
# collective.lead.database.Database.

class IConfigurableDatabase(IDatabase):
    """Configuration aspects of an IDatabase"""

    def invalidate(self):
        """Invalidate the configuration of the database, causing the engine
        to be re-initialised and tables and mappers to be reset.
        Bound metadata is passed to the setup methods for backwards
        compatability, but is unbound by the end of this method.
        """

    _url = Attribute(
        "An sqlalchemy.engine.url.URL used to connect to the database server")

    _engine_properties = Attribute(
        "A dictionary of additional arguments to pass to create_engine()")

    _session_properties = Attribute(
        "A dictionary of additional arguments to pass to create_session()")

    def _setup_tables(metadata, tables):
        """Given an SQLAlchemy Metadata for the current engine, set up
        Tables for the database structure, saving them to the dict
        'tables', keyed by table name.
        """

    def _setup_mappers(tables, mappers):
        """Given a dict of tables, keyed by table name as in self.tables,
        set up all SQLAlchemy mappers for the database and save them to the
        dict 'mappers', keyed by table name.
        """
