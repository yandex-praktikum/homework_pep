# Асинхронный парсер PEP

Python 3.14. Задание — в [TASK.md](TASK.md).

```text
python -m pip install -r requirements.txt
python -m scrapy startproject pep_parse .
python -m scrapy genspider pep peps.python.org
python -m scrapy crawl pep
python -m pytest -q
```

Запуск из корня проекта. Два CSV сохраняются в `results/`.
