from xsbe import transform
import requests
from os import path

def main():
    reader = FeedReader()
    feed_content = reader.read_feed("https://podcasts.files.bbci.co.uk/p05299nl.rss")
    print(feed_content['title'])
    print(feed_content['publish_date'])

    for item in feed_content['items']:
        print(item['publish_date'], item['guid']['#value'], item['enclosure']['url'], item['title'] )


class FeedReader:
    def __init__(self, schema_file: str = f"{path.dirname(__file__)}/rss_schema.xml"):
        with open(schema_file, "r") as file:
            self._parser = transform.create_transformer(file, ignore_unexpected=True)

    def read_feed(self, url: str) -> dict:
        response = requests.get(url)
        response.raise_for_status()
        response_xml = response.content
        return self._parser.loads(response_xml)


if __name__ == '__main__':
    main()
