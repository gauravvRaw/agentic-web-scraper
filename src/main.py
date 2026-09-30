from pydoll.sync import Edge, ExtractionModel, Field

class Quote(ExtractionModel):
    text: str = Field(selector='.text')
    author: str = Field(selector='.author')
    tags: list[str] = Field(selector='.tag')

def main():
    with Edge() as browser:
        tab = browser.start()
        tab.go_to('https://quotes.toscrape.com')

        quotes = tab.extract_all(Quote, scope='.quote', timeout=5)
        for quote in quotes:
            print(f'{quote.author}: {quote.text}')


main()