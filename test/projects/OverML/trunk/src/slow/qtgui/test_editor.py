STATIC_GLOBALS = globals().copy()
exec 'from random import randint' in STATIC_GLOBALS

from itertools import count
from qt import QStringList
from qt_utils import qstrpy, pyqstr

from slow.vis.view_viz import ViewGraph
from slow.pyexec.pydb.views import NodeView, ViewRegistry
from slow.pyexec.pydb.db    import NodeDB, DBNode, LocalNode

DEFAULT_CODE = '''\
NODES = 10

for n in range(NODES):
    "build a new node using buildNode(...)"

def make_foreign(attributes):
    """Do something with the node attribute dictionary, then return it.
    Returning None or an empty dict will not add the node."""
    return attributes
'''

## DEFAULT_CODE = '''\
## NODES  = 10
## MAX_ID = 100

## for n in range(NODES):
##     buildNode(id=n)

## def make_foreign(local_node, attributes):
##     """Do something with the node attribute dictionary, then return it.
##     Returning None or an empty dict will discard the node."""
##     attributes["knows_chord"] = True
##     attributes["alive"]       = True
    
##     dist = (attributes["id"] - local_node.id) % MAX_ID
##     attributes["local_dist"] = dist
##     return attributes
## '''

class TestRunner(object):
    def __init__(self):
        self.static_globals = STATIC_GLOBALS
        
    def run_test(self, slosl_statements, db_attributes, init_code, graphviz_program):
        ids = sorted(a.name for a in db_attributes if a.identifier)
        if not ids:
            raise RuntimeError, "No identifiers specified."

        node_setups = []
        all_nodes   = []
        def buildNode(**kwargs):
            try:
                identifiers = tuple(kwargs[id_name] for id_name in ids)
            except KeyError:
                raise RuntimeError, "Node misses id attribute"

            local_node = LocalNode(**kwargs)
            db = NodeDB('db', local_node, db_attributes)
            viewreg = ViewRegistry(db)

            node_setups.append( (local_node, db, viewreg) )
            all_nodes.append(local_node)

        static_globals = self.static_globals.copy()
        static_globals['make_foreign'] = lambda x:x
        static_globals['buildNode']    = buildNode

        # initialize nodes
        exec init_code in static_globals

        make_foreign = static_globals['make_foreign']
        if not callable(make_foreign):
            make_foreign = lambda x:x

        # copy nodes to all DBs and build node views
        views_by_node = []
        for local_node, local_db, local_viewreg in node_setups:
            for node in all_nodes:
                if node is not local_node:
                    attrs = make_foreign(local_node, dict(vars(node)))
                    if attrs:
                        local_db.addNode( DBNode(local_db, **attrs) )
            node_views = []
            for statement in slosl_statements:
                node_views.append( NodeView(statement, local_viewreg) )
            views_by_node.append( (local_node, node_views) )

        view_graph = ViewGraph(views_by_node)
        return view_graph.graph.tostring('svg', graphviz_program,
                                         overlap='false', fontsize='10')


class TestEditor(object):
    def __init__(self):
        self.__setup_child_calls()
        self.__view_tests = {}
        self.__current_test = None
        self.__running = False
        self.__runner = TestRunner()

    def activate_test_tab(self):
        slosl_model = self.slosl_model()
        statement_names = sorted(s.name for s in slosl_model.statements)

        combobox = self.test_view_select_comboBox
        old_selection = qstrpy( combobox.currentText() )
        combobox.clear()
        strlist = QStringList()
        for name in statement_names:
            strlist.append(name)
        combobox.insertStringList(strlist)

        try:
            current = statement_names.index(old_selection)
        except ValueError:
            if statement_names:
                current = 0
            else:
                current = -1
        combobox.setCurrentItem(current)

    def __setup_child_calls(self):
        try:
            self.__setStatus = self.setStatus
        except AttributeError:
            def dummy(*args):
                pass
            self.__setStatus = dummy

        try:
            self.__tr = self.tr
        except AttributeError:
            def dummy(self, arg):
                return arg
            self.__tr = dummy

    def __stop_test(self):
        self.__running = False

    def test_run_button_clicked(self):
        if self.__running:
            self.__stop_test()
        self.__running = True

        current_test = self.test_view_select_comboBox.currentText()
        if not current_test:
            self.__setStatus(self.__tr("Please select a view to test"))
            return

        current_test = qstrpy(current_test)

        slosl_model = self.slosl_model()
        statement = slosl_model.getStatement(current_test)

        if statement:
            attribute_model = self.attribute_model()
            init_code = qstrpy(self.test_init_code.text())

            graphviz_program = self.test_graphviz_program_comboBox.currentText()
            if graphviz_program:
                graphviz_program = qstrpy(graphviz_program)
            else:
                graphviz_program = 'neato'

            try:
                result = self.__runner.run_test([statement], attribute_model,
                                                init_code, graphviz_program)
                self.test_view_graph.set_image_data(result)
            except Exception, e:
                self.__setStatus(e)
        else:
            self.__setStatus(self.__tr("Error: view '%1' not found").arg(current_test))

    def test_view_select_comboBox_activated(self, view_name):
        view_name = qstrpy(view_name)
        if self.__current_test:
            self.__view_tests[self.__current_test] = qstrpy(self.test_init_code.text())
        self.__current_test = view_name

        test_code = self.__view_tests.get(view_name)
        if not test_code:
            test_code = DEFAULT_CODE
        self.test_init_code.setText(pyqstr(test_code))
