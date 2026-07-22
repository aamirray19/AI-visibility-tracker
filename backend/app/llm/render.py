from pathlib import Path

from jinja2 import Environment, FileSystemLoader

_env = Environment(loader=FileSystemLoader(Path(__file__).parent / "prompts"), autoescape=False)


def render_prompt(template_name: str, **kwargs) -> str:
    return _env.get_template(template_name).render(**kwargs)
