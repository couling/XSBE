import unittest
import datetime
from xsbe import simple_node
from xsbe import transform


class Transform(unittest.TestCase):
    def test_flatten(self):
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

        self.assertDictEqual(
            data,
            {
                'id': 21,
                'name': 'Alan'
            }
        )

    def test_repeating(self):
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

        self.assertDictEqual(
            data,
            {'people': ['Alan', 'Also Alan']}
        )

    def test_repeating_flatten(self):
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

        self.assertDictEqual(
            data,
            {
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
        )

    def test_friendly_name(self):
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

        self.assertDictEqual(
            data,
            {'people': 'Alan'}
        )

    def test_friendly_name_duplicates_error(self):
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

        self.assertRaises(
            transform.DuplicateElement,
            parser.transform_from_xml(doc_node)
        )


class TransformDataTypesInference(unittest.TestCase):
    def test_int(self):
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

        self.assertDictEqual(
            data,
            {
                'value': 28,
            }
        )

    def test_int_catch_error(self):
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

        self.assertRaises(
            ValueError,
            parser.transform_from_xml(doc_node)
        )

    def test_float(self):
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

        self.assertDictEqual(
            data,
            {
                'value': 1.41421356237,
            }
        )

    def test_string(self):
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

        self.assertDictEqual(
            data,
            {
                'value': '+44012345678910'
            }
        )

    def test_date(self):
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

        self.assertDictEqual(
            data,
            {
                'value': datetime.date(2020, 12, 31)
            }
        )


if __name__ == '__main__':
    unittest.main()
