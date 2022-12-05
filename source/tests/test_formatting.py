from io import StringIO

from xsbe import transform


def test_basic_formatting():
    schema = """
    <person id="20" xsbe:type="flatten" xmlns:xsbe="http://xsbe.couling.uk">
      <name>Philip</name>
    </person>
    """

    data = {
        'id': 21,
        'name': 'Alan'
    }

    expected_result = "<?xml version='1.0' encoding='utf-8'?>\n<person id=\"21\"><name>Alan</name></person>"

    parser = transform.create_transformer(StringIO(schema), ignore_unexpected=True)
    document = parser.dumps(data)

    assert document == expected_result
