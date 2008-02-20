import transaction
import threading

from zope.interface import implements
from zope.component import adapts

from transaction.interfaces import ISavepointDataManager, IDataManagerSavepoint
from collective.lead.interfaces import ITransactionAware

from collective.lead.database import Database

NO_SAVEPOINT_SUPPORT = frozenset(['sqlite'])

class ThreadlocalDatabaseTransactions(object):
    """Implementation-specific adapter for transaction awareness
    """
    
    implements(ITransactionAware)
    adapts(Database)
    
    def __init__(self, context):
        self.context = context

    # Called by Database if you attempt to retrieve an engine where
    # transaction.active == False

    def begin(self):
        assert not self.active, "Transaction already in progress"
        transaction.get().join(ThreadlocalDatabaseDataManager(self))
        self.context._threadlocal.active = True
        self.context.engine.begin()
        
    @property
    def active(self):
        return getattr(self.context._threadlocal, 'active', False)
        
    # Called by ThreadlocalEngineConnectionManager in response to Zope
    # transaction commits/rollbacks
        
    def rollback(self):
        self.context.engine.rollback()
        self.context._threadlocal.active = False
        self.context._threadlocal.session = None
    
    def commit(self):
        self.context.engine.commit()
        self.context._threadlocal.active = False
        self.context._threadlocal.session = None


class ThreadlocalDatabaseDataManager(object):
    """Use join the transactions of a threadlocal engine to Zope
    transactions
    """

    implements(ISavepointDataManager)

    def __init__(self, tx):
        self.tx = tx

    def abort(self, trans):
        # sometimes tx is None
        if self.tx is not None:
            self.tx.rollback()
            self.tx = None
        
    def commit(self, trans):
        pass

    def tpc_begin(self, trans):
        pass

    def tpc_vote(self, trans):
        self.tx.commit()
        self.tx = None

    def tpc_finish(self, trans):
        pass

    def tpc_abort(self, trans):
        self.abort(trans)

    def sortKey(self):
        # Try to sort last, so that we vote last - we commit in tpc_vote(),
        # which allows Zope to roll back its transaction if the RDBMS 
        # threw a conflict error.
        return "~lead:%d" % id(self.tx)

    @property
    def savepoint(self):
        if self.tx.context.engine.url.drivername in NO_SAVEPOINT_SUPPORT:
            raise AttributeError('savepoint')
        else:
            return self._savepoint
    
    def _savepoint(self):
        return SessionSavepoint(self.tx.context.session)


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
