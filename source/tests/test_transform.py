import pytest
import datetime
from xsbe import simple_node
from xsbe import transform



def test_flatten():
    schema = """
    <xsbe:schema-by-example xmlns:xsbe="http://xsbe.couling.uk">
      <xsbe:root>
        <person id="20" xsbe:type="flatten">
          <name>Philip</name>
        </person>
      </xsbe:root>
    </xsbe:schema-by-example>
    """

    document = """
    <person id="21">
        <name>Alan</name>
    </person>
    """

    parser = transform.create_transformer(
        simple_node.loads(schema),
        ignore_unexpected=True
    )
    doc_node = simple_node.loads(document)
    data = parser.transform_from_xml(doc_node)

    assert data == {
        'id': 21,
        'name': 'Alan'
    }


def test_repeating():
    schema = """
    <xsbe:schema-by-example xmlns:xsbe="http://xsbe.couling.uk">
      <xsbe:root>
        <people>
          <person xsbe:type="repeating" xsbe:name="people">Philip</person>
        </people>
      </xsbe:root>
    </xsbe:schema-by-example>
    """

    document = """
    <people>
        <person>Alan</person>
        <person>Also Alan</person>
    </people>
    """

    parser = transform.create_transformer(
        simple_node.loads(schema),
        ignore_unexpected=True
    )
    doc_node = simple_node.loads(document)
    data = parser.transform_from_xml(doc_node)

    assert data =={'people': ['Alan', 'Also Alan']}


def test_repeating_flatten():
    schema = """
    <xsbe:schema-by-example xmlns:xsbe="http://xsbe.couling.uk">
      <xsbe:root>
        <people>
          <person id="20" xsbe:type="repeating" xsbe:name="people">
            <name>Philip</name>
          </person>
        </people>
      </xsbe:root>
    </xsbe:schema-by-example>
    """

    document = """
    <people>
        <person id="21">
            <name>Alan</name>
        </person>
        <person id="22">
            <name>Also Alan</name>
        </person>
    </people>
    """

    parser = transform.create_transformer(
        simple_node.loads(schema),
        ignore_unexpected=True
    )
    doc_node = simple_node.loads(document)
    data = parser.transform_from_xml(doc_node)

    assert data == {
            'people': [
                {
                    'name': 'Alan',
                    'id': 21
                },
                {
                    'name': 'Also Alan',
                    'id': 22
                }
            ]
        }


def test_friendly_name():
    schema = """
    <xsbe:schema-by-example xmlns:xsbe="http://xsbe.couling.uk">
      <xsbe:root>
        <people>
          <person name="Philip" xsbe:value-from="name"/>
        </people>
      </xsbe:root>
    </xsbe:schema-by-example>
    """

    document = """
    <people>
        <person name="Alan"/>
    </people>
    """

    parser = transform.create_transformer(
        simple_node.loads(schema),
        ignore_unexpected=True
    )
    doc_node = simple_node.loads(document)
    data = parser.transform_from_xml(doc_node)

    assert data == {'person': 'Alan'}


def test_friendly_name_duplicates_error():
    schema = """
    <xsbe:schema-by-example xmlns:xsbe="http://xsbe.couling.uk">
      <xsbe:root>
        <people>
          <person name="Philip" xsbe:value-from="name"/>
        </people>
      </xsbe:root>
    </xsbe:schema-by-example>
    """

    document = """
    <people>
        <person name="Alan"/>
        <person name="Also Alan"/>
    </people>
    """

    parser = transform.create_transformer(
        simple_node.loads(schema),
        ignore_unexpected=True
    )
    doc_node = simple_node.loads(document)

    with pytest.raises(transform.DuplicateElement):
        parser.transform_from_xml(doc_node)


def test_int():
    schema = """
    <xsbe:schema-by-example xmlns:xsbe="http://xsbe.couling.uk">
      <xsbe:root>
        <person xsbe:type="flatten">
          <value>27</value>
        </person>
      </xsbe:root>
    </xsbe:schema-by-example>
    """

    document = """
    <person>
      <value>28</value>
    </person>
    """

    parser = transform.create_transformer(
        simple_node.loads(schema),
        ignore_unexpected=True
    )
    doc_node = simple_node.loads(document)
    data = parser.transform_from_xml(doc_node)

    assert data == {
        'value': 28,
    }


def test_int_catch_error():
    schema = """
    <xsbe:schema-by-example xmlns:xsbe="http://xsbe.couling.uk">
      <xsbe:root>
        <person xsbe:type="flatten">
          <value>27</value>
        </person>
      </xsbe:root>
    </xsbe:schema-by-example>
    """

    document = """
    <person>
      <value>lorem ipsum dolor sit amet</value>
    </person>
    """

    parser = transform.create_transformer(
        simple_node.loads(schema),
        ignore_unexpected=True
    )
    doc_node = simple_node.loads(document)

    with pytest.raises(ValueError):
        parser.transform_from_xml(doc_node)


def test_float():
    schema = """
    <xsbe:schema-by-example xmlns:xsbe="http://xsbe.couling.uk">
      <xsbe:root>
        <person xsbe:type="flatten">
          <value>3.14159</value>
        </person>
      </xsbe:root>
    </xsbe:schema-by-example>
    """

    document = """
    <person>
      <value>1.41421356237</value>
    </person>
    """

    parser = transform.create_transformer(
        simple_node.loads(schema),
        ignore_unexpected=True
    )
    doc_node = simple_node.loads(document)
    data = parser.transform_from_xml(doc_node)

    assert data == {'value': 1.41421356237}


def test_string():
    schema = """
    <xsbe:schema-by-example xmlns:xsbe="http://xsbe.couling.uk">
      <xsbe:root>
        <person xsbe:type="flatten">
          <value>lorem ipsum dolor sit amet</value>
        </person>
      </xsbe:root>
    </xsbe:schema-by-example>
    """

    document = """
    <person>
      <value>+44012345678910</value>
    </person>
    """

    parser = transform.create_transformer(
        simple_node.loads(schema),
        ignore_unexpected=True
    )
    doc_node = simple_node.loads(document)
    data = parser.transform_from_xml(doc_node)

    assert data == {'value': '+44012345678910'}


def test_date():
    schema = """
    <xsbe:schema-by-example xmlns:xsbe="http://xsbe.couling.uk">
      <xsbe:root>
        <person xsbe:type="flatten">
          <value>2020-12-30</value>
        </person>
      </xsbe:root>
    </xsbe:schema-by-example>
    """

    document = """
    <person>
      <value>2020-12-31</value>
    </person>
    """

    parser = transform.create_transformer(
        simple_node.loads(schema),
        ignore_unexpected=True
    )
    doc_node = simple_node.loads(document)
    data = parser.transform_from_xml(doc_node)

    assert data == {'value': datetime.datetime(2020, 12, 31)}
