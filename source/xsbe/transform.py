import abc
import email.utils
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, TextIO, Union

from . import simple_node

XSBE_SCHEMA_URI = "http://xsbe.couling.uk"

_SCHEMA_NODE_NAME = simple_node.Name("schema-by-example", XSBE_SCHEMA_URI)
_ROOT_NODE_NAME = simple_node.Name("root", XSBE_SCHEMA_URI)
_PART_NODE_NAME = simple_node.Name("part", XSBE_SCHEMA_URI)
_REFERENCE_NODE_NAME = simple_node.Name("reference", XSBE_SCHEMA_URI)
_ATTRIBUTE_RESULT_NAME = simple_node.Name("name", XSBE_SCHEMA_URI)
_ATTRIBUTE_DEFAULT = simple_node.Name("default", XSBE_SCHEMA_URI)
_ATTRIBUTE_TYPE = simple_node.Name("type", XSBE_SCHEMA_URI)
_ATTRIBUTE_VALUE_FROM = simple_node.Name('value-from', XSBE_SCHEMA_URI)

_TYPE_REPEATING = 'repeating'
_TYPE_MANDATORY = 'mandatory'
_TYPE_OPTIONAL = 'optional'
_TYPE_FLATTEN = 'flatten'

_VALUE_KEY = '#value'


class ParseFailure(Exception):
    pass


class UnexpectedAttribute(ParseFailure):
    def __init__(self, attribute_name: simple_node.Name):
        super().__init__(f"Unexpected attribute '{attribute_name}'")


class MissingAttribute(ParseFailure):
    def __init__(self, element_name: simple_node.Name):
        super().__init__(f"Missing required attribute '{element_name}'")


class UnexpectedElement(ParseFailure):
    def __init__(self, element_name: simple_node.Name):
        super().__init__(f"Unexpected element '{element_name}'")


class DuplicateElement(ParseFailure):
    def __init__(self, element_name: simple_node.Name, result_name: Optional[str]):
        super().__init__(f"Duplicate element '{element_name}' ('{result_name}')")


class MissingElement(ParseFailure):
    def __init__(self, element_name: simple_node.Name):
        super().__init__(f"Missing required element '{element_name}'")


class IncorrectRoot(ParseFailure):
    def __init__(self, expected: simple_node.Name, found: simple_node.Name):
        super().__init__(f"Expected {expected} at root but found {found}")


class DuplicateCrossReferenceId(ParseFailure):
    def __init__(self, reference_id: str):
        super().__init__(f"Duplicate cross reference id {reference_id}")


class MissingCrossReference(ParseFailure):
    def __init__(self, *reference_id: str):
        super().__init__(f"Missing cross references: {', '.join(reference_id)}")


class ValueTransformer(abc.ABC):
    result_name: str

    def __init__(self, result_name: Optional[str] = None):
        self.result_name = result_name
        self.default_value = None

    @abc.abstractmethod
    def transform_from_xml(self, value):
        pass

    def transform_to_xml(self, value):
        return str(value)


class TextTransformer(ValueTransformer):
    def transform_from_xml(self, value: str) -> str:
        return value


class IntTransformer(ValueTransformer):
    def transform_from_xml(self, value: str) -> int:
        return int(value)


class FloatTransformer(ValueTransformer):
    def transform_from_xml(self, value: str) -> float:
        return float(value)


class BooleanTransformer(ValueTransformer):
    MAP = {
        "y": True,
        "yes": True,
        "true": True,
        "t": True,
        "no": False,
        "n": False,
        "false": False,
        "f": False,
    }

    def transform_from_xml(self, value: str) -> bool:
        return self.MAP[value.lower()]

    def transform_to_xml(self, value):
        return "true" if value else "false"


class ISODateTransformer(ValueTransformer):
    def transform_from_xml(self, value) -> datetime:
        return datetime.fromisoformat(value)

    def transform_to_xml(self, value: Union[datetime, float]) -> str:
        if isinstance(value, float):
            value = datetime.fromtimestamp(value)
        return value.isoformat()


class ISOZuluDateTransformer(ValueTransformer):
    def transform_from_xml(self, value) -> datetime:
        if value[-1] != "Z":
            raise ValueError("Expected Z timezone")
        result = datetime.fromisoformat(value[:-1])
        if result.tzinfo is not None:
            raise ValueError(f"Invalud date format {value}")
        return result.replace(tzinfo=timezone.utc)

    def transform_to_xml(self, value: Union[datetime, float]) -> str:
        if isinstance(value, float):
            value = datetime.fromtimestamp(value)
        return value.isoformat() + "Z"


class EmailDateTransformer(ValueTransformer):
    def transform_from_xml(self, value) -> datetime:
        try:
            return datetime.fromtimestamp(time.mktime(email.utils.parsedate(value)))
        except TypeError:
            raise ValueError(f"Invalid date {value}")

    def transform_to_xml(self, value: Union[datetime, float]) -> str:
        if isinstance(value, datetime):
            value = value.timestamp()
        return email.utils.formatdate(timeval=value, localtime=False)


class BaseNodeTransformer(abc.ABC):
    node_name: simple_node.Name
    result_name: str
    is_optional: bool
    is_repeating: bool
    union_group: Optional[str]
    flatten: bool
    attributes: Dict[simple_node.Name, ValueTransformer]

    @abc.abstractmethod
    def transform_from_xml(self, value: simple_node.XmlNode):
        pass

    def transform_to_xml(self, value) -> simple_node.XmlNode:
        node = simple_node.XmlNode(self.node_name)
        node.attributes = self._attributes_to_xml(value)
        node.children = self._children_to_xml(value)
        return node

    @abc.abstractmethod
    def _children_to_xml(self, value) -> List[Union[simple_node.XmlNode, str]]:
        pass

    def __init__(self, node_name: simple_node.Name, result_name: str, ignore_unexpected: bool):
        self.node_name = node_name
        self.result_name = result_name
        self.is_optional = True
        self.is_repeating = False
        self.union_group = None
        self.attributes = {}
        self._ignore_unexpected = ignore_unexpected
        self.flatten = False
        self.default_value = None

    def _parse_attributes(self, node: simple_node.XmlNode) -> dict:
        result = {}
        for name, value in node.attributes.items():
            try:
                transformer = self.attributes[name]
            except KeyError:
                if self._ignore_unexpected:
                    continue
                raise UnexpectedAttribute(name)
            result[transformer.result_name] = transformer.transform_from_xml(value)
        for transformer in self.attributes.values():
            if transformer.result_name not in result:
                default = transformer.default_value
                if default is not None:
                    result[transformer.result_name] = default
        return result

    def _attributes_to_xml(self, value: dict, exclude_attribute: Optional[simple_node.XmlNode] = None
                           ) -> Dict[simple_node.Name, str]:
        result = {}
        for name, transformer in self.attributes.items():
            if name == exclude_attribute:
                continue
            if transformer.result_name in value:
                result[name] = transformer.transform_to_xml(value[transformer.result_name])
            elif transformer.default_value is not None:
                result[name] = transformer.transform_to_xml(transformer.default_value)
        return result


class DocumentTransformer:
    root_transformer: BaseNodeTransformer

    def __init__(self, name: simple_node.Name, root_transformer: BaseNodeTransformer):
        self.name = name
        self.root_transformer = root_transformer

    def transform_from_xml(self, value: simple_node.XmlNode):
        if value.name != self.name:
            raise IncorrectRoot(found=value.name, expected=self.name)
        return self.root_transformer.transform_from_xml(value)

    def transform_to_xml(self, value):
        return self.root_transformer.transform_to_xml(value)

    def load(self, file: TextIO):
        document = simple_node.load(file)
        return self.transform_from_xml(document)

    def loads(self, content: str):
        document = simple_node.loads(content)
        return self.transform_from_xml(document)

    def dump(self, file: TextIO, value, **kwargs):
        document = self.transform_to_xml(value)
        return simple_node.dump(file, document, **kwargs)

    def dumps(self, value, **kwargs) -> str:
        document = self.transform_to_xml(value)
        return simple_node.dumps(document, **kwargs)


class ElementNodeTransformer(BaseNodeTransformer):

    children: Dict[simple_node.Name, BaseNodeTransformer]

    def __init__(self, node_name: simple_node.Name, result_name: str, ignore_unexpected: bool):
        super().__init__(node_name, result_name, ignore_unexpected)
        self.children = {}

    def transform_from_xml(self, node: simple_node.XmlNode):
        result = self._parse_children(node)
        self._set_defaults(result)
        if self.attributes:
            result.update(self._parse_attributes(node))
        return result

    def _children_to_xml(self, value: Dict) -> List[Union[simple_node.XmlNode, str]]:
        result = []
        for child in self.children.values():
            if child.is_repeating:
                child_value = value.get(child.result_name, [])
            elif child.flatten:
                child_value = value
            elif child.is_optional:
                child_value = value.get(child.result_name, child.default_value)
                if child_value is None:
                    continue
            else:
                child_value = value[child.result_name]

            if child.is_repeating:
                if not isinstance(child_value, list):
                    raise TypeError(f"{child.result_name} must be a list, received {type(child_value)}")
                for v in child_value:
                    result.append(child.transform_to_xml(v))
            else:
                if child_value is not None:
                    result.append(child.transform_to_xml(child_value))

        return result

    def _parse_children(self, node: simple_node.XmlNode) -> dict:
        # Initialise any child that is a list to an empty list
        result = {child.result_name: [] for child in self.children.values() if child.is_repeating}

        # Process the children
        for child in node.children:
            if isinstance(child, str):
                raise ParseFailure(f"Unexpected text node '{child}'")
            try:
                child_transformer = self.children[child.name]
            except KeyError:
                if self._ignore_unexpected:
                    continue
                raise UnexpectedElement(child.name)
            if child_transformer.is_repeating:
                result[child_transformer.result_name].append(child_transformer.transform_from_xml(child))
            else:
                if child_transformer.flatten:
                    result.update(child_transformer.transform_from_xml(child))
                else:
                    if child_transformer.result_name in result:
                        raise DuplicateElement(child.name, child_transformer.result_name)
                    result[child_transformer.result_name] = child_transformer.transform_from_xml(child)

        return result

    def _set_defaults(self, result_dict: dict):
        for name, transformer in self.children.items():
            if transformer.result_name not in result_dict:
                if transformer.is_optional:
                    if transformer.default_value is not None:
                        result_dict[transformer.result_name] = transformer.default_value
                else:
                    raise MissingElement(name)
            elif transformer.is_repeating and not transformer.is_optional and not result_dict[transformer.result_name]:
                raise MissingElement(name)


class TextNodeTransformer(BaseNodeTransformer):

    def __init__(self, node_name: simple_node.Name, result_name: str, ignore_unexpected: bool,
                 text_transformer: ValueTransformer, default_value: Optional[str] = None):
        super().__init__(node_name, result_name, ignore_unexpected)
        self._text_transformer = text_transformer
        if default_value is not None:
            self.default_value = self._text_transformer.transform_from_xml(default_value)
        self.value_from = None

    def transform_from_xml(self, node: simple_node.XmlNode):
        if self.value_from:
            if node.children:
                if not self._ignore_unexpected:
                    if isinstance(node.children, str):
                        raise ParseFailure("Unexpected text node in %s", node.name)
                    else:
                        raise UnexpectedElement(node.children[0])
            value = node.attributes.get(self.value_from, None)
        elif node.children:
            if not isinstance(node.children[0], str):
                unexpected_child = node.children[0]
                raise UnexpectedElement(unexpected_child.name)
            if len(node.children) > 1:
                unexpected_child = node.children[0]
                raise UnexpectedElement(unexpected_child.name)
            value = node.children[0].strip()
        else:
            value = None
        if value is None:
            if self.is_optional:
                value = self.default_value
            else:
                raise ParseFailure("Missing text value")
        else:
            value = self._text_transformer.transform_from_xml(value)

        if self.attributes:
            result = self._parse_attributes(node)
            result[_VALUE_KEY] = value
            return result
        else:
            return value

    def _children_to_xml(self, value) -> List[Union[simple_node.XmlNode, str]]:
        if self.value_from is not None:
            return []
        if self.attributes:
            if not isinstance(value, dict):
                raise TypeError(f"{self.node_name} expects dict, received {str(type(value))}")
            value = value[_VALUE_KEY]
        return [self._text_transformer.transform_to_xml(value)]

    def _attributes_to_xml(self, value: dict) -> Dict[simple_node.Name, str]:
        attributes = super()._attributes_to_xml(value)
        if self.value_from is not None:
            attributes[self.value_from] = self._text_transformer.transform_to_xml(value)
        return attributes


def create_transformer(schema_document: Union[str, Path, simple_node.XmlNode],
                       ignore_unexpected: bool = False) -> DocumentTransformer:
    if isinstance(schema_document, (str, Path)):
        with open(schema_document, 'r') as file:
            schema_document = simple_node.load(file)

    if schema_document.name == _SCHEMA_NODE_NAME:
        document_root: Optional[DocumentTransformer] = None

        for child in schema_document.children:

            if not isinstance(child, simple_node.XmlNode):
                raise ParseFailure(f"Unexpected text node in {_SCHEMA_NODE_NAME}")
            if child.name == _ROOT_NODE_NAME:
                if document_root is not None:
                    raise DuplicateElement(_ROOT_NODE_NAME, None)
                if len(child.children) != 1 or not isinstance(child.children[0], simple_node.XmlNode):
                    raise ParseFailure(f"{_ROOT_NODE_NAME} must contain exactly one child element and not text")
                document_root = _create_root_transformer(child.children[0], ignore_unexpected)

        if document_root is None:
            raise MissingElement(_ROOT_NODE_NAME)

    else:
        # Lite mode schemas do not have enclosing nodes.
        document_root = _create_root_transformer(schema_document, ignore_unexpected)

    return document_root


def load_transformer(schema_file: TextIO) -> DocumentTransformer:
    document = simple_node.load(schema_file)
    return create_transformer(document)


def loads_transformer(schema: str) -> DocumentTransformer:
    document = simple_node.loads(schema)
    return create_transformer(document)


def _create_root_transformer(root_node: simple_node.XmlNode, ignore_unexpected: bool) -> DocumentTransformer:
    element_transformer = _create_element_transformer(root_node, ignore_unexpected)
    return DocumentTransformer(root_node.name, element_transformer)


def _create_element_transformer(element: simple_node.XmlNode, ignore_unexpected: bool) -> BaseNodeTransformer:
    result_name = element.attributes.get(_ATTRIBUTE_RESULT_NAME, element.name.name)
    exclude_attribute = None
    if element.children and isinstance(element.children[0], str):
        if len(element.children) != 1:
            raise ParseFailure(f"Cannot represent mixed content XML documents")
        text_transform_type = _identify_text_type(element.children[0])
        default_value = element.attributes.get(_ATTRIBUTE_DEFAULT, None)
        result = TextNodeTransformer(element.name, result_name, ignore_unexpected, text_transform_type, default_value)
    elif _ATTRIBUTE_VALUE_FROM in element.attributes and element.attributes[_ATTRIBUTE_VALUE_FROM]:
        value_from = simple_node.Name(element.attributes[_ATTRIBUTE_VALUE_FROM], None)
        text_transform_type = _identify_text_type(element.attributes[value_from])
        exclude_attribute = value_from
        default_value = element.attributes.get(_ATTRIBUTE_DEFAULT, None)
        result = TextNodeTransformer(element.name, result_name, ignore_unexpected, text_transform_type, default_value)
        result.value_from = value_from
    else:
        result = ElementNodeTransformer(element.name, result_name, ignore_unexpected)
        result.children = {child.name: _create_element_transformer(child, ignore_unexpected)
                           for child in element.children}

    for name, value in element.attributes.items():
        if name == exclude_attribute:
            continue
        if name.namespace != XSBE_SCHEMA_URI:
            if name.namespace is not None and name.namespace != element.name.namespace:
                result_name = f"{name.name}:{name.namespace}"
            else:
                result_name = name.name
            result.attributes[name] = _identify_text_type(value, result_name)

    node_type = element.attributes.get(_ATTRIBUTE_TYPE, _TYPE_OPTIONAL)
    if node_type != _TYPE_OPTIONAL:
        if node_type == _TYPE_MANDATORY:
            result.is_optional = False
        elif node_type == _TYPE_REPEATING:
            result.is_repeating = True
        elif node_type == _TYPE_FLATTEN:
            result.flatten = True
        else:
            raise ParseFailure(f"Unknown node type {node_type}")

    return result


def _identify_text_type(text: str, result_name: Optional[str] = None) -> ValueTransformer:
    if text in BooleanTransformer.MAP:
        return BooleanTransformer(result_name=result_name)
    try:
        float(text)
    except ValueError:
        pass
    else:
        if "." in text:
            return FloatTransformer(result_name=result_name)
        return IntTransformer(result_name=result_name)

    for date_type in (ISODateTransformer, ISOZuluDateTransformer, EmailDateTransformer):
        try:
            transformer = date_type(result_name=result_name)
            transformer.transform_from_xml(text)
            return transformer
        except ValueError:
            pass

    return TextTransformer(result_name=result_name)
