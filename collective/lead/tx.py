import transaction

from zope.interface import implements

from transaction.interfaces import IDataManager, ISavepointDataManager, IDataManagerSavepoint

from sqlalchemy.orm.scoping import ScopedSession

# The status of the session is stored on the connection info
STATUS_KEY = 'lead:status'
STATUS_ACTIVE = 'active' # session joined to transaction, writes allowed.
STATUS_DIRTY = 'dirty' # data has been written
STATUS_READONLY = 'readonly' # session joined to transaction, no writes allowed.

NO_SAVEPOINT_SUPPORT = frozenset(['sqlite'])

class SessionDataManager(object):
    """Integrate a top level sqlalchemy session transaction into a zope transaction
    
    One phase variant, no savepoint support.
    """
    
    implements(IDataManager)

    def __init__(self, session, status):
        if session.transactional:
            self.tx = session.transaction._iterate_parents()[-1]
        else:
            assert session.transaction is None
            self.tx = session.begin()
        self.session = session
        self.session.connection().info[STATUS_KEY] = status
        self.state = 'init'

    def abort(self, trans):
        if self.tx is not None: # this could happen after a tpc_abort
            self.session.connection().info[STATUS_KEY] = None
            self.session.close()
            self.tx = self.session = None
            self.state = 'aborted'

    def tpc_begin(self, trans):
        self.session._autoflush()
    
    def commit(self, trans):
        status = self.session.connection().info[STATUS_KEY]
        self.session.connection().info[STATUS_KEY] = None
        if status is not STATUS_DIRTY:
            self.session.close()
            self.tx = self.session = None
            self.state = 'no work'

    def tpc_vote(self, trans):
        # for a one phase data manager commit last in tpc_vote
        if self.tx is not None: # there may have been no work to do
            self.tx.commit()
            self.session.close()
            self.tx = self.session = None
            self.state = 'finished on vote'
                
    def tpc_finish(self, trans):
        pass

    def tpc_abort(self, trans):
        raise TypeError("Already committed")

    def sortKey(self):
        # Try to sort last, so that we vote last - we may commit in tpc_vote(),
        # which allows Zope to roll back its transaction if the RDBMS 
        # threw a conflict error.
        return "~lead:%d" % id(self.tx)


class SessionSavepointDataManager(SessionDataManager):
    """One phase variant supporting savepoints.
    """
    
    implements(ISavepointDataManager)
    
    def savepoint(self):
        return SessionSavepoint(self.session)


class TwoPhaseSessionDataManager(SessionDataManager):
    """Two phase variant, no savepoint support.
    """
    def tpc_vote(self, trans):
        if self.tx is not None: # there may have been no work to do
            self.tx.prepare()
            self.state = 'voted'
                
    def tpc_finish(self, trans):
        if self.tx is not None:
            self.tx.commit()
            self.session.close()
            self.tx = self.session = None
            self.state = 'finished'

    def tpc_abort(self, trans):
        if self.tx is not None: # we may not have voted, and been aborted already
            self.tx.rollback() # this may not be strictly necessary
            self.session.close()
            self.tx = self.session = None
            self.state = 'aborted commit'

    def sortKey(self):
        # Sort normally
        return "lead.twophase:%d" % id(self.tx)


class TwoPhaseSessionSavepointDataManager(TwoPhaseSessionDataManager):
    """Two phase variant supporting savepoints.
    """
    
    implements(ISavepointDataManager)
    
    def savepoint(self):
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


_DM_MAP = { # (twophase, savepoint): DataManager
    (False, False): SessionDataManager,
    (False, True) : SessionSavepointDataManager,
    (True, False) : TwoPhaseSessionDataManager,
    (True, True)  : TwoPhaseSessionSavepointDataManager,
    }

def join_transaction(session, initial_status=STATUS_ACTIVE):
    """Join a session to a transaction using the appropriate datamanager.
       
    It is safe to call this multiple times, if the session is already joined
    then it just returns.
       
    `initial_status` is either STATUS_ACTIVE, STATUS_DIRTY or STATUS_READONLY
    """
    if session.connection().info.get(STATUS_KEY, None) is None:
        DataManager = _DM_MAP[(bool(session.twophase), session.bind.url.drivername not in NO_SAVEPOINT_SUPPORT)]
        transaction.get().join(DataManager(session, initial_status))

def dirty_session(session):
    """Mark a session as needing to be committed
    """
    info = session.connection().info
    assert info.get(STATUS_KEY, None) is not STATUS_READONLY
    info[STATUS_KEY] = STATUS_DIRTY

