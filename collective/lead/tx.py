import transaction

from zope.interface import implements
from zope.component import adapts

from transaction.interfaces import ISavepointDataManager, IDataManagerSavepoint
from collective.lead.interfaces import ITransactionAware

from collective.lead.database import Database, _DIRTY_KEY
from sqlalchemy.orm.scoping import ScopedSession

NO_SAVEPOINT_SUPPORT = frozenset(['sqlite'])

class DatabaseTransactions(object):
    """Implementation-specific adapter for transaction awareness
    """
    
    implements(ITransactionAware)
    adapts(Database)
    
    def __init__(self, context):
        self.context = context

    # Called by Database if you attempt to retrieve an engine where
    # transaction.active == False

    def begin(self, session):
        assert not self.active, "Transaction already in progress"
        transaction.get().join(SessionDataManager(self, session))
        self.context._threadlocal.active = True
        
    @property
    def active(self):
        return getattr(self.context._threadlocal, 'active', None)
    
    def deactivate(self):
        self.context._threadlocal.active = None


class SessionDataManager(object):
    """Integrate a top level sqlalchemy session transaction into a zope transaction
    
    Optionally supports twophase commit protocol
    """
    
    implements(ISavepointDataManager)
    # sometimes this only implements IDataManager. But it doesn't matter as transaction
    # tests for the existance of the savepoint method.

    def __init__(self, context, session):
        if session.transactional:
            self.tx = session.transaction._iterate_parents()[-1]
        else:
            assert session.transaction is None
            self.tx = session.begin()
        self.context = context # only really needed for non transactional sessions
        self.session = session

    def abort(self, trans):
        if self.tx is not None:
            self.tx.rollback()
            self._cleanup()

    def tpc_begin(self, trans):
        self.session._autoflush()
    
    def commit(self, trans):
        if not self.session.connection().info.get(_DIRTY_KEY, False):
            self.abort(trans) # no work to do
            

    def tpc_vote(self, trans):
        if self.tx is not None: # there may have been no work to do
            if self.session.twophase:
                self.tx.prepare()
            else:
                self.tx.commit() # for a one phase data manager commit last in tpc_vote
                self._cleanup()

    def tpc_finish(self, trans):
        if self.tx is not None:
            if self.session.twophase:
                self.tx.commit()
                self._cleanup()

    def tpc_abort(self, trans):
        if self.tx is not None: # we may not have voted, and been aborted already
            self.abort(trans)

    def sortKey(self):
        # Try to sort last, so that we vote last - we may commit in tpc_vote(),
        # which allows Zope to roll back its transaction if the RDBMS 
        # threw a conflict error.
        return "~lead:%d" % id(self.tx)
    
    def _cleanup(self):
        self.session.connection().info[_DIRTY_KEY] = False
        self.session.close()
        self.tx = None
        self.context.deactivate()

    @property
    def savepoint(self):
        if self.context.context.engine.url.drivername in NO_SAVEPOINT_SUPPORT:
            raise AttributeError('savepoint')
        else:
            return self._savepoint
    
    def _savepoint(self):
        return SessionSavepoint(self.session)


class SessionSavepoint:
    implements(IDataManagerSavepoint)

    def __init__(self, session):
        self.session = session
        self.transaction = session.begin_nested()
        session.flush() # do I want to do this? Probably.

    def rollback(self):
        # no need to check validity, sqlalchemy should raise an exception. I think.
        self.transaction.rollback()
        self.session.clear() # remove when Session.rollback does an attribute_manager.rollback
