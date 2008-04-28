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
table1 and table2.

    >>> class TableOne(object):
    ...     pass
    >>> class TableTwo(object):
    ...     pass

You are supposed to subclass collective.lead.Database, fill in its template
methods, and then register the new class as a global, non-persistent
named utility providing IDatabase.

    >>> from collective.lead import Database
    >>> import sqlalchemy as sa
    >>> from sqlalchemy import orm

    >>> class MyDatabase(Database):
    ...     @property
    ...     def _url(self):
    ...         return sa.engine.url.URL(drivername='mysql', username='user',
    ...                    host='localhost',  database='testdb')
    ...
    ...     def _setup_tables(self, metadata, tables):
    ...         tables['table1'] = sa.Table('table1', metadata, autoload=True)
    ...         tables['table2'] = sa.Table('table2', metadata, autoload=True)
    ... 
    ...     def _setup_mappers(self, tables, mappers):
    ...         mappers['table1'] = orm.mapper(TableOne, tables['table1'])
    ...         mappers['table2'] = orm.mapper(TableTwo, tables['table2'],
    ...                                         properties = {
    ...                                             'table1' : orm.relation(TableOne),
    ...                                             })
        

The database utility can now be registered using zcml:

 <utility
    provides="collective.lead.interfaces.IDatabase"
    factory=".database.MyDatabase"
    name="my.database"
    />

or if you prefer directly from python (XXX this does not work):

    >>> from zope.component import provideUtility
    >>> from collective.lead.interfaces import IDatabase
    >>> provideUtility(MyDatabase, name='my.database', provides=IDatabase)

Using the database connection
-----------------------------

In application code, you can now get a database engine by name. This engine
is threadlocal, and contains a single, cached session. When it is first
requested, a new transaction will be begun. This is joined to a Zope
transaction, and will commit or roll back as appropriate when the request
ends. Or, in other words, it should work more or less as you'd expect and
you should not need to worry about transactions (neither Zope nor SQL ones).

    >>> from zope.component import getUtility
    >>> db = getUtility(IDatabase, name='my.database')
    >>> db.session.query(TableOne).list()
    []
    
    >>> db.connection.execute("SELECT * FROM table1")

    
