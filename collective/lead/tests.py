# Much inspiration from z3c.sqlalchemy/trunk/src/z3c/sqlalchemy/tests/testSQLAlchemy.py
#
# You may want to run the tests with your database. To do so set the environment variable
# TEST_DSN to the connection url. e.g.:
# export TEST_DSN=postgres://plone:plone@localhost/test
# export TEST_DSN=mssql://plone:plone@/test?dsn=mydsn
#
# To test the commit code export TEST_COMMIT=True 
#
# NOTE: The sqlite that ships with Mac OS X 10.4 is buggy. Install a newer version (3.5.6)
#       and rebuild pysqlite2 against it.


import os
import unittest
import transaction
import threading
import sqlalchemy as sa
from sqlalchemy import orm, sql
from collective.lead import Database, tx
from collective.lead.database import _DIRTY_KEY
from collective.lead.interfaces import IDatabase, ITransactionAware
from zope.component import provideAdapter, provideUtility, getUtility
DB_NAME = 'collective.lead.tests.testlead'

LeadDataManager = tx.SessionDataManager

TEST_COMMIT = os.environ.get('TEST_COMMIT')
TEST_DSN = os.environ.get('TEST_DSN', 'sqlite:///:memory:')

# Setup adapters, (what configure.zcml does)
provideAdapter(
    tx.DatabaseTransactions,
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

    _url = TEST_DSN
    
    if _url.startswith('sqlite'):
        _session_properties = Database._session_properties.copy()
        _session_properties['twophase'] = False
    
    def _setup_tables(self, metadata, tables):
        tables['test_users'] = sa.Table('test_users', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('firstname', sa.VARCHAR(255)), # mssql cannot do equality on a text type
            sa.Column('lastname', sa.VARCHAR(255)),
            )
        tables['test_skills'] = sa.Table('test_skills', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('user_id', sa.Integer),
            sa.Column('name', sa.VARCHAR(255)),
            sa.ForeignKeyConstraint(('user_id',), ('test_users.id',)),
            )

    def _setup_mappers(self, tables, mappers):
        mappers['test_users'] = orm.mapper(User, tables['test_users'],
            properties = {
                'skills': orm.relation(Skill,
                    primaryjoin=tables['test_users'].columns['id']==tables['test_skills'].columns['user_id']),
            })
        mappers['test_skills'] = orm.mapper(Skill, tables['test_skills'])



class User2(SimpleModel):
    pass

class TestCleverMappersDatabase(Database):
    _url = 'sqlite:///:memory:'
    _session_properties = Database._session_properties.copy()
    _session_properties['twophase'] = False
    
    def _setup_tables(self, metadata, tables):
        tables['test_users2'] = sa.Table('test_users2', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('firstname', sa.VARCHAR(255)), # mssql cannot do equality on a text type
            sa.Column('lastname', sa.VARCHAR(255)),
            )
    
    def _setup_mappers(self, tables, mappers):
        mappers['test_users2'] = self.mapper(User2, tables['test_users2'])

db2 = TestCleverMappersDatabase()
db2._Session().begin()
db2._metadata.create_all()
db2._Session().commit()


# Setup the database
def setup_db():
    db = TestDatabase()
    provideUtility(db, IDatabase, name=DB_NAME)
    
setup_db()

class DummyException(Exception):
    pass
 
class DummyTargetRaised(DummyException):
    pass  

class DummyTargetResult(DummyException):
    pass

class DummyDataManager(object):
    def __init__(self, key, target=None, args=(), kwargs={}):
        self.key = key
        self.target = target
        self.args = args
        self.kwargs = kwargs
    
    def abort(self, trans):
        pass

    def tpc_begin(self, trans):
        pass
    
    def commit(self, trans):
        pass

    def tpc_vote(self, trans):
        if self.target is not None:
            try:
                result = target(*self.args, **self.kwargs)
            except Exception, e:
                raise DummyTargetRaised(e)
            raise DummyTargetResult(result)
        else:
            raise DummyException('DummyDataManager cannot commit')

    def tpc_finish(self, trans):
        pass

    def tpc_abort(self, trans):
        pass
    
    def sortKey(self):
        return self.key


class LeadTests(unittest.TestCase):

    @property
    def db(self):
        return getUtility(IDatabase, name=DB_NAME)
    
    def setUp(self):
        ignore = self.db.session
        self.db._metadata.drop_all()
        self.db._metadata.create_all()
    
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
        results = self.db.connection.execute(stmt)
        self.assertEqual(results.fetchall(), [(1, u'udo', u'juergens'), (2, u'heino', u'n/a')])
        
    def testRelations(self):
        session = self.db.session
        session.save(User(id=1,firstname='foo', lastname='bar'))

        user = session.query(User).filter_by(firstname='foo')[0]
        user.skills.append(Skill(id=1, name='Zope'))
        session.flush()
    
    def testTransactionJoining(self):
        transaction.abort() # clean slate
        t = transaction.get()
        self.failIf([r for r in t._resources if r.__class__ is LeadDataManager],
             "Joined transaction too early")
        ignore = self.db.session
        self.failUnless([r for r in t._resources if r.__class__ is LeadDataManager],
             "Not joined transaction")
    
    def testSavepoint(self):
        use_savepoint = not self.db.engine.url.drivername in tx.NO_SAVEPOINT_SUPPORT
        t = transaction.get()
        session = self.db.session
        query = session.query(User)
        self.failIf(query.all(), "Users table should be empty")
        
        s0 = t.savepoint(optimistic=True) # this should always work
        
        if not use_savepoint: return # sqlite databases do not support savepoints
        
        s1 = t.savepoint()
        session.save(User(id=1, firstname='udo', lastname='juergens'))
        session.flush()
        self.failUnless(len(query.all())==1, "Users table should have one row")
        
        s2 = t.savepoint()
        session.save(User(id=2, firstname='heino', lastname='n/a'))
        session.flush()
        self.failUnless(len(query.all())==2, "Users table should have two rows")
        
        s2.rollback()
        self.failUnless(len(query.all())==1, "Users table should have one row")
        
        s1.rollback()
        self.failIf(query.all(), "Users table should be empty")
    
    def testCommit(self):
        if not TEST_COMMIT: return # skip this test
        try:
            use_savepoint = not self.db.engine.url.drivername in tx.NO_SAVEPOINT_SUPPORT
            session = self.db.session
            query = session.query(User)
            rows = query.all()
            self.assertEqual(len(rows), 0)
            
            transaction.commit() # test a none modifying transaction works
            session = self.db.session
            query = session.query(User)
            rows = query.all()

            session.save(User(id=1, firstname='udo', lastname='juergens'))
            session.save(User(id=2, firstname='heino', lastname='n/a'))
            session.flush()

            rows = query.order_by(query.table.c.id).all()
            self.assertEqual(len(rows), 2)
            row1 = rows[0]
            d = row1.asDict()
            self.assertEqual(d, {'firstname' : 'udo', 'lastname' : 'juergens', 'id' : 1})
            
            transaction.commit()
            
            if self.db.engine.url.drivername == 'postgres':
                stmt = sql.text('SELECT gid FROM pg_prepared_xacts WHERE database = :database;')
                results = self.db.connection.execute(stmt, database=self.db.engine.url.database)
                self.assertEqual(len(results.fetchall()), 0, "Test no outstanding prepared transactions")
    
            rows = query.order_by(query.table.c.id).all()
            self.assertEqual(len(rows), 2)
            row1 = rows[0]
            d = row1.asDict()
            self.assertEqual(d, {'firstname' : 'udo', 'lastname' : 'juergens', 'id' : 1})
    
            # bypass the session machinary
            stmt = sql.text('SELECT * FROM test_users;')
            results = self.db.connection.execute(stmt)
            self.assertEqual(len(results.fetchall()), 2)
    
            if use_savepoint:
                # lets just test that savepoints don't affect commits
                t = transaction.get()
                rows = query.order_by(query.table.c.id).all()
        
                s1 = t.savepoint()
                session.delete(rows[1])
                session.flush()
                transaction.commit()
        
                # bypass the session machinary
                results = self.db.connection.execute(stmt)
                self.assertEqual(len(results.fetchall()), 1)
    
    
            # Test that we clean up after a tpc_abort
            t = transaction.get()
            dummy = DummyDataManager(key='~~~dummy.last')
            t.join(dummy)
            session = self.db.session
            query = session.query(User)
            rows = query.all()
            session.delete(rows[0])
            session.flush()
            
            try:
                t.commit()
            except DummyTargetResult, e:
                result = e.args[0]
                #XXX test that we have recover list here
            except DummyTargetRaised, e:
                raise e.args[0]
            except DummyException, e:
                pass
            
            transaction.begin()   

            if self.db.session.twophase:
                self.assertEqual(len(self.db.connection.recover_twophase()), 0, "Test no outstanding prepared transactions")

        finally:
            transaction.abort()
            transaction.begin()
            self.db._metadata.drop_all()
            transaction.commit()
    
    def testThread(self):
        global thread_error
        thread_error = None
        def target(db):
            try:
                session = db.session
                db._metadata.drop_all()
                db._metadata.create_all()
            
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
            except Exception, err:
                global thread_error
                thread_error = err
            transaction.abort()
        
        thread = threading.Thread(target=target, args=(self.db,))
        thread.start()
        thread.join()
        if thread_error is not None:
            raise thread_error # reraise in current thread
    
    def testConnection(self):
        conn1 = self.db.connection
        conn2 = self.db.connection
        self.assert_(conn1 is conn2, "make sure we get the same connection returned each time")
    
    def testCleverMappers(self):
        transaction.abort() # clean slate
        t = transaction.get()
        self.failIf([r for r in t._resources if r.__class__ is LeadDataManager],
             "Joined transaction too early")
        
        newuser = User2(id=1, firstname='udo', lastname='juergens')
        
        self.failUnless([r for r in t._resources if r.__class__ is LeadDataManager],
             "Not joined transaction")
        #self.failUnless(db2.connection.info[_DIRTY_KEY], 'There should be work to do')
        
        transaction.commit()
        t = transaction.begin()
        self.failIf([r for r in t._resources if r.__class__ is LeadDataManager],
             "Joined transaction too early")

        users = User2.query.all()
        
        self.failUnless([r for r in t._resources if r.__class__ is LeadDataManager],
             "Not joined transaction")
        self.failUnless(not db2.connection.info.get(_DIRTY_KEY, None), 'There should not be work to do')
        self.assertEqual(len(users), 1, 'There should not be one user here')
        
        

def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(LeadTests))
    return suite
