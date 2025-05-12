# tool_decorator.py

def tool(func=None, **kwargs):
    """
    Заглушка для декоратора @tool, чтобы не мешал запуску.
    """
    def decorator(f):
        return f
    return decorator(func) if func else decorator
