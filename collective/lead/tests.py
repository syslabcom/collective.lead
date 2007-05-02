import unittest

from zope.testing import doctestunit
from zope.component import testing
from Testing import ZopeTestCase as ztc

def test_suite():
    return unittest.TestSuite([

        # XXX - We don't have "real" tests yet, because dealing with the
        # database dependency is painful. You could trust me when I tell
        # you I've tested this with another package which does have
        # real database tests (against a real database), or you could
        # help me write some tests against e.g. sqlite. :)

        # ztc.ZopeDocFileSuite(
        #    'README.txt', package='collective.lead',
        #    setUp=testing.setUp, tearDown=testing.tearDown),

        ])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
