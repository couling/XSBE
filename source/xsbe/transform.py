import abc
import email.utils
import io
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, NamedTuple, Optional, TextIO, Union
from xml.etree import ElementTree

XSBE_SCHEMA_URI = "{http://xsbe.couling.uk}"

_SCHEMA_NODE_NAME = f"{XSBE_SCHEMA_URI}schema-by-example"
_ROOT_NODE_NAME = f"{XSBE_SCHEMA_URI}root"
_PART_NODE_NAME = f"{XSBE_SCHEMA_URI}part"
_REFERENCE_NODE_NAME = f"{XSBE_SCHEMA_URI}reference"
_ATTRIBUTE_RESULT_NAME = f"{XSBE_SCHEMA_URI}name"
_ATTRIBUTE_DEFAULT = f"{XSBE_SCHEMA_URI}default"
_ATTRIBUTE_TYPE = f"{XSBE_SCHEMA_URI}type"
_ATTRIBUTE_VALUE_FROM = f"{XSBE_SCHEMA_URI}value-from"

_TYPE_REPEATING = 'repeating'
_TYPE_MANDATORY = 'mandatory'
_TYPE_OPTIONAL = 'optional'
_TYPE_FLATTEN = 'flatten'

_VALUE_KEY = '#value'


class ParseFailure(Exception):
    pass


class UnexpectedAttribute(ParseFailure):
    def __init__(self, attribute_name: str):
        super().__init__(f"Unexpected attribute '{attribute_name}'")


class MissingAttribute(ParseFailure):
    def __init__(self, element_name: str):
        super().__init__(f"Missing required attribute '{element_name}'")


class UnexpectedElement(ParseFailure):
    def __init__(self, element_name: str):
        super().__init__(f"Unexpected element '{element_name}'")


class DuplicateElement(ParseFailure):
    def __init__(self, element_name: str, result_name: Optional[str]):
        super().__init__(f"Duplicate element '{element_name}' ('{result_name}')")


class MissingElement(ParseFailure):
    def __init__(self, element_name: str):
        super().__init__(f"Missing required element '{element_name}'")


class IncorrectRoot(ParseFailure):
    def __init__(self, expected: str, found: str):
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
        ...

    @abc.abstractmethod
    def transform_to_xml(self, value):
        ...


class TextTransformer(ValueTransformer):
    def transform_from_xml(self, value: str) -> str:
        return value

    def transform_to_xml(self, value: str) -> str:
        return value


class IntTransformer(ValueTransformer):
    def transform_from_xml(self, value: str) -> int:
        return int(value)

    def transform_to_xml(self, value: int) -> str:
        return str(value)


class FloatTransformer(ValueTransformer):
    def transform_from_xml(self, value: str) -> float:
        return float(value)

    def transform_to_xml(self, value: float) -> str:
        return str(value)


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
            raise ValueError(f"Invalid date format {value}")
        return result.replace(tzinfo=timezone.utc)

    def transform_to_xml(self, value: Union[datetime, float]) -> str:
        if isinstance(value, float):
            value = datetime.fromtimestamp(value)
        return value.isoformat() + "Z"


class EmailDateTransformer(ValueTransformer):
    def transform_from_xml(self, value) -> datetime:
        try:
            return email.utils.parsedate_to_datetime(value)
            #return datetime.fromtimestamp(time.mktime(email.utils.parsedate_tz(value)))
        except TypeError:
            raise ValueError(f"Invalid date {value}")

    def transform_to_xml(self, value: Union[datetime, float]) -> str:
        if isinstance(value, datetime):
            value = value.timestamp()
        return email.utils.formatdate(timeval=value, localtime=False)


class BaseNodeTransformer(abc.ABC):
    node_name: str
    result_name: str
    is_optional: bool
    is_repeating: bool
    union_group: Optional[str]
    flatten: bool
    attributes: dict[str, ValueTransformer]

    @abc.abstractmethod
    def transform_from_xml(self, value: ElementTree.Element):
        ...

    @abc.abstractmethod
    def transform_to_xml(self, value) -> ElementTree.Element:
        ...

    def __init__(self, node_name: str, result_name: str, ignore_unexpected: bool):
        self.node_name = node_name
        self.result_name = result_name
        self.is_optional = True
        self.is_repeating = False
        self.union_group = None
        self.attributes = {}
        self._ignore_unexpected = ignore_unexpected
        self.flatten = False
        self.default_value = None

    def _parse_attributes(self, node: ElementTree.Element) -> dict:
        result = {}
        for name, value in node.attrib.items():
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

    def _attributes_to_xml(self, value: dict, exclude_attribute: Optional[ElementTree.Element] = None
                           ) -> dict[str, str]:
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

    def __init__(self, name: str, root_transformer: BaseNodeTransformer):
        self.name = name
        self.root_transformer = root_transformer

    def transform_from_xml(self, value: ElementTree.Element):
        if value.tag != self.name:
            raise IncorrectRoot(found=value.tag, expected=self.name)
        return self.root_transformer.transform_from_xml(value)

    def transform_to_xml(self, value):
        return self.root_transformer.transform_to_xml(value)

    def load(self, file: Union[TextIO, BinaryIO, str, Path]) -> Any:
        document = ElementTree.parse(file)
        return self.transform_from_xml(document.getroot())

    def loads(self, content: Union[str, bytes]) -> Any:
        if isinstance(content, str):
            content_reader = io.StringIO(content)
        elif isinstance(content, bytes):
            content_reader = io.BytesIO(content)
        else:
            raise TypeError(f"Expected content of type str or bytes, go {type(content).__name__}")
        return self.load(content_reader)

    def dump(self, file: BinaryIO, value, **kwargs):
        root_node = self.transform_to_xml(value)
        document = ElementTree.ElementTree(root_node)
        return document.write(
            file,
            encoding=kwargs.pop("encoding", "utf-8"),
            xml_declaration=kwargs.pop("xml_declaration", True),
            **kwargs,
        )

    def dumps(self, value, **kwargs) -> str:
        output = io.BytesIO()
        self.dump(output, value, **kwargs)
        return output.getvalue().decode(kwargs.get("encoding", "utf-8"))


class ElementNodeTransformer(BaseNodeTransformer):

    children: dict[str, BaseNodeTransformer]

    def __init__(self, node_name: str, result_name: str, ignore_unexpected: bool):
        super().__init__(node_name, result_name, ignore_unexpected)
        self.children = {}

    def transform_from_xml(self, node: ElementTree.Element):
        result = self._parse_children(node)
        self._set_defaults(result)
        if self.attributes:
            result.update(self._parse_attributes(node))
        return result

    def transform_to_xml(self, value) -> ElementTree.Element:
        node = ElementTree.Element(self.node_name)
        node.attrib = self._attributes_to_xml(value)
        node.extend(self._children_to_xml(value))
        return node

    def _children_to_xml(self, value: dict) -> list[Union[ElementTree.Element, str]]:
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

    def _parse_children(self, node: ElementTree.Element) -> dict:
        # Initialise any child that is a list to an empty list
        result = {child.result_name: [] for child in self.children.values() if child.is_repeating}

        # Process the children
        for child in node:
            if isinstance(child, str):
                raise ParseFailure(f"Unexpected text node '{child}'")
            try:
                child_transformer = self.children[child.tag]
            except KeyError:
                if self._ignore_unexpected:
                    continue
                raise UnexpectedElement(child.tag)
            if child_transformer.is_repeating:
                result[child_transformer.result_name].append(child_transformer.transform_from_xml(child))
            else:
                if child_transformer.flatten:
                    result.update(child_transformer.transform_from_xml(child))
                else:
                    if child_transformer.result_name in result:
                        raise DuplicateElement(child.tag, child_transformer.result_name)
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

    def __init__(self, node_name: str, result_name: str, ignore_unexpected: bool,
                 text_transformer: ValueTransformer, default_value: Optional[str] = None):
        super().__init__(node_name, result_name, ignore_unexpected)
        self._text_transformer = text_transformer
        if default_value is not None:
            self.default_value = self._text_transformer.transform_from_xml(default_value)
        self.value_from = None

    def transform_from_xml(self, node: ElementTree.Element):
        if self.value_from:
            if len(node) > 0:
                if not self._ignore_unexpected:
                    if isinstance(node.children, str):
                        raise ParseFailure("Unexpected text node in %s", node.name)
                    else:
                        raise UnexpectedElement(node.children[0])
            value = node.attrib.get(self.value_from, None)
        elif len(node):
            raise UnexpectedElement(next(iter(node)))
        else:
            value = node.text
            if value is not None:
                value = value.strip()
                if not value:
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

    def transform_to_xml(self, value) -> ElementTree.Element:
        node = ElementTree.Element(self.node_name)
        node.attrib = self._attributes_to_xml(value)
        text_value = self._text_transformer.transform_to_xml(value)
        if self.value_from is not None:
            node.attrib[self.value_from] = text_value
        else:
            node.text = text_value
        return node

    def _children_to_xml(self, value) -> list[Union[ElementTree.Element, str]]:
        if self.value_from is not None:
            return []
        if self.attributes:
            if not isinstance(value, dict):
                raise TypeError(f"{self.node_name} expects dict, received {str(type(value))}")
            value = value[_VALUE_KEY]
        return [self._text_transformer.transform_to_xml(value)]


def create_transformer(schema_document: Union[str, Path, TextIO, BinaryIO, ElementTree.Element],
                       ignore_unexpected: bool = False) -> DocumentTransformer:
    if isinstance(schema_document, (str, Path)) or hasattr(schema_document, 'read'):
        with ExitStack() as stack:
            if isinstance(str, Path):
                schema_document = stack.enter_context(open(schema_document, 'r'))
            schema_document = ElementTree.parse(schema_document).getroot()

    if schema_document.tag == _SCHEMA_NODE_NAME:
        document_root: Optional[DocumentTransformer] = None

        for child in schema_document:
            if child.tag == _ROOT_NODE_NAME:
                if document_root is not None:
                    raise DuplicateElement(_ROOT_NODE_NAME, None)
                if len(child) != 1:
                    raise ParseFailure(f"{_ROOT_NODE_NAME} must contain exactly one child element")
                document_root = _create_root_transformer(next(iter(child)), ignore_unexpected)

        if document_root is None:
            raise MissingElement(_ROOT_NODE_NAME)

    else:
        # Lite mode schemas do not have enclosing nodes.
        document_root = _create_root_transformer(schema_document, ignore_unexpected)

    return document_root


def _create_root_transformer(root_node: ElementTree.Element, ignore_unexpected: bool) -> DocumentTransformer:
    element_transformer = _create_element_transformer(root_node, ignore_unexpected)
    return DocumentTransformer(root_node.tag, element_transformer)


def _create_element_transformer(element: ElementTree.Element, ignore_unexpected: bool) -> BaseNodeTransformer:
    result_name = element.attrib.get(_ATTRIBUTE_RESULT_NAME, split_qualified_name(element.tag).name)
    exclude_attribute = None
    if element.text and element.text.strip():
        if len(element):
            raise ParseFailure(f"Cannot represent mixed content XML documents")
        text_transform_type = _identify_text_type(element.text.strip())
        default_value = element.attrib.get(_ATTRIBUTE_DEFAULT, None)
        result = TextNodeTransformer(element.tag, result_name, ignore_unexpected, text_transform_type, default_value)
    elif _ATTRIBUTE_VALUE_FROM in element.attrib:
        value_from = split_qualified_name(element.attrib[_ATTRIBUTE_VALUE_FROM]).name
        text_transform_type = _identify_text_type(element.attrib[value_from])
        exclude_attribute = value_from
        default_value = element.attrib.get(_ATTRIBUTE_DEFAULT, None)
        result = TextNodeTransformer(element.tag, result_name, ignore_unexpected, text_transform_type, default_value)
        result.value_from = value_from
    else:
        result = ElementNodeTransformer(element.tag, result_name, ignore_unexpected)
        result.children = {child.tag: _create_element_transformer(child, ignore_unexpected) for child in element}

    element_name = split_qualified_name(element.tag)
    for name, value in element.attrib.items():
        if name == exclude_attribute:
            continue
        if not name.startswith(XSBE_SCHEMA_URI):
            split_name = split_qualified_name(name)
            if split_name.namespace is not None and split_name.namespace != element_name.namespace:
                result_name = name
            else:
                result_name = split_name.name
            result.attributes[name] = _identify_text_type(value, result_name)

    node_type = element.attrib.get(_ATTRIBUTE_TYPE, _TYPE_OPTIONAL)
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


DATE_TRANSFORMERS = [ISODateTransformer, ISOZuluDateTransformer, EmailDateTransformer]


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

    for date_type in DATE_TRANSFORMERS:
        try:
            transformer = date_type(result_name=result_name)
            transformer.transform_from_xml(text)
            return transformer
        except ValueError:
            pass

    return TextTransformer(result_name=result_name)


class QualifiedName(NamedTuple):
    namespace: Optional[str]
    name: str


def split_qualified_name(tag: str) -> QualifiedName[Optional[str], str]:
    if tag[0] == "{":
        position = tag.index("}")
        return QualifiedName(tag[1:position], tag[position+1:])
    return QualifiedName(None, tag)
