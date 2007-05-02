import transaction
import threading

from zope.interface import implements
from zope.component import adapts

from transaction.interfaces import IDataManager
from collective.lead.interfaces import ITransactionAware

from collective.lead.database import Database

class TreadlocalDatabaseTransactions(object):
    """Implementation-specific adapter for transaction awareness
    """
    
    implements(ITransactionAware)
    adapts(Database)
    
    def __init__(self, context):
        self.context = context

    # Called by Database if you attempt to retrieve an engine where
    # transaction.active == False

    def begin(self):
        transaction.get().join(TreadlocalDatabaseDataManager(self))
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
    
class TreadlocalDatabaseDataManager(object):
    """Use join the transactions of a threadlocal engine to Zope
    transactions
    """

    implements(IDataManager)

    def __init__(self, tx):
        self.tx = tx

    def abort(self, trans):
        self.tx.rollback()
        self.tx = None
        
    def commit(self, trans):
        self.tx.commit()
        self.tx = None

    def tpc_begin(self, trans):
        pass

    def tpc_vote(self, trans):
        pass

    def tpc_finish(self, trans):
        pass

    def tpc_abort(self, trans):
        pass

    def sortKey(self):
        return str(id(self))