import pytest
import datetime
from xsbe import transform
from io import StringIO


def test_flatten():
    schema = """
    <xsbe:schema-by-example xmlns:xsbe="http://xsbe.couling.uk">
      <xsbe:root>
        <people>
            <flattened xsbe:type="flatten">
                <person id="20" xsbe:type="repeating">
                  <name>Philip</name>
                </person>
            </flattened>
        </people>
      </xsbe:root>
    </xsbe:schema-by-example>
    """

    document = """
    <people>
        <flattened>
            <person id="21">
                <name>Alan</name>
            </person>
        </flattened>
    </people>
    """

    parser = transform.create_transformer(StringIO(schema), ignore_unexpected=True)
    data = parser.loads(document)

    assert data == {
        'person': [
            {
                'id': 21,
                'name': 'Alan'
            }
        ]
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

    parser = transform.create_transformer(StringIO(schema), ignore_unexpected=True)
    data = parser.loads(document)

    assert data =={'people': ['Alan', 'Also Alan']}


def test_non_xsbe_root_node():
    schema = """
    <people xmlns:xsbe="http://xsbe.couling.uk">
      <person xsbe:type="repeating" xsbe:name="people">Philip</person>
    </people>
    """

    document = """
    <people>
        <person>Alan</person>
        <person>Also Alan</person>
    </people>
    """

    parser = transform.create_transformer(StringIO(schema), ignore_unexpected=True)
    data = parser.loads(document)

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

    parser = transform.create_transformer(StringIO(schema), ignore_unexpected=True)
    data = parser.loads(document)

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

    parser = transform.create_transformer(StringIO(schema), ignore_unexpected=True)
    data = parser.loads(document)

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

    parser = transform.create_transformer(StringIO(schema), ignore_unexpected=True)

    with pytest.raises(transform.DuplicateElement):
        parser.loads(document)


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

    parser = transform.create_transformer(StringIO(schema), ignore_unexpected=True)
    data = parser.loads(document)

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

    parser = transform.create_transformer(StringIO(schema), ignore_unexpected=True)

    with pytest.raises(ValueError):
        parser.loads(document)


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

    parser = transform.create_transformer(StringIO(schema), ignore_unexpected=True)
    data = parser.loads(document)

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

    parser = transform.create_transformer(StringIO(schema), ignore_unexpected=True)
    data = parser.loads(document)

    assert data == {'value': '+44012345678910'}


def _tz(**kwargs) -> datetime.timezone:
    return datetime.timezone(datetime.timedelta(**kwargs))


@pytest.mark.parametrize(
    ('value', 'result'), [
        ('2020-12-31', datetime.datetime(2020, 12, 31)),
        ('2020-12-31T11:45:23', datetime.datetime(2020, 12, 31, 11, 45, 23)),
        ('2020-12-31 11:45:23', datetime.datetime(2020, 12, 31, 11, 45, 23)),
        ('2020-12-31 11:45:23+01:00', datetime.datetime(2020, 12, 31, 11, 45, 23, tzinfo=_tz(hours=1))),
        ('2020-12-31T11:45:23+01:00', datetime.datetime(2020, 12, 31, 11, 45, 23, tzinfo=_tz(hours=1))),
        ('2020-12-31T11:45:23Z', datetime.datetime(2020, 12, 31, 11, 45, 23, tzinfo=_tz(hours=0))),
        ('Mon, 16 Nov 2009 13:32:02 +0400', datetime.datetime(2009, 11, 16, 13, 32, 2, tzinfo=_tz(hours=4))),
        ('Mon, 16 Nov 2009 13:32:02', datetime.datetime(2009, 11, 16, 13, 32, 2)),
    ])
def test_date(value: str, result: datetime):
    schema = f"""
    <xsbe:schema-by-example xmlns:xsbe="http://xsbe.couling.uk">
      <xsbe:root>
        <person xsbe:type="flatten">
          <value>{value}</value>
        </person>
      </xsbe:root>
    </xsbe:schema-by-example>
    """

    document = f"""
    <person>
      <value>{value}</value>
    </person>
    """

    parser = transform.create_transformer(StringIO(schema), ignore_unexpected=True)
    data = parser.loads(document)
    assert list(data.keys()) == ['value']
    assert data['value'] == result
    assert data['value'].tzinfo == result.tzinfo


