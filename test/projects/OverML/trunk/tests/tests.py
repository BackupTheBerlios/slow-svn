#!/usr/bin/env python

import unittest, sys

def build_testsuite(all_globals):
    test_cases = [ cls for cls in all_globals
                   if type(cls) is type and issubclass(cls, unittest.TestCase) ]

    test_suites = []

    for test_class in test_cases:
        suite = unittest.makeSuite(test_class)
        test_suites.append(suite)

    return unittest.TestSuite(test_suites)


def run_or_profile(suite):
    runner = unittest.TextTestRunner(verbosity=2)

    args = sys.argv[1:]

    if '-P' in args or '-PP' in args:
        try:
            import psyco
            if '-PP' in sys.argv[1:]:
                psyco.profile()
            else:
                psyco.full()
            print "Using Psyco."
        except:
            pass

    if '-p' in args:
        import os, hotshot, hotshot.stats
        LOG_FILE="profile.log"

        profiler = hotshot.Profile(LOG_FILE)
        profiler.runcall(runner.run, suite)
        profiler.close()

        stats = hotshot.stats.load(LOG_FILE)
        stats.strip_dirs()
        stats.sort_stats('time', 'calls')
        stats.print_stats(60)

        try:
            os.unlink(LOG_FILE)
        except:
            pass
    else:
        runner.run(suite)


def run_testsuites(all_globals):
    run_or_profile( build_testsuite(all_globals) )
