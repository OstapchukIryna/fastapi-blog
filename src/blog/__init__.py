"""
The blog application.

Five layers, and an import may only ever point downwards:

    presentation/  api и web — всё, что знает про HTTP и про Jinja
    services/      что приложение умеет делать: запросы, правила, отказы
    schemas/       формы данных на границе
    infrastructure/ база, ORM-модели, файлы на диске
    core/          настройки и криптография; не импортирует ничего нашего

Каждый слой — пакет, а не модуль, чтобы новая сущность добавлялась
файлом рядом, а не строкой в конце общего файла.
"""
