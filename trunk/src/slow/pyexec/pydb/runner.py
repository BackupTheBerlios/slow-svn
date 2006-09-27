from StringIO import StringIO
from itertools import count, imap

from views import NodeView, ViewRegistry, PySlosl
from db    import NodeDB, DBNode, LocalNode, PyAttribute

STATIC_GLOBALS = globals().copy()
exec 'import random' in STATIC_GLOBALS
exec 'from random import randint' in STATIC_GLOBALS

class TestRunner(object):
    def __init__(self, status_writer):
        self.static_globals = STATIC_GLOBALS
        self.status = status_writer

    def run_profile(self, slosl_statements, db_attributes, init_code):
        import hotshot, hotshot.stats, os, sys

        stderr = sys.stderr # discard runtime warning for tempnam
        sys.stderr = StringIO()
        prof_filename = os.tempnam(None, 'slow-')
        sys.stderr = stderr

        prof = hotshot.Profile(prof_filename)

        views = prof.runcall(self.build_views, slosl_statements,
                             db_attributes, init_code)
        prof.close()
        stats = hotshot.stats.load(prof_filename)
        stats.strip_dirs()

        stdout = sys.stdout

        stats.sort_stats('time', 'calls')
        sys.stdout = StringIO()
        stats.print_stats()
        profile_data = sys.stdout.getvalue()

        stats.sort_stats('cumulative', 'calls')
        sys.stdout = StringIO()
        stats.print_stats()
        self.profile_data = (profile_data, sys.stdout.getvalue())

        sys.stdout = stdout

        os.remove(prof_filename)
        return views

    def run_test(self, slosl_statements, db_attributes, init_code):
        return self.build_views(slosl_statements, db_attributes, init_code)

    def build_views(self, slosl_statements, db_attributes, init_code):
        ids = sorted(a.name for a in db_attributes if a.identifier)
        if not ids:
            raise RuntimeError, "No identifiers specified."

        pyslosl_statements = map(PySlosl, slosl_statements)
        pyattributes       = dict( (a.name, a) for a in imap(PyAttribute, db_attributes) )

        node_setups = []
        all_nodes   = []
        def buildNode(**kwargs):
            try:
                identifiers = tuple(kwargs[id_name] for id_name in ids)
            except KeyError:
                raise RuntimeError, "Node misses id attribute"

            local_node = LocalNode(ids, **kwargs)
            db = NodeDB('db', local_node, pyattributes)
            viewreg = ViewRegistry(db)

            node_setups.append( (local_node, db, viewreg) )
            all_nodes.append(local_node)

        static_globals = self.static_globals.copy()
        static_globals['buildNode'] = buildNode

        for view in pyslosl_statements:
            for varname, pyvalue in view.withs:
                try:
                    static_globals[varname] = eval(pyvalue, static_globals)
                except NameError:
                    pass

        # initialize nodes
        exec init_code in static_globals

        make_foreign = static_globals['make_foreign']
        if not callable(make_foreign):
            make_foreign = lambda x:x

        # copy nodes to all DBs
        for local_node, local_db, local_viewreg in node_setups:
            for node in all_nodes:
                if node is not local_node:
                    attrs = make_foreign(local_node, dict(vars(node)))
                    if attrs:
                        local_db.addNode( DBNode(local_db, **attrs) )

        # build node views
        views_by_node = []
        for local_node, local_db, local_viewreg in node_setups:
            node_views = []
            for pyslosl in pyslosl_statements:
                node_views.append( NodeView(pyslosl, local_viewreg) )
            views_by_node.append( (local_node, node_views) )

        return views_by_node
