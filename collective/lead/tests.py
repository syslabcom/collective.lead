# Much inspiration from z3c.sqlalchemy/trunk/src/z3c/sqlalchemy/tests/testSQLAlchemy.py
#
# You may want to run the tests with your database. To do so set the environment variable
# TEST_DSN to the connection url. e.g.:
# export TEST_DSN=postgres://plone:plone@localhost/test
#
# To test the commit code export TEST_COMMIT=True 
#
# NOTE: The sqlite that ships with Mac OS X 10.4 and 10.5 is buggy. Install a newer version (3.5.6)
#       and rebuild pysqlite2 against it.


import os
import unittest
import transaction
import sqlalchemy as sa
from sqlalchemy import orm, sql
from collective.lead import Database
from collective.lead.interfaces import IDatabase
from zope.component import provideAdapter, provideUtility, getUtility
DB_NAME = 'collective.lead.tests.testlead'


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

    _url = os.environ.get('TEST_DSN', 'sqlite:///:memory:')
    
    def _setup_tables(self, metadata, tables):
        tables['test_users'] = sa.Table('test_users', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('firstname', sa.Text),
            sa.Column('lastname', sa.Text),
            )
        tables['test_skills'] = sa.Table('test_skills', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('user_id', sa.Integer),
            sa.Column('name', sa.Text),
            sa.ForeignKeyConstraint(('user_id',), ('test_users.id',)),
            )
        metadata.drop_all()
        metadata.create_all()

    def _setup_mappers(self, tables, mappers):
        mappers['test_users'] = orm.mapper(User, tables['test_users'],
            properties = {
                'skills': orm.relation(Skill,
                    primaryjoin=tables['test_users'].columns['id']==tables['test_skills'].columns['user_id']),
            })
        mappers['test_skills'] = orm.mapper(Skill, tables['test_skills'])

# Setup the database
def setup_db():
    db = TestDatabase()
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
        
        # bypass the session machinary
        stmt = sql.select(query.table.columns).order_by('id')
        results = self.db.engine.connect().execute(stmt)
        self.assertEqual(results.fetchall(), [(1, u'udo', u'juergens'), (2, u'heino', u'n/a')])
        
        # and rollback
        transaction.abort()
        self.db.invalidate()
        results = self.db.connection.execute(stmt)
        self.assertEqual(results.fetchall(), [])
        
    def testRelations(self):        
        session = self.db.session
        session.save(User(id=1,firstname='foo', lastname='bar'))

        user = session.query(User).filter_by(firstname='foo')[0]
        user.skills.append(Skill(id=1, name='Zope'))
        session.flush()


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(LeadTests))
    return suite
