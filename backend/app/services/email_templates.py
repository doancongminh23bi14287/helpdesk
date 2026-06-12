import os
from string import Template

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), '..', 'email_templates')


def render_template(name: str, **kwargs) -> str:
    """Render an email template file with string.Template safe substitution."""
    path = os.path.join(_TEMPLATES_DIR, name)
    with open(path, encoding='utf-8') as f:
        return Template(f.read()).safe_substitute(**kwargs)
