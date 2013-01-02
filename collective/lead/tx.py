import transaction
import threading

from zope.interface import implements
from zope.component import adapts

from transaction.interfaces import IDataManager
from collective.lead.interfaces import ITransactionAware

from collective.lead.database import Database

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

    implements(IDataManager)

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