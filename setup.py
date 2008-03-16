from setuptools import setup, find_packages
import sys, os

version = '2.0'

setup(name='collective.lead',
      version=version,
      description="SQLAlchemy/Zope2 transaction integration",
      long_description="""\
The lead part of the alchemist's toolkit.

Yes, it's Yet Another SQLAlchemy/Zope Integration Package. I'm sorry,
I really am. Many thanks to Andreas Jung for z3c.sqlalchemy and Kapil 
Thangavelu for ore.alchemist. I borrowed the Zope transaction data
manager code from Andreas who borrowed it from Kapil, I believe.

The purpose of this package is to be the lead part and the lead part only.
The gold-making bit is left to SQLAlchemy. That means that are no 
abstractions or lazy initialisaion or table auto-detection for building 
SQLAlchemy table metadata and mappers, no generation of Zope 3 interfaces,
no CRUD operations, and no dancing polar bears.

You need to understand SQLAlchemy for this package and this README to make 
any sense. See http://sqlalchemy.org/doc.

NOTE: collective.lead 2.0 requires SQLAlchemy 0.4.

The use case
------------

 - You want SQLAlchemy
 
 - You want to look up database connections/sessions as named utilities
 
 - You want to use simple domain/mapper classes, with no particular 
   dependencies
   
 - You don't want to worry about transaction and connection handling
 
 - You want to be able to configure SQL connection parameters at run-time,
   e.g. in the ZODB. Well, you don't have to, but it's nice to have the
   option.
""",
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
      url='http://svn.plone.org/collective/collective.lead',
      license='LGPL',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['collective'],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          # -*- Extra requirements: -*-
          'setuptools',
          'SQLAlchemy>=0.4.4',
      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
