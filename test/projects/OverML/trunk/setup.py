#!/usr/bin/python
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

import sys, os

VERSION  = '0.3.1'
PACKAGE_NAME = 'slow'
PACKAGES = ['slow', 'slow.model', 'slow.qtgui', 'slow.vis',
            'slow.xslt', 'slow.schema']
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

    author='Stefan Behnel',
    author_email='behnel@dvs1.informatik.tu-darmstadt.de',
    url='http://www.dvs1.informatik.tu-darmstadt.de/research/OverML/',

    classifiers = [
    'Development Status :: 3 - Alpha',
    'Intended Audience :: Developers',
    'Intended Audience :: Science/Research',
    'Programming Language :: Python',
    ],
    )
