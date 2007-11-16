=================
 collective.lead
=================

The lead part of the alchemist's toolkit.

Yes, it's Yet Another SQLAlchemy/Zope Integration Package. I'm sorry,
I really am. Many thanks to Andreas Jung for z3c.sqlalchemy and Kapil 
Thangavelu for ore.alchemist. I borrowed the Zope transaction data
manager code from Andreas who borrowed it from Kapil, I believe.

The purpose of this package is to be the lead part and the lead part only.
The gold-making bit is left to SQLAlchemy. That means that are no 
abstractions or lazy initialisaion or table auto-detection for building 
SQLAlchemy table metadata and mappers, no generation of Zope 3 interfaces,
no CRUD operations, and no dancing polar bears.

You need to understand SQLAlchemy for this package and this README to make 
any sense. See http://sqlalchemy.org/docs/.

The use case
------------

 - You want SQLAlchemy
 
 - You want to look up database connections/sessions as named utilities
 
 - You want to use simple domain/mapper classes, with no particular 
   dependencies
   
 - You don't want to worry about transaction and connection handling
 
 - You want to be able to configure SQL connection parameters at run-time,
   e.g. in the ZODB. Well, you don't have to, but it's nice to have the
   option.

What you have to do
-------------------

Let's say we had some domain classes TableOne and TableTwo, relating to tables
table1 and table2. (We'll give these classes __repr__() functions to help
in testing.)

    >>> class TableOne(object):
    ...    def __repr__(self):
    ...        kargs = []
    ...        for col in self.c:
    ...            colnm = col.name
    ...            kargs.append('%s=%r' % (colnm, getattr(self, colnm, None)))
    ...        return '%s(%s)' % (self.__class__.__name__, ', '.join(kargs))
    >>> class TableTwo(object):
    ...    def __repr__(self):
    ...        kargs = []
    ...        for col in self.c:
    ...            colnm = col.name
    ...            kargs.append('%s=%r' % (colnm, getattr(self, colnm, None)))
    ...        return '%s(%s)' % (self.__class__.__name__, ', '.join(kargs))

You need to subclass collective.lead.Database, and fill in its
template methods. Then you register the new class as a global, non-persistent
named utility providing IDatabase.

    >>> from collective.lead import Database
    >>> import sqlalchemy as sa

We'll create the subclass for our test database:

    >>> class MyDatabase(Database):
    ...     @property
    ...     def _url(self):
    ...         return sa.engine.url.URL(drivername='sqlite', database=':memory:')
    ...
    ...     def _setup_tables(self, metadata, tables):
    ...         tables['table1'] = sa.Table('table1', 
    ...                      metadata,    
    ...                      sa.Column('id', sa.Integer, sa.Sequence('id_seq',optional=True), primary_key=True ,autoincrement=True),
    ...                      sa.Column('column', sa.String), )
    ...         tables['table2'] = sa.Table('table2', 
    ...                      metadata,    
    ...                      sa.Column('id', sa.Integer, sa.Sequence('id_seq',optional=True), primary_key=True ,autoincrement=True),
    ...                      sa.Column('table1_id', sa.Integer, sa.ForeignKey('table1.id'),nullable=False, index=True), )
    ... 
    ...     def _setup_mappers(self, tables, mappers):
    ...         mappers['table1'] = self.assign_mapper(TableOne, tables['table1'])
    ...         mappers['table2'] = self.assign_mapper(TableTwo, tables['table2'],
    ...                                         properties = {
    ...                                             'table1' : sa.orm.relation(TableOne),
    ...                                             })
        

The database utility can now be registered using zcml::

 <utility
    provides="collective.lead.interfaces.IDatabase"
    factory=".database.MyDatabase"
    name="my.database"
    />

Or, if you prefer, directly from python:

    >>> from zope.component import provideUtility
    >>> from collective.lead.interfaces import IDatabase
    >>> myDataBase = MyDatabase()
    >>> provideUtility(myDataBase, name='my.database', provides=IDatabase)

Using the database connection
-----------------------------

In application code, you can now get the database utility by name. The
database utility tracks a threadlocal engine, threadlocal metadata, and a
scoped, threadlocal session.

    >>> from zope.component import getUtility
    >>> db = getUtility(IDatabase, name='my.database')

First we initialize the database:

    >>> db.metadata.drop_all()
    >>> db.metadata.create_all()
    >>> db.session.query(TableOne).all()
    []

Since the mapped classes are available as attributes, we can also write
that last query as:

    >>> db.TableOne.query.all()
    []

**Note**: It's always safest to access a mapped class via the database
utility. On access, the utility guarantees that the tables and mappers have
been set up and that a transaction is active for the current thread.  If you
simply use the class (e.g. ``TableOne.query.all()`` or ``obj = TableOne()``),
the setup for the current thread may not be in place.

The connection is also available, in case you want to build SQL statements
yourself. The connection supplied here actually participates in the session's
transaction context.

    >>> db.connection.execute("SELECT * FROM table1")
    <sqlalchemy.engine.base.ResultProxy object at ...>

Managing transactions
---------------------

When it is first requested, a new transaction is begun. This transaction is
joined to a Zope transaction, and will commit or roll back as appropriate
when the request ends. Or, in other words, it should work -- more or less --
as you'd expect. You should not need to worry about transactions (neither
Zope nor SQL ones).
				   
    >>> object1 = db.TableOne()
    >>> object1.column = "column"
    >>> db.session.save(object1)

Objects are automatically flushed by the session.

    >>> db.session.query(TableOne).filter_by(column="column").one() == object1
    True

And the data can be accessed both via ORM and via SQL expressions.

    >>> db.TableOne.query.first()
    TableOne(id=1, column='column')
    >>> db.connection.execute("SELECT * FROM table1").fetchall()
    [(1, u'column')]

Rolling back prior to a commit works as expected.

    >>> db.session.rollback()
    >>> db.TableOne.query.all()
    []

A commit finalizes the transaction. (Be very careful injecting your own
database commits, since they bypass Zope's transaction.)

    >>> object1 = db.TableOne()
    >>> object1.column = "column"
    >>> db.session.save(object1)
    >>> db.session.new
    set([TableOne(id=None, column='column')])
    >>> db.session.commit()
    >>> db.session.new
    set([])
    >>> object1
    TableOne(id=1, column='column')
    >>> db.session.clear()
    >>> db.connection.execute("SELECT * FROM table1").fetchall()
    [(1, u'column')]

Let's try it with the Zope transaction.

    >>> import transaction
    >>> obj1 = db.TableOne()
    >>> obj1.column = 'fkey test'

As an aside, new instances are automatically saved upon construction when you
use the ``assign_mapper()`` method (which wraps the contextual
``Session.mapper``). So if you use ``assign_mapper()``, there's no need to
even call ``db.session.save()``.

    >>> db.session.new
    set([TableOne(id=None, column='fkey test')])
    >>> obj2 = db.TableTwo()
    >>> obj2.table1 = obj1
    >>> db.session.new
    set([TableOne(id=None, column='fkey test'), TableTwo(id=None, table1_id=None)])

Neither of the new records are in the database yet. Let's do the commit via
Zope.

    >>> transaction.commit()
    >>> db.session.new
    set([])
    >>> db.TableTwo.query.all()
    [TableTwo(id=1, table1_id=2)]
    >>> db.TableOne.query.get(2)
    TableOne(id=2, column='fkey test')
