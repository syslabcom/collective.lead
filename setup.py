from setuptools import setup, find_packages
import sys, os

version = '1.0'

setup(name='collective.lead',
      version=version,
      description="lead",
      long_description="""\
SQLAlchemy/Zope2 transaction integration""",
      # Get more strings from http://www.python.org/pypi?%3Aaction=list_classifiers
      classifiers=[
        "Framework :: Zope2",
        "Framework :: Zope3",
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries :: Python Modules",
        ],
      keywords='',
      author='Martin Aspeli',
      author_email='optilude@gmx.net',
      url='http://svn.plone.org/plone/collective.lead',
      license='LGPL',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['collective'],
      include_package_data=True,
      zip_safe=True,
      install_requires=[
          # -*- Extra requirements: -*-
          'setuptools',
          'SQLAlchemy',
      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
