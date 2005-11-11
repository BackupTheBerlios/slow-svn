try:
    from psyco.classes import *
except: pass

#from itertools import *

from specparser import Function, Variable
from saxparser  import *

from xdr_model   import XdrDataTypes, XdrAttributeModel
from slosl_model import SloslStatement


class XdrData(object):
    def __init__(self, data_description=None):
        self.setDataDescription(data_description)
    def setDataDescription(self, data_description):
        self.data_description = data_description
    def getDataDescription(self):
        if self.data_description:
            return self.data_description
        else:
            return ()

class NamedXdrData(XdrData):
    def __init__(self, name, data_description=None):
        XdrData.__init__(self, data_description)
        self.name = name

class Message(NamedXdrData):
    def __init__(self, name, header_ref=None, fields=None):
        NamedXdrData.__init__(self, name, fields)
        self.header_ref = header_ref
    def __repr__(self):
        return "Message{%s}[%s]" % (
            self.header_ref or '',
            ','.join(str(f) for f in self.getDataDescription())
            )

class Header(object):
    def __repr__(self):
        return "Header[%s]" % ','.join(str(f) for f in self.getDataDescription())

class NamedHeader(Header, NamedXdrData):
    pass

class AnonymousHeader(Header, XdrData):
    pass


############################################################
## SAX Parsers
############################################################

class SloslDefinitionParser(ReflectiveSaxHandler):
    NAMESPACE_SLOSL="slosl"
    def __init__(self):
        super(SloslDefinitionParser, self).__init__()
        self.statements = []

    class ViewDef(object):
        def __init__(self, param_dict, qos):
            self.qos_statements    = qos
            self.view_name         = param_dict['createview']
            self.view_attributes   = param_dict['select']
            self.select_distinct   = param_dict['distinct']
            self.object_select     = { 'node' : param_dict['ranked'] }
            self.view_parents      = param_dict['from']
            self.variable_options  = tuple( param_dict['with'].iteritems() )
            self.where_expression  = param_dict['where']
            self.having_expression = param_dict['having']
            self.loops             = param_dict['foreach']
            self.select_buckets    = param_dict['buckets']

    def viewdef(self):
        return self.ViewDef(self.parameters, self.qos)

    def __init_state(self, view_name):
        self.qos = []
        self.parameters = parameters = {
            'where'   : True,
            'having'  : True,
            'from'    : [],
            'ranked'  : None,
            'buckets' : False,
            'distinct': False
            }
        parameters['foreach'] = []
        parameters['select']  = {}
        parameters['with']    = {}
        parameters['createview'] = view_name

    @tag_context('viewdef', namespace=NAMESPACE_SLOSL)
    def __startElementNS(self, (namespace, name), qname, attributes):
        self.discard_data()
        get_attribute = self.attribute

        if name == 'viewdef':
            self.__init_state(get_attribute(attributes, 'name'))
        elif name in ('select', 'with'):
            self.current_name = get_attribute(attributes, 'name')
        elif name == 'ranked':
            self.current_parameters = []
            self.parameters['ranked'] = Function(
                get_attribute(attributes, 'function'),
                self.current_parameters )
        elif name == 'foreach':
            if attributes.get('bucket') == 'true':
                self.parameters['buckets'] = True
            else:
                self.parameters['foreach'].append(
                    (Variable(get_attribute(attributes, 'variable')),
                     (get_attribute(attributes, 'range_min', None),
                      get_attribute(attributes, 'range_max')))
                    )

    @tag_context('viewdef', namespace=NAMESPACE_SLOSL)
    def __endElementNS(self, (namespace, name), qname):
        if name in ('select', 'with'):
            self.parameters[name][self.current_name] = self.join_data()
            del self.current_name
        elif name == 'from':
            self.parameters[name].append( self.join_data() )
        elif name in ('having', 'where'):
            self.parameters[name] = self.join_data()
        elif name == 'parameter':
            self.current_parameters.append( self.join_data() )
        elif name == 'ranked':
            del self.current_parameters
        elif name == 'viewdef':
            self.statements.append( self.viewdef() )


class XdrDefinitionParser(ReflectiveSaxHandler):
    NAMESPACE_XDR = "http://www.ietf.org/rfc/rfc1014.txt"
    def __init__(self):
        super(XdrDefinitionParser, self).__init__()
        self.__current_container = []
        self.__containers = []

    def finish_containers(self):
        container = self.__current_container
        self.__current_container = []
        del self.__containers[:]
        return container

    def current_container(self):
        return self.__current_container

    @tag_context(namespace=NAMESPACE_XDR)
    def __startElementNS(self, (namespace, name), qname, attributes):
        get_attribute = self.attribute

        if name == 'structure':
            new_container = []
            self.__current_container.append( (name, new_container) )
            self.__containers.append(self.__current_container)
            self.__current_container = new_container
        else:
            self.__current_container.append(
                (name, get_attribute(attributes, 'name'),
                 XdrDataTypes.TYPE_DICT[name],
                 tuple( (a[0][1], a[1]) for a in attributes.items()
                        if a[0][1] != 'name' )) )

    @tag_context(namespace=NAMESPACE_XDR)
    def __endElementNS(self, (namespace, name), qname):
        if name == 'structure':
            self.__current_container = self.__containers.pop()


class OverlayDefinitionParser(SloslDefinitionParser, XdrDefinitionParser):
    NAMESPACE_LOCAL = "test"
    def __init__(self):
        super(OverlayDefinitionParser, self).__init__()
        self.known_types    = {}
        self.known_messages = {}
        self.known_headers  = {}
        self.known_attributes = {}
        self.known_transports = {}

    @tag_context('message', namespace=NAMESPACE_LOCAL)
    def __message_startElementNS(self, (namespace, name), qname, attributes):
        get_attribute = self.attribute
        if name == 'message':
            header_ref = get_attribute(attributes, 'header', None)
            self.current_message = Message(
                get_attribute(attributes, 'name'), header_ref )
        elif name == 'data':
            self.finish_containers()

    @tag_context('message', namespace=NAMESPACE_LOCAL)
    def __message_endElementNS(self, (namespace, name), qname):
        if name == 'message':
            self.known_messages[self.current_message.name] = self.current_message
            del self.current_message
        elif name == 'data':
            self.current_message.setDataDescription( self.finish_containers() )
        elif name == 'header':
            if hasattr(self, 'current_message'):
                self.current_message.setHeader(self.current_header)


    @tag_context('header', namespace=NAMESPACE_LOCAL)
    def __header_startElementNS(self, (namespace, name), qname, attributes):
        get_attribute = self.attribute
        self.finish_containers()
        header_name = get_attribute(attributes, 'name', None)
        if header_name:
            self.current_header = NamedHeader(header_name, self.current_container())
        else:
            self.current_header = AnonymousHeader(self.current_container())

    @tag_context('overlay', namespace=NAMESPACE_LOCAL)
    def __overlay_endElementNS(self, (namespace, name), qname):
        if name == 'header' and hasattr(self.current_header, 'name'):
            self.known_headers[self.current_header.name] = self.current_header

    @tag_context('types', namespace=NAMESPACE_LOCAL)
    def __types_startElementNS(self, (namespace, name), qname, attributes):
        if name == 'type':
            self.finish_containers()
            self.known_types[ self.attribute(attributes, 'name') ] = self.current_container()

    @tag_context('types', namespace=NAMESPACE_LOCAL)
    def __types_endElementNS(self, (namespace, name), qname):
        if name == 'types':
            self.finish_containers()

    @tag_context('node-attributes', namespace=NAMESPACE_LOCAL)
    def __attributes_startElementNS(self, (namespace, name), qname, attributes):
        if name == 'attribute':
            self.known_attributes[ self.attribute(attributes, 'name') ] = \
                                   self.attribute(attributes, 'type')

    @tag_context('transports', namespace=NAMESPACE_LOCAL)
    def __transports_startElementNS(self, (namespace, name), qname, attributes):
        if name == 'transport':
            self.known_transports[ self.attribute(attributes, 'name') ] = \
                                   self.attribute(attributes, 'type')


############################################################
## some tests as __main__
############################################################

if __name__ == '__main__':
    example_message = '''
<overlay xmlns="%(local_ns)s"
         xmlns:slosl="%(slosl_ns)s"
         xmlns:xdr="%(xdr_ns)s">
  <types>
    <type name="ID128">
      <xdr:farray name="ID128" length="16">
        <xdr:char />
      </xdr:farray>
    </type>
  </types>

  <node-attributes>
    <attribute name="id"      type="ID128" />
    <attribute name="latency" type="int" />
    <attribute name="alive"   type="bool" />
  </node-attributes>

  <transports>
    <transport type="TCP" name="reliable" />
    <transport type="UDP" name="besteffort" />
  </transports>

  <messages>
    <header name="myHeader1">
      <xdr:opaque name="id" opaque_type="ID128" />
    </header>

    <message name="myMType1" transport="reliable" header="myHeader1">
      <data>
        <xdr:boolean name="some_bool_data" />
        <xdr:structure>
          <xdr:boolean name="whatsin" />
          <xdr:char    name="mychar" />
        </xdr:structure>
        <xdr:varray name="nodes" node_view="chord_fingers" bucket="i=(1:3)"/>
      </data>
    </message>

    <message name="myMType2" transport="besteffort">
      <data>
        <xdr:opaque name="id" attribute="id" size="16" />
        <xdr:int    name="some_int" />
      </data>
    </message>
  </messages>

  <node-views>
    <slosl:node-view name="circle_neighbours">
      <slosl:select name="id" />
      <slosl:select name="addr" />
      <slosl:ranked function="lowest">
        <slosl:parameter>n_count</slosl:parameter>
        <slosl:parameter>min(abs(local.id - node.id),
                       max_id - abs(local.id - node.id))</slosl:parameter>
      </slosl:ranked>
      <slosl:from>db</slosl:from>
      <slosl:with name="local" />
      <slosl:with name="n_count" />
      <slosl:with name="max_id">2^160</slosl:with>
    </slosl:node-view>

    <slosl:node-view name="chord_fingers">
      <slosl:select name="id" />
      <slosl:select name="addr" />
      <slosl:ranked function="highest">
        <slosl:parameter>i+1</slosl:parameter>
        <slosl:parameter>dist(local.id, node.id)</slosl:parameter>
      </slosl:ranked>
      <slosl:from>db</slosl:from>
      <slosl:with name="local" />
      <slosl:with name="log_nodes" />
      <slosl:having>dist(local.id, node.id) in (2^i : 2^(i+1))</slosl:having>
      <slosl:foreach variable="i" range_min="0" range_max="log_nodes" />
    </slosl:node-view>
  </node-views>

  <rules>
    <message-rule name="myMType1_in" event="incoming" message_name="myMType1">
    </message-rule>
  </rules>
</overlay>
''' % { 'local_ns' : OverlayDefinitionParser.NAMESPACE_LOCAL,
        'xdr_ns'   : XdrDefinitionParser.NAMESPACE_XDR,
        'slosl_ns' : SloslDefinitionParser.NAMESPACE_SLOSL
        }

    try:
        from cStringIO import StringIO
    except:
        from StringIO  import StringIO

    try:
        import psyco
        psyco.profile()
        print "Using Psyco."
    except:
        pass

    result = OverlayDefinitionParser.parse( StringIO(example_message) )
    print result.known_messages
    print result.known_headers
    print result.known_types
    print result.known_attributes
    print result.known_transports
