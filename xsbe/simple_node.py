from typing import Optional, Dict, List, Union, TextIO, Set, Generator
from dataclasses import dataclass, field
import io
import itertools
from xml.sax.saxutils import escape as _escape
from xml.dom.minidom import parse as _parse, parseString as _parseString
import xml.dom

__all__ = ["XmlNode", "Name", "dump", "dumps", "from_dom"]


@dataclass(frozen=True)
class Name:
    name: str
    namespace: Optional[str] = field(default=None)

    def __iter__(self):
        yield self.name
        yield self.namespace

    def __repr__(self):
        return self.name if self.namespace is None else f"{self.name}:{self.namespace}"


class XmlNode:
    name: Name
    attributes: Dict[Name, str]
    children = List[Union["XmlNode", str]]

    def __init__(self, name: Name):
        self.name = name
        self.attributes = {}
        self.children = []

    def __repr__(self) -> str:
        result = io.StringIO()
        result.write("<")
        result.write(repr(self.name))
        result.write(" ...")
        if self.children:
            result.write(">...</")
            result.write(self.name.name)
            result.write(">")
        else:
            result.write("/>")
        return result.getvalue()

    def __getitem__(self, name: Union[str, Name]) -> str:
        return self.attributes[self._normalise_name(name)]

    def __setitem__(self, name: Union[str, Name], value: str):
        self.attributes[self._normalise_name(name)] = value

    def get(self, name: Union[str, Name], default: Optional[str] = None) -> str:
        return self.attributes.get(self._normalise_name(name), default)

    def setdefault(self, name: Union[str, Name], default: Optional[str] = None) -> str:
        return self.attributes.setdefault(self._normalise_name(name), default)

    def _normalise_name(self, name: Union[str, Name]) -> Name:
        if isinstance(name, str):
            return Name(name, None)
        else:
            return name


def from_dom(node) -> XmlNode:
    assert node.nodeType == xml.dom.Node.ELEMENT_NODE
    result = XmlNode(Name(namespace=node.namespaceURI, name=node.localName))
    for attribute, value in node.attributes.itemsNS():
        attribute_ns, attribute_name = attribute
        if attribute_ns not in ("http://www.w3.org/2000/xmlns/", "http://www.w3.org/2001/XMLSchema-instance"):
            result[Name(attribute_name, attribute_ns)] = value
    for child in node.childNodes:
        if child.nodeType == xml.dom.Node.COMMENT_NODE:
            continue
        if child.nodeType == xml.dom.Node.TEXT_NODE:
            if child.nodeValue.strip():
                result.children.append(child.nodeValue)
        else:
            result.children.append(from_dom(child))
    return result


def dumps(node: XmlNode, namespace_map: Optional[Dict[str, str]] = None, write_xmlns: bool = True,
          default_namespace: Optional[str] = ...) -> str:
    target = io.StringIO()
    dump(target, node, namespace_map, write_xmlns, default_namespace)
    return target.getvalue()


def dump(target: TextIO, node: XmlNode, namespace_map: Optional[Dict[str, str]] = None, write_xmlns: bool = True,
         default_namespace: Optional[str] = ...):
    if default_namespace is ...:
        default_namespace = node.name.namespace
    if namespace_map is None:
        namespace_map = _build_namespace_map(node, default_namespace)
    else:
        assert len(namespace_map) == len(set(namespace_map.values()))
    dumper = _Dumper(target, namespace_map)
    dumper.dump(node, write_xmlns)


class _Dumper:
    def __init__(self, target: TextIO, namespace_map: Dict[str, str] = None):
        self._target = target
        self._namespace_map = namespace_map

    def dump(self, node: XmlNode, write_xmlns: bool):
        self._target.write("<")
        self._write_name(node.name)
        if write_xmlns:
            self._write_namespaces()
        for attribute, value in node.attributes.items():
            self._write_attribute(attribute, value, node.name.namespace)
        if node.children:
            self._target.write(">")
            for child in node.children:
                if isinstance(child, XmlNode):
                    self.dump(child, False)
                else:
                    self._target.write(_escape(child))
            self._target.write("</")
            self._write_name(node.name)
            self._target.write(">")
        else:
            self._target.write("/>")

    def _write_namespaces(self):
        for namespace in self._namespace_map.keys():
            self._write_attribute(Name(..., namespace), namespace, None)

    def _write_attribute(self, name: Name, value: str, parent_namespace: Optional[str]):
        self._target.write(" ")
        self._write_name(name if name.namespace != parent_namespace else Name(name.name))
        self._target.write('="')
        self._target.write(_escape(value))
        self._target.write('"')

    def _write_name(self, name: Name):
        if name.name is ...:
            name_str = self._namespace_map.get(name.namespace)
            if name_str is None:
                name_str = "xmlns"
                namespace_prefix = None
            else:
                namespace_prefix = "xmlns"
        else:
            name_str = name.name
            namespace_prefix = self._namespace_map.get(name.namespace)
        if namespace_prefix is not None:
            self._target.write(namespace_prefix)
            self._target.write(":")
        self._target.write(name_str)


def _build_namespace_map(node: XmlNode, default_namespace: Optional[str]) -> Dict[str, str]:
    if default_namespace is None:
        return dict(zip(discover_namespaces(node), _namespace_prefix_sequence()))
    else:
        # Deliberately exclude the default namespace from discovered namespaces
        result = dict(zip(discover_namespaces(node, {default_namespace}), _namespace_prefix_sequence()))
        result[default_namespace] = None
        return result


def discover_namespaces(node: XmlNode, discovered: Optional[Set[str]] = None) -> Generator[str, None, None]:
    if discovered is None:
        discovered = set()
    if node.name.namespace is not None and node.name.namespace not in discovered:
        discovered.add(node.name.namespace)
        yield node.name.namespace
    for _, namespace in node.attributes.keys():
        if namespace is not None and namespace not in discovered:
            discovered.add(namespace)
            yield namespace
    for child in node.children:
        if isinstance(child, XmlNode):
            yield from discover_namespaces(child, discovered)


def _namespace_prefix_sequence() -> Generator[str, None, None]:
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    letter_count = 1
    while True:
        for letters in itertools.product(*(alphabet for _ in range(letter_count))):
            yield "".join(letters)
        letter_count += 1


def load(source: TextIO) -> XmlNode:
    dom = _parse(source)
    node = dom.firstChild
    while node.nodeType != xml.dom.Node.ELEMENT_NODE:
        node = node.nextSibling
        assert node is not None, "Root not not found!"
    return from_dom(node)


def loads(source: str) -> XmlNode:
    dom = _parseString(source)
    node = dom.firstChild
    while node.nodeType != xml.dom.Node.ELEMENT_NODE:
        node = node.nextSibling
        assert node is not None, "Root not not found!"
    return from_dom(node)
