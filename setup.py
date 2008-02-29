from setuptools import setup, find_packages
import os

version = '1.0'

setup(name='collective.lead',
      version=version,
      description="SQLAlchemy/Zope2 transaction integration",
      long_description=
          open(os.path.join("collective", "lead", "README.txt")).read()+"\n"+
          open(os.path.join("docs", "HISTORY.txt")).read(),
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
          'setuptools',
          'SQLAlchemy>=0.3.10,<0.4dev',
      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
