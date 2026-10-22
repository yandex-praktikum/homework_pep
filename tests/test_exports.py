import csv
import re
import shutil
import subprocess
import sys
import threading
from collections import Counter
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / 'fixtures'
STAMP = r'\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}'


@contextmanager
def fixture_server(broken=False, duplicate_number=False, missing_field=None):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            route = self.path.split('?', 1)[0]
            files = {'/': 'index.html', '/numerical/': 'numerical.html',
                     '/pep-0020/': 'pep-0020.html', '/pep-0008/': 'pep-0008.html',
                     '/pep-0222/': 'pep-0222.html',
                     '/pep-0020-alias/': 'pep-0020.html'}
            if route == '/robots.txt':
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'User-agent: *\nAllow: /\n')
                return
            if route not in files or (broken and route == '/pep-0222/'):
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            body = (FIXTURES / files[route]).read_bytes()
            if route == '/pep-0222/':
                if missing_field == 'name':
                    body = body.replace('PEP 222 – Example document'.encode('utf-8'), b'')
                elif missing_field == 'status':
                    body = body.replace(b' Final ', b'')
            if duplicate_number and route == '/numerical/':
                body = body.replace(b'</tbody>', b'<tr><td><a class="pep" href="/pep-0020-alias/">20</a></td></tr></tbody>')
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def project_copy(tmp_path):
    target = tmp_path / 'project'
    target.mkdir()
    assert (ROOT / 'pep_parse').is_dir(), 'Создайте проект pep_parse.'
    shutil.copytree(ROOT / 'pep_parse', target / 'pep_parse',
                    ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(ROOT / 'scrapy.cfg', target / 'scrapy.cfg')
    return target


def crawl(project, url):
    run = subprocess.run(
        [sys.executable, str(Path(__file__).parent / 'run_fixture_crawl.py'), url],
        cwd=project, capture_output=True, text=True, encoding='utf-8',
        errors='replace', timeout=60,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    return run


def read_csv(path):
    with path.open(encoding='utf-8', newline='') as stream:
        reader = csv.reader(stream)
        rows = list(reader)
    return rows[0], rows[1:]


def assert_pair(folder, stamp):
    header, rows = read_csv(folder / f'pep_{stamp}.csv')
    assert header == ['Номер', 'Название', 'Статус']
    assert len(rows) == 3 and len({row[0] for row in rows}) == 3
    assert {tuple(row) for row in rows} == {
        ('20', 'PEP 20 – The Zen of Python', 'Active'),
        ('8', 'PEP 8 – Style, whitespace and «quotes»', 'Active'),
        ('222', 'PEP 222 – Example document', 'Final'),
    }
    header, summary = read_csv(folder / f'status_summary_{stamp}.csv')
    assert header == ['Статус', 'Количество']
    assert summary[-1] == ['Total', str(len(rows))]
    assert len(summary[:-1]) == len({row[0] for row in summary[:-1]})
    assert {status: int(count) for status, count in summary[:-1]} == Counter(row[2] for row in rows)


def test_two_runs_create_independent_pairs(tmp_path):
    project = project_copy(tmp_path)
    with fixture_server() as url:
        crawl(project, url)
        results = project / 'results'
        files = set(results.glob('*.csv'))
        assert len(files) == 2
        first_stamps = {re.fullmatch('pep_(' + STAMP + r')\.csv', p.name).group(1)
                        for p in files if p.name.startswith('pep_')}
        assert len(first_stamps) == 1
        assert_pair(results, first_stamps.pop())
        old_bytes = {p.name: p.read_bytes() for p in files}
        crawl(project, url)
    files = list(results.glob('*.csv'))
    assert len(files) == 4
    stamps = set()
    for path in files:
        match = re.fullmatch(r'(?:pep|status_summary)_(' + STAMP + r')\.csv', path.name)
        assert match, path.name
        stamps.add(match.group(1))
    assert len(stamps) == 2
    for stamp in stamps:
        assert_pair(results, stamp)
    for name, content in old_bytes.items():
        assert (results / name).read_bytes() == content


def test_failed_download_is_not_a_complete_pair(tmp_path):
    project = project_copy(tmp_path)
    with fixture_server(broken=True) as url:
        run = crawl(project, url)
    assert not list((project / 'results').glob('status_summary_*.csv'))
    assert 'ERROR' in run.stderr


def test_different_urls_for_one_number_do_not_invalidate_summary(tmp_path):
    project = project_copy(tmp_path)
    with fixture_server(duplicate_number=True) as url:
        crawl(project, url)
    summaries = list((project / 'results').glob('status_summary_*.csv'))
    assert len(summaries) == 1
    stamp = summaries[0].stem.removeprefix('status_summary_')
    assert_pair(project / 'results', stamp)


@pytest.mark.parametrize('missing_field', ['name', 'status'])
def test_missing_field_is_not_a_complete_pair(tmp_path, missing_field):
    project = project_copy(tmp_path)
    with fixture_server(missing_field=missing_field) as url:
        run = crawl(project, url)
    assert not list((project / 'results').glob('status_summary_*.csv'))
    assert 'ERROR' in run.stderr
