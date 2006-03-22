#!/usr/bin/python

setup_args = {}
try:
    from setuptools import setup
    setup_args['install_requires'] = [ 'mathdom>=0.7', 'lxml>=0.9' ]
except ImportError:
    from distutils.core import setup

import sys, os

VERSION  = '0.3.2'
PACKAGE_NAME = 'slow'
PACKAGES = ['slow', 'slow.model', 'slow.qtgui', 'slow.vis',
            'slow.xslt', 'slow.schema',
            'slow.pyexec', 'slow.pyexec.pydb', 'slow.pyexec.utils']
PACKAGE_DIRS = {'slow' : 'src/slow'}
PACKAGE_DATA = {
    'slow.qtgui'  : ['ts/*.ts'],
    'slow.schema' : ['*.rng'],
    'slow.xslt'   : ['*.xsl'],
    }

MAKE_DIRS = 'src/slow/qtgui', 'src/slow/schema'

# RUN SETUP

for make_path in MAKE_DIRS:
    make_dir = os.path.join(*make_path.split('/'))
    try:
        os.stat(os.path.join(make_dir, 'Makefile'))
    except OSError:
        continue
    if os.system('make -C '+make_dir) != 0:
        sys.exit(1)

setup(
    name=PACKAGE_NAME,
    version=VERSION,
    packages=PACKAGES,
    package_dir=PACKAGE_DIRS,
    package_data=PACKAGE_DATA,

    description='SLOW - The SLOSL Overlay Workbench',
    long_description="""\
SLOW - The SLOSL Overlay Workbench

What is SLOW?
-------------

SLOW is a visual, integrated, rapid development environment for Internet
overlay networks and Peer-to-Peer systems.  It is strongly focused on the
design of local topology decisions based on SLOSL and concepts from the
database area.  SLOW allows you to visually design and specify topologies and
protocols in a platform and language neutral way.  You can test them against
different scenarios from within the workbench before you bet your money on
their implementation.  At any time, you can save the specification in OverML
and generate a source code implementation from it.

What are SLOSL and OverML?
--------------------------

SLOW is based on the domain specific languages OverML_ and SLOSL_.  The
Overlay Modelling Language OverML is an XML language for the specification of
overlay protocols, topologies and node data.  The SQL-Like Overlay
Specification Language SLOSL is the topology specification language of OverML.
It is based on SQL.  There is also some `additional information`_ on the web.

.. _`additional information`: http://www.dvs1.informatik.tu-darmstadt.de/research/OverML/

.. _OverML: http://www.dvs1.informatik.tu-darmstadt.de/publications/pdf/behnel2005overlaylanguages.pdf
.. _SLOSL:  http://www.dvs1.informatik.tu-darmstadt.de/publications/pdf/behnel2005overlayspecification.pdf

Current status of SLOW:
-----------------------

The workbench is currently in alpha state.  Some screenshots_ from the
running system are on the Berlios developer site.

.. _screenshots: http://developer.berlios.de/screenshots/?group_id=5525

The complete workflow for design and testing is implemented, a number of
overlay topologies were implemented (see the file example.xod in the
source distribution).  There is a preliminary Python execution environment
for the specified overlays.  Source code generation is unfinished.  It
obviously requires a generator for the target language.  Current focus is
on the languages Java and Python.

Requirements:
-------------

The workbench is written in Python 2.4.  It requires PyQt3_, lxml_ and
MathDOM_.

.. _Python:  http://www.python.org/
.. _PyQt3:   http://www.riverbankcomputing.co.uk/pyqt/
.. _lxml:    http://codespeak.net/lxml/
.. _MathDOM: http://mathdom.sourceforge.net/

SLOW 0.3.2 requires lxml 0.9 and MathDOM 0.7.  Note that lxml requires
libxml2_ and libxslt_ to be installed.

.. _libxml2: http://xmlsoft.org/
.. _libxslt: http://xmlsoft.org/XSLT/
""",

    author       = 'Stefan Behnel',
    author_email = 'scoder@users.berlios.de',
    url          = 'http://developer.berlios.de/projects/slow/',

    classifiers = [
    'Development Status :: 3 - Alpha',
    'Intended Audience :: Developers',
    'Environment :: X11 Applications :: Qt',
    'Operating System :: OS Independent',
    'Programming Language :: Python',
    'License :: OSI Approved :: GNU General Public License (GPL)',
    'Intended Audience :: Science/Research',
    'Topic :: Communications',
    'Topic :: Internet',
    'Topic :: Scientific/Engineering :: Visualization',
    'Topic :: Software Development :: Code Generators',
    'Topic :: System :: Distributed Computing',
    'Topic :: System :: Networking',
    ],
    **setup_args
)
