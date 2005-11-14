import re
from itertools import *
from string    import Template

from helpers import _TYPE_MAPPING_PYDB, _md5hex

from sqldb import _NODE_ID_COLUMN
from slow.model import slosl_model
from mathml.utils.sqlterm import SqlTermBuilder, tree_converters

SLOSL_SQL = 'slosl-sql'

class SQLExpressionBuilder(SqlTermBuilder):
    _INTERVAL_NOTATION = {
        u'closed'      : u'BETWEEN (%s)     AND (%s)    '.replace(u'  ', u''),
        u'closed-open' : u'BETWEEN (%s)     AND ((%s)-1)'.replace(u'  ', u''),
        u'open-closed' : u'BETWEEN ((%s)+1) AND (%s)    '.replace(u'  ', u''),
        u'open'        : u'BETWEEN ((%s)+1) AND ((%s)-1)'.replace(u'  ', u''),
        }

    def _handle_interval(self, operator, operands, status):
        assert operator[:9] == u'interval:'
        return [ self._INTERVAL_NOTATION[ operator[9:] ] % tuple(operands) ]

tree_converters.register_converter(SLOSL_SQL, SQLExpressionBuilder())


class SQLViewBuilder(object):
    _SQL_SELECT_TEMPLATE = Template("""
    $comment_out_create CREATE VIEW $view_name AS
    SELECT $distinct node.%(node_id)s, 1 AS _noderank, $variables $select_attribute_conversion
    FROM (SELECT * FROM $local_table WHERE %(node_id)s = '$local_node_id') AS local,
         $parent_union AS node
    WHERE ($where) AND ($having)
    ORDER BY _noderank
    $select_limit
    """ % {'node_id':_NODE_ID_COLUMN})

    _SQL_SINGLE_RANK_TEMPLATE = Template("""
    $comment_out_create CREATE VIEW $view_name AS
    SELECT _noderank, _node_id, $variables $select_attribute_conversion
    FROM (
      SELECT DISTINCT node.%(node_id)s, $variable_select $select_attributes, (
        SELECT COUNT(*)
        FROM (SELECT *
          FROM $parent_union AS node
          WHERE ($where) AND ($having)
         ) AS _node
        WHERE ($local_rank_expression) $cmp ($rank_expression)
      ) AS _noderank
      FROM (SELECT * from $local_table WHERE %(node_id)s = '$local_node_id') AS local,
           $variable_source
           (SELECT node.*
            FROM $parent_union AS node,
                 (SELECT * from $local_table WHERE %(node_id)s = '$local_node_id') AS local
            WHERE ($where)
           ) AS node
      WHERE ($having)
    ) AS node
    WHERE (_noderank <= $max)
    ORDER BY $variables _noderank
    $select_limit
    """ % {'node_id':_NODE_ID_COLUMN})

    _SQL_MULTI_PARENT_RANK_TEMPLATE = Template("""
    CREATE VIEW _parents_$view_name AS
    SELECT DISTINCT node.%(node_id)s, $variable_select $select_attributes
    FROM (SELECT * FROM $local_table WHERE %(node_id)s = '$local_node_id') AS local,
         $variable_source
         (SELECT node.*
          FROM $parent_union AS node,
               (SELECT * from $local_table WHERE %(node_id)s = '$local_node_id') AS local
          WHERE ($where)
         ) AS node
    WHERE ($having)
    ;

    CREATE VIEW $view_name AS
    SELECT _noderank, _node_id, $variables $select_attribute_conversion
    FROM (
      SELECT node.%(node_id)s, $variable_select $select_attributes, (
        SELECT COUNT(*)
        FROM _parents_$view_name AS _node
        WHERE ($local_rank_expression) $cmp ($rank_expression)
      ) AS _noderank
      FROM (SELECT * FROM $local_table WHERE %(node_id)s = '$local_node_id') AS local,
           _parents_$view_name AS node
    ) AS node
    WHERE (_noderank <= $max)
    ORDER BY $variables _noderank
    $select_limit
    """ % {'node_id':_NODE_ID_COLUMN})

    _SQL_RANK_TEMPLATE = _SQL_SINGLE_RANK_TEMPLATE

    _DISTINCT = "DISTINCT ON %s" % _NODE_ID_COLUMN


    def __relative(rel_val, expr):
        return "abs(( %s ) - ( %s ))" % (rel_val, expr)
    def __absolute(expr):
        return expr

    _RANK = {
        'lowest'   : ('<=', __absolute),
        'highest'  : ('>=', __absolute),
        'closest'  : ('<=', __relative),
        'furthest' : ('>=', __relative),
        }
    del __relative, __absolute


    _DUMMY_TABLE  = '(SELECT NULL)'

    def build_sql_view_statement(self, db, model, new_view_name, parent_models,
                                 external_variables, local_node_id, limit=-1):
        select_attributes = self._build_attribute_select(model)
        expr_to_sql = self._expr_to_sql

        parent_union = self._build_parent_join(db, model, parent_models,
                                               external_variables)

        where  = expr_to_sql(model.where)  or 'True'
        having = expr_to_sql(model.having) or 'True'

        if limit >= 0:
            select_limit = 'LIMIT %d' % limit
        else:
            select_limit = ''

        variables, variable_select, variable_source = self._build_var_select(
            model, external_variables)

        rank_function = model.ranked
        if rank_function and rank_function.name:
            params = map(expr_to_sql, rank_function.parameters)
            cmp, rank_builder = self._RANK[ rank_function.name ]
            rank_expr = rank_builder(*params[1:])
            max_nodes = expr_to_sql(params[0])

            select_template = Template(self._SQL_RANK_TEMPLATE.safe_substitute(
                select_attributes = self._build_attribute_select(model),
                cmp = cmp,
                rank_expression       = rank_expr,
                local_rank_expression = rank_expr.replace(' node.', ' _node.'), # FIXME?
                local_where = where.replace(' node.', ' _node.'), # FIXME?
                max = max_nodes
                ))
        else:
            select_template = self._SQL_SELECT_TEMPLATE

        select_view = Template(select_template.safe_substitute(
                view_name     = db.view_name(new_view_name),
                distinct      = model.distinct and self._DISTINCT or '',
                parent_union  = parent_union,
                where         = where,
                having        = having,
                local_node_id = local_node_id,
                local_table   = db.local_table_name(),
                variables     = variables,
                variable_select = variable_select,
                variable_source = variable_source,
                select_attribute_conversion = self._build_attribute_conversion(model)
                ))

        return ( select_view.substitute(comment_out_create='',   select_limit=''),
                 select_view.substitute(comment_out_create='--', select_limit=select_limit) )

    def _var_table_name(self, var_name, values):
        if isinstance(values, Variable):
            return str(values) # untested
        elif isinstance(values, (IntList, XRange)):
            return "_var_integer"
        else:
            return "_var_%s" % _TYPE_MAPPING_PYDB[ type(values[0]) ]

    def _find_sequences(self, values):
        if isinstance(values, AnyList):
            return ( values.elements ,)
        elif isinstance(values, XRange):
            return ( values ,)
        elif isinstance(values, IntList):
            return values.ranges
        else:
            assert False, "Invalid type for values: %s" % type(values)


    _VARIABLE_SELECT_TEMPLATE = Template(
        "(SELECT value AS $var_name FROM $table $where) AS _ignore_$var_name, " )

    def _build_var_select(self, model, external_variables):
        select_template = self._VARIABLE_SELECT_TEMPLATE

        var_names = []
        variable_selects = []
        variable_sources = []
        for variable in model.iterforeach():
            var_name = variable.name
            values   = variable.parsed_declaration
            var_names.append( "%s, " % var_name )
            variable_selects.append( "%s AS %s, " % (var_name, var_name) )

            table_name = self._var_table_name(var_name, values)
            hash_vals = map(_md5hex, self._find_sequences(values))
            if hash_vals:
                where = 'WHERE %s' % ' OR '.join( "hash = '%s'" % hash_val for hash_val in hash_vals )
            else:
                where = ''

            variable_sources.append( select_template.substitute(
                table=table_name, where=where, var_name=var_name) )

        if external_variables:
            for var_name in external_variables:
                var_names.append( "%s, " % var_name )
                variable_selects.append( "%s AS %s, " % (var_name, var_name) )

        return [ ''.join(l)
                 for l in (var_names, variable_selects, variable_sources) ]

    def build_variable_tables(self, model, view_name):
        if model.foreach_count == 0:
            return None
        template = "SELECT _create_variables_%s('%s', %d, ARRAY[%s])"
        md5hex   = _md5hex
        types    = _TYPE_MAPPING_PYDB
        find_sequences = self._find_sequences

        selects = []
        for variable in model.iterforeach():
            var_name = variable.name
            values   = variable.parsed_declaration
            table_name = self._var_table_name(var_name, values)
            sequences  = find_sequences(values)
            val_type   = types[ type(sequences[0]) ]
            for seq in sequences:
                hash_val = md5hex(seq)
                values   = tuple(seq) # convert to straight values
                selects.append( template % (val_type, hash_val, len(values),
                                            ','.join(imap(str, values))) )
        return ';'.join(selects)

    def _expr_to_sql(self, expression):
        if hasattr(expression, 'serialize'):
            # FIXME: collect dependencies somewhere!!
            return expression.serialize(SLOSL_SQL)
        else:
            return ''

    def _build_parent_join(self, db, model, parent_models, external_variables):
        db_table_name = db.node_table_name
        if len(parent_models) == 1:
            return db_table_name(parent_models[0].name)

        all_attributes = frozenset( attr.name
                                    for attr in model.attribute_dependencies
                                    if attr.object_name == 'node' )
        all_attributes.update(external_variables)

        sorted_attributes = tuple(sorted(all_attributes))

        selections = []
        for parent in parents:
            parent_attributes = set(
                attr.name for attr in parent.iterselect() )

            if external_variables:
                parent_attributes.update(
                    var.name for var in parent.iterforeach() )

            unmatched_attributes = all_attributes - parent_attributes

            attributes = []
            for attr in sorted_attributes:
                if attr in unmatched_attributes:
                    attr = 'NULL AS %s' % attr
                attributes.append(attr)

            selections.append(
                "(SELECT %s FROM %s)" % (','.join(attributes), db_table_name(parent.name))
                )

        return '(%s)' % ' UNION '.join(selections)

    def _build_attribute_conversion(self, model):
        attributes = []
        for attr in sorted(model.iterselect()):
            expression = attr.value
            if expression:
                select = "%r AS %s" % (expression, attr.name)
            else:
                select = attr.name
            attributes.append(select)
        return ', '.join(attributes)

    def _build_attribute_select(self, model):
        return ', '.join(sorted(
            str(attr) for attr in model.attribute_dependencies
            if attr.object_name == 'node')) or 'node.*'

    def _build_loop_select(self, model):
        return ','.join( model.iterforeachnames() )
