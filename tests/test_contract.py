import importlib
import logging
from pathlib import Path

import pytest
import scrapy


def test_project_structure(project_settings):
    assert Path('scrapy.cfg').is_file(), 'scrapy.cfg должен лежать в корне.'
    assert project_settings.get('SPIDER_MODULES')
    assert any(value is not None for value in
               project_settings.getdict('ITEM_PIPELINES').values())
    assert project_settings.getdict('FEEDS'), 'Настройте выгрузку через FEEDS.'


def test_item_fields(project_settings):
    item_class = importlib.import_module('pep_parse.items').PepParseItem
    assert issubclass(item_class, scrapy.Item)
    assert {'number', 'name', 'status'} <= item_class.fields.keys()


def test_spider_contract(spider_class, project_settings, callback_outputs):
    assert issubclass(spider_class, scrapy.Spider)
    assert spider_class.name == 'pep'
    from scrapy.crawler import Crawler
    spider = spider_class.from_crawler(Crawler(spider_class, project_settings))
    requests = callback_outputs(spider.start)
    assert requests and all(isinstance(request, scrapy.Request) for request in requests)
    assert {request.url for request in requests} == {'https://peps.python.org/'}
    assert callable(spider.parse) and callable(spider.parse_pep)


def test_index_links(spider_class, html_response, callback_outputs):
    requests = callback_outputs(spider_class().parse, html_response('numerical.html'))
    assert all(isinstance(request, scrapy.Request) for request in requests)
    assert {request.url for request in requests} == {
        'https://peps.python.org/pep-0020/',
        'https://peps.python.org/pep-0008/',
        'https://peps.python.org/pep-0222/',
    }
    assert all(request.callback.__name__ == 'parse_pep' for request in requests)


@pytest.mark.parametrize(('filename', 'number', 'name', 'status'), [
    ('pep-0020.html', '20', 'PEP 20 – The Zen of Python', 'Active'),
    ('pep-0008.html', '8', 'PEP 8 – Style, whitespace and «quotes»', 'Active'),
    ('pep-0222.html', '222', 'PEP 222 – Example document', 'Final'),
])
def test_document_fields(spider_class, html_response, callback_outputs, filename, number, name, status):
    items = callback_outputs(spider_class().parse_pep, html_response(filename))
    assert len(items) == 1
    assert str(items[0]['number']) == number
    assert items[0]['name'] == name
    assert items[0]['status'] == status


@pytest.mark.parametrize('field', ['name', 'status'])
def test_missing_field_is_logged(spider_class, html_response, callback_outputs, caplog, field):
    response = html_response('pep-0020.html')
    body = response.text.replace(
        '<h1 class="page-title"> PEP 20 – The Zen of Python </h1>', '<h1></h1>'
    ) if field == 'name' else response.text.replace('<abbr> Active </abbr>', '')
    with caplog.at_level(logging.ERROR):
        assert not callback_outputs(spider_class().parse_pep, response.replace(body=body.encode()))
    assert caplog.records, 'Сообщите в логе об отсутствии обязательного поля.'
