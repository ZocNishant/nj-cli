# Contributing to nj

## Adding a scraper

1. Create `nj/scrapers/yourplatform.py`
2. Implement `BaseScraper`:

```python
class YourScraper(BaseScraper):
    def name(self) -> str:
        return "yourplatform"
    def scrape(self, roles, location) -> list[Job]:
        # never raises — catch all exceptions internally
        ...
```

3. Add visa classification using `VisaFilter`
4. Add tests in `tests/integration/test_scraper_yourplatform.py`
   using respx to mock HTTP calls
5. Register in `cmd_search.py` and `cmd_run.py`

## Adding an LLM provider

1. Create `nj/providers/yourprovider.py`
2. Implement `BaseLLMProvider`:

```python
class YourProvider(BaseLLMProvider):
    def name(self) -> str: return "yourprovider"
    def supports_json_mode(self) -> bool: return True
    async def complete(self, request) -> LLMResponse: ...
```

3. Register in `nj/providers/registry.py`
4. Add tests mocking the provider client

## PR requirements

- All existing tests must pass: `poetry run pytest`
- No personal data in any committed file
- Code formatted: `poetry run black nj/`
- Linted: `poetry run ruff check nj/`
- New features need tests

## Never commit

`.env`, `config.yaml`, `cv/cv_base.json`, `cv/profile.json`,
`cookies/`, `output/`, `logs/`
