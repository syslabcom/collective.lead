import unittest

import zope.annotation
import zope.security
import zope.app.security
import zope.app.component
import zope.app.container

from zope.testing import doctestunit
from zope.component import testing
from Testing import ZopeTestCase as ztc

from zope.app.testing.placelesssetup import setUp, tearDown

from zope.configuration.xmlconfig import XMLConfig

import collective.lead

def configurationSetUp(test):
    setUp()

    XMLConfig('meta.zcml', zope.security)()
    XMLConfig('meta.zcml', zope.app.security)()
    XMLConfig('meta.zcml', zope.app.component)()

    XMLConfig('configure.zcml', zope.app.security)()
    XMLConfig('configure.zcml', zope.app.container)()
    XMLConfig('configure.zcml', zope.annotation)()


    XMLConfig('configure.zcml', collective.lead)()
    # XMLConfig('meta.zcml', plone.contentrules)()

def configurationTearDown(test):
    tearDown()


def test_suite():
    return unittest.TestSuite([

        # XXX - We don't have "real" tests yet, because dealing with the
        # database dependency is painful. You could trust me when I tell
        # you I've tested this with another package which does have
        # real database tests (against a real database), or you could
        # help me write some tests against e.g. sqlite. :)

        ztc.ZopeDocFileSuite(
           'README.txt', package='collective.lead',
            setUp=configurationSetUp,
            tearDown=configurationTearDown),

           #setUp=testing.setUp, tearDown=testing.tearDown),

        ])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
