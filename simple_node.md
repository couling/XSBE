# `xsbe.simple_node`

This library is a simplified object model for representing XML content.  It should be simpler to traverse than DOM and 
also avoids common pitfalls of code that uses DOM.  At this time the parser is dependent on DOM however in future this 
will be phased out.

## Model

It's composed of only two very simple classes:

### `xsbe.simple_node.Name`

Represents the name of an XML element or attribute.  It's only two fields are:
- `name: str` name
- `namespace: Optional[str]` namespace **URI** *(not namespace prefix!)*


### `xsbe.simple_node.XmlNode`

Represents a single XML Element.  It has only three fields:

- `name: Name` The element name
- `attributes: Dict[Name, str]` The element's attributes.
- `children: List[Union[XmlNode, str]]` All child elements (CDATA is not currently supported).


## XML Documents can be parsed and formatted with:

### `xsbe.simple_node.load(file: TextIO) --> XmlNode` 
 
   loads a document from a file
   
### `xsbe.simple_node.loads(document: str) --> XmlNode` 
 
   loads a document from a string
   
### `xsbe.simple_node.dumps`

   ```
   xsbe.simple_node.dumps(
       node: XmlNode, 
       namespace_map: Optional[Dict[str, str]] = None, 
       write_xmlns: bool = True,
       default_namespace: Optional[str] = ...) -> str
   ```

Writes an XmlNode to a string. 
 
 `node` is the node to write. 
 
 `namespace_map` is a dict mapping from namespace URIs 
to a prefix.  If this is not specified, prefixes will be assigned automatically in alphabetical order.  

`write_xmlns` can be used to disable writing `xmlns:foo="..."` type attributes.  This is useful if the node being 
dumped is a snippet.  It MUST only be set `False` if `write_xmlns` is populated.  

`default_namespace` specifies which namespace is the default namespace (the one applied to un-prefixed nodes).  If 
`None`, all nodes within a namespace will be dumped with a namespace prefix.

### `xsbe.simple_node.dumps`

   ```
   xsbe.simple_node.dumps(
       target: TextIO,
       node: XmlNode, 
       namespace_map: Optional[Dict[str, str]] = None, 
       write_xmlns: bool = True,
       default_namespace: Optional[str] = ...) -> str
   ```

Writes an XmlNode to a file object.

 `target` The file object to write to. 
 
 `node` is the node to write. 
 
 `namespace_map` is a dict mapping from namespace URIs 
to a prefix.  If this is not specified, prefixes will be assigned automatically in alphabetical order.  

`write_xmlns` can be used to disable writing `xmlns:foo="..."` type attributes.  This is useful if the node being 
dumped is a snippet.  It MUST only be set `False` if `write_xmlns` is populated.  

`default_namespace` specifies which namespace is the default namespace (the one applied to un-prefixed nodes).  If 
`None`, all nodes within a namespace will be dumped with a namespace prefix.