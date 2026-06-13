# fastkeel/cli/new.py
from pathlib import Path

import typer
from jinja2 import Environment, PackageLoader

app = typer.Typer()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """fastkeel - FastAPI 后端项目脚手架"""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command()
def new(
    name: str = typer.Argument(help="项目名称"),
    with_user: bool = typer.Option(True, "--with-user/--no-with-user", help="启用用户模块"),
    with_social: bool = typer.Option(False, "--with-social/--no-with-social", help="启用社交模块"),
    with_payment: bool = typer.Option(False, "--with-payment/--no-with-payment", help="启用支付模块"),
    with_jobs: bool = typer.Option(False, "--with-jobs/--no-with-jobs", help="启用定时任务模块"),
    path: str = typer.Option(".", "--path", help="生成路径"),
):
    """生成 FastAPI 项目骨架。"""
    target_dir = Path(path) / name
    target_dir.mkdir(parents=True, exist_ok=True)

    env = Environment(
        loader=PackageLoader("fastkeel", "templates/default"),
    )

    templates = [
        "main.py.j2",
        "config.toml.j2",
        "pyproject.toml.j2",
        "project/__init__.py.j2",
        "project/models/__init__.py.j2",
        "project/routes/__init__.py.j2",
        "project/logic/__init__.py.j2",
        "project/prompts/.gitkeep.j2",
        "tests/__init__.py.j2",
        "tests/conftest.py.j2",
    ]

    context = {
        "project_name": name,
        "with_user": with_user,
        "with_social": with_social,
        "with_payment": with_payment,
        "with_jobs": with_jobs,
    }

    for template_name in templates:
        dest = target_dir / template_name.removesuffix(".j2")
        dest.parent.mkdir(parents=True, exist_ok=True)
        template = env.get_template(template_name)
        content = template.render(**context)
        dest.write_text(content)

    typer.echo(f"✅ {name} 已创建在 {target_dir}")
    typer.echo(f"   cd {name}")
    typer.echo(f"   python3 main.py")
