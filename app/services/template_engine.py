from jinja2 import Template as JinjaTemplate, TemplateError


class TemplateEngine:
    @staticmethod
    def render(body: str, context: dict) -> str:
        try:
            return JinjaTemplate(body).render(**(context or {}))
        except TemplateError as e:
            raise ValueError(f"Template render error: {e}") from e

    @staticmethod
    def extract_variables(body: str):
        from jinja2 import Environment, meta

        env = Environment()
        ast = env.parse(body)
        return sorted(meta.find_undeclared_variables(ast))
