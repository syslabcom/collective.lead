# Much inspiration from z3c.sqlalchemy/trunk/src/z3c/sqlalchemy/tests/testSQLAlchemy.py

import os
import unittest
import transaction
import sqlalchemy as sa
from sqlalchemy import orm
from collective.lead import Database, tx
from collective.lead.interfaces import IDatabase, ITransactionAware
from zope.component import provideAdapter, provideUtility, getUtility
DB_NAME = 'collective.lead.tests.testlead'

LeadDataManager = tx.ThreadlocalDatabaseDataManager


# Setup adapters, (what configure.zcml does)
provideAdapter(
    tx.ThreadlocalDatabaseTransactions,
    adapts=(Database,),
    provides=ITransactionAware,
    )


class SimpleModel(object):
    
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)
    
    def asDict(self):
        return dict((k, v) for k, v in self.__dict__.items() if not k.startswith('_'))


class User(SimpleModel):
    pass


class Skill(SimpleModel):
    pass


class TestDatabase(Database):

    _url = 'sqlite:///test'
    
    def _setup_tables(self, metadata, tables):
        tables['users'] = sa.Table('users', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('firstname', sa.Text),
            sa.Column('lastname', sa.Text),
            )
        tables['skills'] = sa.Table('skills', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('user_id', sa.Integer),
            sa.Column('name', sa.Text),
            sa.ForeignKeyConstraint(('user_id',), ('users.id',)),
            )

    def _setup_mappers(self, tables, mappers):
        mappers['users'] = orm.mapper(User, tables['users'],
            properties = {
                'skills': orm.relation(Skill,
                    primaryjoin=tables['users'].columns['id']==tables['skills'].columns['user_id']),
            })
        mappers['skills'] = orm.mapper(Skill, tables['skills'])

# Setup the database
def setup_db():
    db = TestDatabase()
    db._initialize_engine(create_all=True)
    provideUtility(db, IDatabase, name=DB_NAME)

setup_db()
    

class LeadTests(unittest.TestCase):

    @property
    def db(self):
        return getUtility(IDatabase, name=DB_NAME)
        
    def tearDown(self):
        transaction.abort()

    def testSimplePopulation(self):
        session = self.db.session
        query = session.query(User)
        rows = query.all()
        self.assertEqual(len(rows), 0)

        session.save(User(id=1, firstname='udo', lastname='juergens'))
        session.save(User(id=2, firstname='heino', lastname='n/a'))
        session.flush()
        
        rows = query.order_by(query.table.c.id).all()
        self.assertEqual(len(rows), 2)
        row1 = rows[0]
        d = row1.asDict()
        self.assertEqual(d, {'firstname' : 'udo', 'lastname' : 'juergens', 'id' : 1})
        
    def testXXRelations(self):
        session = self.db.session
        session.save(User(id=1,firstname='foo', lastname='bar'))

        user = session.query(User).filter_by(firstname='foo')[0]
        user.skills.append(Skill(id=1, name='Zope'))
        session.flush()
    
    def testTransactioJoining(self):
        transaction.abort() # clean slate
        t = transaction.get()
        self.failIf([r for r in t._resources if r.__class__ is LeadDataManager],
             "Joined transaction too early")
        ignore = self.db.session
        self.failUnless([r for r in t._resources if r.__class__ is LeadDataManager],
             "Not joined transaction")

def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(LeadTests))
    return suite
