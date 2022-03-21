# VSRALA

## Запуск dev-сервера

Создаем venv. используем ```python3.8``` или ```python3.9```:
```bash
python3.9 -m venv venv
. venv/bin/activate
pip install -r requirements.txt
```

Выполняем миграции, чтобы создать тестовую БД:
```bash
python manage.py migrate
```

Запуск dev-сервера(http://127.0.0.1:8000):
```bash
python manage.py runserver
```

Тесты:
```bash
python manage.py test -v2
```