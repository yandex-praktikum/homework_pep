import importlib
import asyncio
import inspect
from pathlib import Path

import pytest
from scrapy.settings import Settings
from scrapy.spiderloader import SpiderLoader

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.fixture
def project_settings():
    try:
        module = importlib.import_module('pep_parse.settings')
    except ModuleNotFoundError:
        pytest.fail('Создайте проект: python -m scrapy startproject pep_parse .')
    settings = Settings()
    settings.setmodule(module)
    return settings


@pytest.fixture
def spider_class(project_settings):
    try:
        return SpiderLoader(project_settings).load('pep')
    except KeyError:
        pytest.fail('Создайте и подключите паука с именем pep.')


@pytest.fixture
def html_response():
    from scrapy.http import HtmlResponse

    def make(name, url='https://peps.python.org/numerical/'):
        return HtmlResponse(url=url, body=(FIXTURES / name).read_bytes(),
                            encoding='utf-8')
    return make


@pytest.fixture
def callback_outputs():
    from scrapy.utils.spider import iterate_spider_output

    def collect(callback, *args):
        async def run():
            result = callback(*args)
            if inspect.isawaitable(result):
                result = await result
            if hasattr(result, '__aiter__'):
                return [value async for value in result]
            return list(iterate_spider_output(result))
        return asyncio.run(run())
    return collect
