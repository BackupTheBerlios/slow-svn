from string      import Template
from collections import deque
from itertools   import *

from twisted.internet   import defer, reactor
from twisted.enterprise import adbapi
from pyPgSQL.libpq import DatabaseError

from observable import ReflectiveObservable, TypedObservable, Observable
from viewspec   import ViewSpecification
from node       import StaticNode, AbstractNode
from specparser import (StatementElement, Attribute, Variable,
                        XRange, IntList, AnyList)

from helpers     import _md5hex, _TYPE_MAPPING_PYDB, _TYPE_MAPPING_DBPY
from slosl2sql   import SQLViewBuilder

_NODE_ID_COLUMN = '_node_id'
_LOCAL_TABLE    = '_db_table_local'
_MAX_ROW_FETCH  = 30

STATIC_ATTRIBUTE, VOLATILE_ATTRIBUTE = 'static', 'volatile'


class NodeDestroyedError(Exception):
    pass


def db_connect(dbmodule="pyPgSQL.PgSQL",
               noisy=False, min_connect=4, max_connect=8,
               *args, **kwargs):
    return ObservableConnectionPool(
        dbmodule, cp_noisy=noisy, cp_min=min_connect, cp_max=max_connect,
        *args, **kwargs )


def rebuild_db(db_pool):
    return db_pool.runOperation(__CLEAN_UP_STATEMENT)


__CREATE_VAR_FUNCTION = Template("""
CREATE OR REPLACE FUNCTION _create_variables_$type(text, integer, anyarray) RETURNS integer AS '
DECLARE
  hash_val    ALIAS FOR $$1 ;
  value_count ALIAS FOR $$2 ;
  value_array ALIAS FOR $$3 ;
BEGIN
  -- handle trivial and most common cases before locking
  IF value_count < 1 OR EXISTS (SELECT 1 FROM _var_$type WHERE hash = hash_val) THEN
    RETURN NULL ;
  END IF ;

  -- block write access to assure uniqueness of hash values
  LOCK TABLE _var_$type IN EXCLUSIVE MODE;

  -- check again after locking (coming here is rare, so we can afford it)
  IF EXISTS (SELECT 1 FROM _var_$type WHERE hash = hash_val) THEN
    RETURN NULL ;
  END IF ;

  FOR i IN 1 .. value_count LOOP
    INSERT INTO _var_$type (hash, value) VALUES (hash_val, value_array[i]) ;
  END LOOP ;

  RETURN NULL ;
END ;
' LANGUAGE plpgsql ;
""")

__CLEAN_UP_STATEMENT = Template("""
CREATE OR REPLACE FUNCTION _clean_up_db_tables() RETURNS integer AS '
DECLARE
  table RECORD ;
  tables text := '' '' ;
BEGIN
  FOR table IN
    SELECT * FROM pg_tables
      WHERE tablename LIKE ''_db_table_%''
         OR tablename LIKE ''_var_%''
      ORDER BY tablename
  LOOP
    tables := tables || '', '' || quote_ident(table.tablename) ;
  END LOOP ;

  IF character_length(trim(tables)) > 0 THEN
    EXECUTE ''DROP TABLE '' || substring(tables from 3) || '' CASCADE'' ;
  END IF ;

  CREATE TABLE _var_text    (hash text, value text) ;
  CREATE TABLE _var_bool    (hash text, value bool) ;
  CREATE TABLE _var_integer (hash text, value integer) ;

$insert_bools ;

  CREATE INDEX _index_var_text    ON _var_text    (hash);
  CREATE INDEX _index_var_integer ON _var_integer (hash);

  DROP FUNCTION _clean_up_db_tables() ;
  RETURN 1 ;
END ;
' LANGUAGE plpgsql ;

CREATE OR REPLACE FUNCTION _create_variables_bool(text, integer, anyarray) RETURNS integer AS '
BEGIN RETURN NULL; END;
' LANGUAGE plpgsql ;

$create_var_functions

CREATE OR REPLACE FUNCTION analyze_dbs() RETURNS integer AS '
DECLARE
  table_count integer := 0;
  table RECORD ;
BEGIN
  FOR table IN
    SELECT * FROM pg_tables
      WHERE tablename LIKE ''_db_table_%''
         OR tablename LIKE ''_var_%''
      ORDER BY tablename
  LOOP
    EXECUTE ''ANALYZE '' || quote_ident(table.tablename) ;
    table_count := table_count + 1;
  END LOOP ;

  RETURN table_count ;
END ;
' LANGUAGE plpgsql ;

SELECT _clean_up_db_tables() ;
""").substitute(

    insert_bools = ';\n'.join(
    "INSERT INTO _var_bool VALUES (''%s'', %s)" % (_md5hex(bool_tuple), b)
    for bool_tuple in [(True,), (False,), (False,True)]
    for b in bool_tuple ),

    create_var_functions = ''.join( __CREATE_VAR_FUNCTION.substitute(type=vtype)
                                    for vtype in ('integer', 'text') )

    )


class ObservableConnectionPool(adbapi.ConnectionPool):
    def __init__(self, *args, **kwargs):
        adbapi.ConnectionPool.__init__(self, *args, **kwargs)

        self._subscriptions = {}
        self._notifications = deque()
        self._pending = False
        self.__class__._superclass_run_interaction = adbapi.ConnectionPool._runInteraction

    def subscribe(self, event_type, observer):
        try:
            observers = self._subscriptions[event_type]
        except KeyError:
            observers = set()
            self._subscriptions[event_type] = observers
            self.runOperation("LISTEN %s" % event_type)
        observers.add(observer)

    def unsubscribe(self, event_type, observer):
        try:
            observers = self._subscriptions[event_type]
        except KeyError:
            return
        observers.remove(observer)
        if not observers:
            del self._subscriptions[event_type]
            # self.runOperation("UNLISTEN event_type") # FIXME: which thread?

    def _deliver_notifies(self):
        "Called from reactor to deliver notifications."
        notifications = self._notifications
        if not notifications:
            return

        self._pending = False
        
        # remove duplicates one by one to allow concurrent appends in threads!
        notify_set = set()
        add, pop = notify_set.add, notifications.popleft
        while notifications:
            add(pop().relname)

        call_later = reactor.callLater
        for notification in notify_set:
            try:
                observers = self._subscriptions[notification]
            except KeyError:
                continue
            for observer in observers:
                call_later(0, observer, notification)

    def _run_and_receive_notifies(self, transaction, interaction, *args, **kwargs):
        """Called concurrently in threads to run DB interactions
        and collect notifications. pyPgSQL specific."""
        result = interaction(transaction, *args, **kwargs)

        map(self._notifications.append,
            iter(transaction.conn.conn.notifies, None))
        if not self._pending and self._notifications:
            self._pending = True
            reactor.callFromThread(self._deliver_notifies)

        return result

    def _runInteraction(self, interaction, *args, **kwargs):
        return self._superclass_run_interaction(
            self._run_and_receive_notifies, interaction, *args, **kwargs)
            #self, self._run_and_receive_notifies, interaction, *args, **kwargs)


class SQLNode(AbstractNode):
    def destroy(self):
        self._exists = False
        del self._node_id

class StaticSQLNode(StaticNode):
    def __init__(self, node_id, attribute_value_dict):
        StaticNode.__init__(self, attribute_value_dict, hash(node_id))
        self._node_id = node_id
        self._exists  = True
    def destroy(self):
        self._exists = False
        del self._node_id

class DBStateAPI(object):
    def __init__(self, db):
        self.__db = db
        for attr in ('local_node', ):
            setattr(self, attr, getattr(db, attr))

class SQLNodeDB(object):
    _SQL_VIEW_BUILDER = SQLViewBuilder()
    def __init__(self, db_name, db_pool, node_identifier_attributes,
                 attribute_types=None, attribute_defaults={},
                 node_filter=None):
        self.name = db_name
        self.db_pool = db_pool
        self.node_identifier_attributes = tuple(sorted(node_identifier_attributes))
        self.node_filter = node_filter
        self._views = {}
        self._local_node = None

        if not attribute_types:
            attribute_types = {}

        attr_static = STATIC_ATTRIBUTE
        self._static_attributes = set( aname for (aname, (dynamism, atype))
                                       in attribute_types.iteritems()
                                       if dynamism == attr_static )
        self.__attributes = dict( (aname, atype)
                                  for (aname, (dynamism, atype))
                                  in attribute_types.iteritems() )
        self.__attribute_defaults = attribute_defaults or {}
        self.table_name = self.node_table_name()

        subscription = '_notify_%s' % self.table_name
        db_pool.subscribe(subscription, self._db_notify)

    def connect(self, callback):
        deferred = defer.DeferredList( (self._create_local_table(),
                                        self._create_node_table(),
                                        self._create_node_function()) )
        def return_db(_):
            return self
        deferred.addCallback(return_db)
        deferred.addCallback(callback)

    def _db_notify(self, event_type):
        print event_type

    def local_table_name(self):
        return _LOCAL_TABLE

    def local_node(self):
        if self._local_node:
            return self._local_node._static_clone()
        else:
            return None

    def node_table_name(self, name=None):
        if name is None:
            name = self.name
        else:
            try:
                view = self._views[name]
                return self.view_name(view.name)
            except:
                pass
        return "_db_table_%s_nodes" % name

    def view_name(self, name):
        return '_db_view_%s' % name

    def _create_node_table(self):
        return self._create_table( self.table_name, self.__attributes,
                                   self.__attribute_defaults, replace=True )

    def _create_local_table(self):
        return self._create_table( self.local_table_name(), self.__attributes,
                                   self.__attribute_defaults, replace=False )

    def _create_table(self, table_name, attribute_types, attribute_defaults, replace=True):
        type_mapping   = _TYPE_MAPPING_PYDB
        sql_attributes = []
        for attr_name, atype in attribute_types.iteritems():
            default = attribute_defaults.get(attr_name)
            if default:
                default = repr(default)
            else:
                default = 'NULL'
            sql_attributes.append( ",\n %s %s DEFAULT %s" % (
                attr_name, type_mapping[atype], default) )

        create_table = self._DB_TABLE_CREATE.substitute(
            replace = replace and 'true' or 'false',
            table_name = table_name,
            other_attributes = ''.join(sql_attributes),
            unique_attributes = ', '.join(self.node_identifier_attributes)
            )

        return self.db_pool.runOperation(create_table)


    _DB_TABLE_CREATE = Template("""
    CREATE OR REPLACE FUNCTION _create_$table_name() RETURNS integer AS '
    BEGIN
      IF $replace = true THEN
        IF EXISTS (SELECT 1 FROM pg_class WHERE relname = ''$table_name'') THEN
          DROP TABLE $table_name CASCADE ;
        END IF ;
      END IF ;
      IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = ''$table_name'') THEN
        CREATE TABLE $table_name (
          %(node_id)s BIGSERIAL PRIMARY KEY  $other_attributes
        ) ;
        IF character_length(trim(''$unique_attributes'')) > 0 THEN
          CREATE UNIQUE INDEX _id_attributes_$table_name
            ON $table_name ($unique_attributes) ;
        END IF ;

        CREATE OR REPLACE RULE _notify_on_update_$table_name AS
          ON UPDATE TO $table_name
          DO NOTIFY _notify_$table_name ;
      END IF ;

      DROP FUNCTION _create_$table_name() ;
      RETURN NULL ;
    END ;
    ' LANGUAGE plpgsql ;
    SELECT _create_$table_name()
    """ % {'node_id':_NODE_ID_COLUMN})

    _DB_FUNCTION_CREATE = Template("""
    CREATE OR REPLACE FUNCTION _create_$function_name() RETURNS integer AS '
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_proc WHERE proname = ''$function_name'') THEN
        $function_def
      END IF ;
      DROP FUNCTION _create_$function_name() ;
      RETURN NULL ;
    END
    ' LANGUAGE plpgsql ;
    SELECT _create_$function_name()
    """)

    def iterAttributeTypes(self):
        return self.__attributes.iteritems()

    def iterAttributeNames(self):
        return iter(sorted(self.__attributes.iterkeys()))

    def create_view(self, callback, view_spec, viewreg, **variable_initializations):
        view = SQLNodeView(self, view_spec, viewreg, self._local_node.dbid(),
                           self._static_attributes, variable_initializations)
        deferred = view._connect()

        def register(_):
            self._views[view.name] = view
            return view
        deferred.addCallback(register)
        deferred.addCallback(callback)

    def create_node(self, insert_node=True, **value_initializations):
        node = SQLDBNode(self, self.table_name, self._static_attributes)
        if insert_node:
            return node._insert(value_initializations)
        else:
            return defer.succeed(node)

    def create_local_node(self, **value_initializations):
        node = SQLDBNode(self, self.local_table_name(), self._static_attributes)
        self._local_node = node
        return node._insert(value_initializations)

    def create_function(self, function_name, function_def):
        db_function_name = function_name # '_db_func_%s_%s' % (self.name, function_name)
        function = self._DB_FUNCTION_CREATE.substitute(
            function_def  = function_def.replace("'", "''") % db_function_name,
            function_name = db_function_name
            )
        return self.db_pool.runOperation(function)

    def select_nodes(self, callback, view_spec):
        to_sql  = self._SQL_VIEW_BUILDER
        db_pool = self.db_pool

        select_name = '_local_select_%s' % view_spec.view_name
        parents = (self,)

        _create, select_statement = to_sql.build_sql_view_statement(
            self, view_spec, select_name, parents, (),
            self._local_node.dbid(), limit=_MAX_ROW_FETCH )

        variable_creates = to_sql.build_variable_tables(
            view_spec, select_name )

        if variable_creates:
            deferred = db_pool.runOperation(variable_creates)
            def run_select(_):
                # print "SELECT:", select_statement
                return db_pool.runQuery(select_statement)
            deferred.addCallback(run_select)
        else:
            deferred = db_pool.runQuery(select_statement)

        attribute_names = sorted( (attr.name for attr in view_spec.view_object.attributes.iterkeys()),
                                  reverse=True )
        node_class = StaticSQLNode
        def collect(rows):
            nodes  = []
            append = nodes.append
            attributes = {}
            for result in rows:
                node_id = result[1]
                attributes.update( izip(attribute_names, reversed(result)) )
                append( node_class(node_id, attributes) )
            return nodes

        deferred.addCallback(collect)
        deferred.addCallback(callback)

    _DB_INSERT_OR_UPDATE_NODE = Template("""
    CREATE OR REPLACE FUNCTION _insert_or_update_$table_name(integer, text[], text[]) RETURNS integer AS '
    DECLARE
      node_count ALIAS FOR $$1 ;
      col_assign ALIAS FOR $$2 ;
      id_select  ALIAS FOR $$3 ;

      ignore RECORD ;
      already_there boolean ;
    BEGIN
      LOCK TABLE $table_name IN EXCLUSIVE MODE ;

      FOR i IN 1 .. node_count LOOP
        already_there := false ;
        FOR ignore IN EXECUTE ''SELECT 1 FROM $table_name WHERE '' || (id_select[i])
        LOOP
          already_there := true ;
        END LOOP ;

        IF already_there = true THEN
          EXECUTE ''UPDATE $table_name SET '' || (col_assign[i]) ||
                  '' WHERE '' || (id_select[i]) ;

        ELSE
          INSERT INTO $table_name DEFAULT VALUES ;

          EXECUTE ''UPDATE $table_name SET '' || (col_assign[i]) ||
                  '' WHERE %(node_id)s = '' ||
                  quote_literal(currval(''${table_name}_%(node_id)s_seq'')) ;
        END IF ;
      END LOOP ;

      RETURN NULL ;
    END
    ' LANGUAGE plpgsql
    """ % {'node_id' : _NODE_ID_COLUMN} )

    def _create_node_function(self):
        self._insert_or_update_node = '_insert_or_update_%s' % self.table_name

        sql_insert_or_update_node = self._DB_INSERT_OR_UPDATE_NODE.substitute(
            table_name = self.table_name )
        return self.db_pool.runOperation( sql_insert_or_update_node )

    def add_nodes(self, nodes):
        id_attributes = self.node_identifier_attributes
##         if not id_attributes:
##             raise ValueError, "Missing ID attributes for new nodes!"
        attributes = self.__attributes.keys()
        sql_values = []
        id_selects = []
        id_set = set()
        for node in ifilter(self.node_filter, nodes):
            values    = []
            try:
                id_select= "' %s '" % ' AND '.join(
                    "%s = ''%s''" % (id_attr, str(getattr(node, id_attr)).replace("'", "''''"))
                    for id_attr in id_attributes )
            except AttributeError:
                continue

            if id_select in id_set:
                continue

            for aname in attributes:
                try: value = getattr(node, aname)
                except AttributeError:
                    continue
                values.append( "%s = ''%s''" % (aname, str(value).replace("'", "''''")) )
            if values:
                id_set.add(id_select)
                id_selects.append(id_select)
                sql_values.append( "' %s '" % ', '.join(values) )

        if sql_values:
            inserts = "SELECT %s(%d, ARRAY[%s], ARRAY[%s])" % (
                self._insert_or_update_node,
                len(sql_values),
                ', '.join(sql_values),
                ', '.join(id_selects)
                )
            return self.db_pool.runOperation(inserts)
        else:
            return None


class SQLNodeView(object): # (ReflectiveObservable):
    def __init__(self, db, spec, viewreg, local_node_id, static_attributes,
                 variable_initializations, view_name=None):
        self.name    = view_name = view_name or spec.view_name
        self.parents = parents = tuple( viewreg[parent] # raises KeyError
                                        for parent in spec.view_parents )

        self._spec      = spec
        self._viewreg   = viewreg
        self._db        = db
        self.local_node = db.local_node # method to return static local node

        loops = list(spec.loops)
        external_variables = []
        if spec.select_buckets:
            known_variables = set(var[0].name for var in loops)
            for parent in parents:
                for variable, values in parent.variables():
                    variable_name = variable.name
                    if variable_name not in known_variables:
                        loops.append( (variable, values) )
                        known_variables.add(variable_name)
                        external_variables.append(variable_name)

        self._variable_list  = tuple(loops)
        self._variable_names = tuple(var[0].name for var in loops)

        to_sql = _SQL_VIEW_BUILDER # global instance

        (self._sql_create_statement,
         self._sql_select_statement) = to_sql.build_sql_view_statement(
            db, spec, self.name, parents, external_variables,
            local_node_id, _MAX_ROW_FETCH )

        self._sql_create_vars = to_sql.build_variable_tables(spec, view_name)

        self._db_view_name   = db_view_name = db.view_name(view_name)
        self._attribute_names = tuple(sorted(attr.name for attr in spec.view_object.attributes.iterkeys()))

        self._node_class = StaticSQLNode
        self._prepare_statements()

    def _connect(self):
        db_pool = self._db.db_pool

        create_variable_tables = self._sql_create_vars
        if create_variable_tables:
            deferred = db_pool.runOperation(create_variable_tables)
        else:
            deferred = defer.succeed(1)

        def create_view(_):
            return db_pool.runOperation(self._sql_create_statement)
        deferred.addCallback(create_view)

        def register(_):
            self._viewreg.register(self)
            return self
        deferred.addCallback(register)
        return deferred

    def getSpec(self):
        return self._spec

    def getSelect(self):
        return self._sql_select_statement

    def _prepare_statements(self):
        db_view_name = self._db_view_name
        variables    = ','.join(self._variable_names)
        attributes   = ','.join(self._attribute_names)

        self._select_len     = ("SELECT count(*) FROM %s" % db_view_name)
        self._select_nodes   = ("SELECT %s,%s FROM %s" %
                                (_NODE_ID_COLUMN, attributes, db_view_name) )
        self._select_bucket  = self._select_nodes + ' WHERE %s'

        if variables:
            self._select_all = ("SELECT %s,%s,%s FROM %s ORDER BY %s" %
                                (variables, _NODE_ID_COLUMN, attributes,
                                 db_view_name, variables) )
        else:
            self._select_all = self._select_nodes

    def variables(self):
        return self._variable_list

    def _multi_variable_iterator(self, variables):
        if not variables:
            yield ()
        else:
            variable, values = variables[0]
            variable_name = variable.name
            for loop_values in self._multi_variable_iterator(variables[1:]):
                for value in values:
                    if hasattr(value, 'evaluate'):
                        value = value.evaluate(value_dict)
                    yield loop_values + (value,)

    def iter_variables(self):
        """Builds an iterator that returns one tuple for each combination of
        values of the loop variables.
        It returns () if there are no variables."""
        return self._multi_variable_iterator(self._variable_list)

    def node_count(self, callback): # __len__(self)
        deferred = self._db.db_pool.runQuery(self._select_len)

        def unpack_one(row):
            return row[0]

        deferred.addCallback(unpack_one)
        deferred.addCallback(callback)

    def _build_node_iterator(self, rows):
        node_class = self._node_class
        attributes = self._attribute_names
        values = {}
        fill_dict = values.update
        for row in rows:
            fill_dict( izip(attributes, row[1:]) )
            yield node_class(row[0], values)

    def iterNodes(self, callback): # __iter__(self)
        deferred = self._db.db_pool.runQuery(self._select_nodes)
        deferred.addCallback(self._build_node_iterator)
        deferred.addCallback(callback)

    def iterBucket(self, callback, *val_tuple):
        if len(val_tuple) == 1 and isinstance(val_tuple[0], tuple):
            val_tuple = val_tuple[0]
        val_compare = ' AND '.join('%s = %r' % item
                                   for item in izip(self._variable_names, val_tuple))

        deferred = self._db.db_pool.runQuery(
            self._select_bucket % (val_compare or 'true') )
        deferred.addCallback(self._build_node_iterator)
        deferred.addCallback(callback)

    def iterBuckets(self, callback):
        var_count  = len(self._variable_names)
        if var_count == 0:
            def bucket_iterator_callback(node_iterator):
                # create an iterator over a fake single bucket
                callback(iter( [((), tuple(node_iterator))] ))
            self.iterNodes(bucket_iterator_callback)
            return

        deferred = self._db.db_pool.runQuery(self._select_all)

        id_pos     = var_count
        attr_start = id_pos+1
        node_class = self._node_class
        attributes = self._attribute_names
        def build_node_iterator(rows):
            values = {}
            fill_dict = values.update
            def build_node(row):
                fill_dict( izip(attributes, row[attr_start:]) )
                return node_class(row[id_pos], values)

            for variables, node_tuples in groupby( imap(tuple, rows),
                                                   (lambda t: t[:var_count]) ):
                yield (variables, map(build_node, node_tuples))

        deferred.addCallback(build_node_iterator)
        deferred.addCallback(callback)


class SQLDBNode(object):
    def __init__(self, database, table_name, static_attributes,
                 change_observer=None):
        self._exists     = True
        self._node_id    = -1
        self._table_name = table_name
        self._database   = database
        self._static_attributes = set(static_attributes)
        self._attributes = frozenset()

        self.setChangeObserver(change_observer)

    def __hash__(self):
        return hash(self._node_id)

    def __dummy(self, *args):
        pass

    _insert_template = Template("""
    INSERT INTO $table_name ($columns) VALUES $values ;
    SELECT currval('${table_name}_%s_seq')
    """ % _NODE_ID_COLUMN)

    _refresh_template = Template("""
    SELECT * FROM $table_name WHERE %s = $node_id
    """ % _NODE_ID_COLUMN)

    _store_template = Template("""
    UPDATE $table_name SET $values WHERE %s = $node_id
    """ % _NODE_ID_COLUMN)

    def dbid(self):
        return self._node_id

    def _insert(self, callback, values):
        db_pool = self._database.db_pool
        names, values = zip( *values.items() )

        deferred = db_pool.runQuery(self._insert_template.substitute(
            table_name = self._table_name,
            columns    = ','.join(names),
            values     = repr(tuple(values))
            ))

        def set_node_id(result_tuple):
            self._node_id = node_id = result_tuple[0][0]
            self._insert  = self.__dummy
            self._refresh_query   = self._refresh_template.substitute(
                node_id=node_id, table_name=self._table_name )
            self._update_template = Template(self._store_template.safe_substitute(
                node_id=node_id, table_name=self._table_name ))

            return self._refresh() # returns self

        deferred.addCallback(set_node_id)
        deferred.addCallback(callback)

    def _set_values(self, value_dict_container):
        value_dict = value_dict_container[0]
        attribute_names = self._attributes
        for name in attribute_names:
            if not value_dict.has_key(name):
                delattr(self, name)
        self.__dict__.update(
            (name, value) for (name, value) in value_dict.items() # not iteritems!
            if name and not name.startswith('_') )
        self._attributes = frozenset(sorted(value_dict.keys()))
        return self

    def _refresh(self, callback):
        deferred = self._database.db_pool.runQuery(self._refresh_query)
        deferred.addCallback(self._set_values)
        deferred.addCallback(callback)

    def _store(self):
        values = ', '.join( "%s = %s" % (name, getattr(self, name))
                            for name in self._attributes
                            if name not in self._static_attributes )

        return self._database.db_pool.runOperation(
            self._update_template.substitute(values=values) )

    def _static_clone(self):
        return StaticNode( dict(self._iter_attributes()) )

    def _iter_attributes(self):
        return ((name, getattr(self, name)) for name in self._attributes)

    def setChangeObserver(self, observer):
        self._notify_update = observer or self.__dummy

    def __repr__(self):
        return "node[%s]" % ','.join( "%s=%r" % (name, getattr(self,name))
                                      for name in sorted(self._attributes) )


def _build_node_class(db, source, attributes=None, static_attributes=()):
    """Build a new node class.
    For views, attributes are converted using the expressions
    defined in the view specification.
    """
    if not attributes:
        attributes = {}

    class SQLViewNode(SQLNode):
        _attributes = tuple(sorted(attr.name for attr in attributes.iterkeys()))
        _dependencies = {}
        __slots__ = ('_node_id', '_hashval') + _attributes
        def __init__(self, node_id):
            self._exists   = True
            self._node_id = node_id
            self._hashval = hash(node_id)

    dependencies = SQLViewNode._dependencies
    for attr, function in attributes.iteritems():
        aname = attr.name
        if function and function.isConstant():
            value = function.evaluate()
            f_dependencies = ()
        else:
            value = SQLViewAttributeDescriptor(db, aname, source,
                                               static=aname in static_attributes)
            if function:
                f_dependencies = function.getDependencies()
            else:
                f_dependencies = (attr,)
        setattr(SQLViewNode, aname, value)
        dependencies[aname] = f_dependencies

    return SQLViewNode


class SQLAttributeDescriptor(object):
    __slots = ('db_cursor', 'statement')
    def __init__(self, db, attr_name, source, static=False):
        self.db        = db
        self.db_pool   = db.db_pool
        self.static    = static
        self.attr_name = attr_name
        self.get_statement = ("SELECT %s FROM %s      WHERE %s = %%d" %
                              (attr_name, source, _NODE_ID_COLUMN) )
        self.set_statement = ("UPDATE %s SET %s = %%s WHERE %s = %%d" %
                              (source, attr_name, _NODE_ID_COLUMN) )
    def __get__(self, instance, owner):
        if instance is None: return self
        if not instance._exists:
            raise AttributeError
        try:
            return self.value
        except AttributeError:
            pass
        db_pool = self.db_pool
        deferred = db_pool.runQuery(self.get_statement, (instance._node_id,))
        # FIXME from here ...
        result = cursor.fetchone()
        if result:
            value = result[0]
            if self.static:
                self.value = value
            return value
        else:
            instance.destroy()
            return None
    def __set__(self, instance, value):
        if self.static:
            raise AttributeError, "can't set attribute value"
        self.db_cursor.execute(self.set_statement, (value, instance._node_id))
        self.db.commit()


class SQLViewAttributeDescriptor(SQLAttributeDescriptor):
    def __set__(self, instance, value):
        raise AttributeError, "can't set attribute value"


try:
    from optimize import bind_all
    import sys
    bind_all(sys.modules[__name__])
    del sys, bind_all
except:
    pass
