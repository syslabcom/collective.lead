import transaction
import threading

from zope.interface import implements
from zope.component import adapts

from transaction.interfaces import ISavepointDataManager, IDataManagerSavepoint
from collective.lead.interfaces import ITransactionAware

from collective.lead.database import Database
from sqlalchemy.orm.scoping import ScopedSession

NO_SAVEPOINT_SUPPORT = frozenset(['sqlite'])

class DatabaseTransactions(object):
    """Implementation-specific adapter for transaction awareness
    """
    
    implements(ITransactionAware)
    adapts(Database)
    
    def __init__(self, context):
        self.context = context
        self._Session = context._Session
        self._threadlocal = threading.local()

    # Called by Database if you attempt to retrieve an engine where
    # transaction.active == False

    def begin(self):
        assert not self.active, "Transaction already in progress"
        transaction.get().join(SessionDataManager(self))
        self._threadlocal.active = True
        
    @property
    def active(self):
        return getattr(self._threadlocal, 'active', False)
    
    def deactivate(self):
        self._threadlocal.active = False
    
    @property
    def session(self):
        return self._Session()


class SessionDataManager(object):
    """Integrate a top level sqlalchemy session transaction into a zope transaction
    
    Optionally supports twophase commit protocol
    """
    
    implements(ISavepointDataManager)

    def __init__(self, context):
        assert context.session.transaction is None
        self.context = context
        self.session = context.session
        self.tx = self.session.begin()

    def abort(self, trans):
        if self.tx is not None:
            self.tx.rollback()
            self._cleanup()

    def tpc_begin(self, trans):
        pass
    
    def commit(self, trans):
        self.session._autoflush()

    def tpc_vote(self, trans):
        if self.session.twophase:
            self.tx.prepare()
        else:
            self.tx.commit() # for a one phase data manager commit last in tpc_vote
            self._cleanup()

    def tpc_finish(self, trans):
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
