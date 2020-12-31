# XSBE - XML Schema By Example

XSBE is a novel library intended for *rapid development* of XML related python code.  

It takes the approach of using lightly annotated example XML documents to act as a schema.  Using these schemas it can 
then transform an XML document into a more friendly data structures built of dictionaries and lists such as you might 
expect through parsing json or yaml.

It's composed of two main libraries:
 - `xsbe.simple_node` Offers a reduced object model for representing XML document *content*.  See [simple_node](simple_node.md)
 - `xsbe.transform` Offers schema definition and transformer components. See [transform](transform.md)
 
