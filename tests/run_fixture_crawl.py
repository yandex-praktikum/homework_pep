"""Изолированный процесс обхода сохранённых HTML-страниц."""
import sys
from pathlib import Path
from urllib.parse import urlsplit

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.spiderloader import SpiderLoader
from scrapy.utils.project import get_project_settings

sys.path.insert(0, str(Path.cwd()))
settings = get_project_settings()
settings.set('LOG_LEVEL', 'ERROR', priority='cmdline')
process = CrawlerProcess(settings)
spider = SpiderLoader(settings).load('pep')
url = sys.argv[1]


class FixtureSpider(spider):
    # Проверка настоящего стартового URL проводится отдельно.
    allowed_domains = [urlsplit(url).hostname]

    async def start(self):
        yield scrapy.Request(url, callback=self.parse)


process.crawl(FixtureSpider)
process.start()
