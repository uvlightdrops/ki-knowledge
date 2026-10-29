"""Compatibility and dependency contracts for the responsibility split."""

import ast
import builtins
import dis
import importlib
import inspect
import os
from pathlib import Path
from types import CodeType
from types import SimpleNamespace

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ki_knowledge.django_site.settings")
django.setup()

from django.urls import resolve, reverse
from ki_knowledge.django_site import services, views, views_data_sources


SERVICE_MODULES = (
    "data_display", "chat_service", "prompt_library", "knowledge_browser",
    "domain_registry", "support_chat", "pdf_jobs",
)
VIEW_MODULES = (
    "views_source_workspace", "views_source_browser", "views_source_detail",
    "views_content", "views_semantic", "views_jira", "views_chat", "views_pdf",
)


def module(name):
    return importlib.import_module(f"ki_knowledge.django_site.{name}")


@pytest.mark.parametrize("name", SERVICE_MODULES + VIEW_MODULES)
def test_extracted_functions_remain_available_through_facades(name):
    owner = module(name)
    facade = views_data_sources if name in VIEW_MODULES else services
    for symbol, value in vars(owner).items():
        if inspect.isfunction(value) and value.__module__ == owner.__name__:
            if not symbol.startswith("_"):
                assert getattr(facade, symbol) is value, symbol
                assert symbol in facade.__all__, symbol
                if name in VIEW_MODULES:
                    assert getattr(views, symbol) is value, symbol


@pytest.mark.parametrize("name", SERVICE_MODULES + VIEW_MODULES)
def test_extracted_modules_do_not_depend_on_compatibility_facades(name):
    tree = ast.parse(Path(module(name).__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module not in {
                "services", "views_data_sources",
                "ki_knowledge.django_site.services",
                "ki_knowledge.django_site.views_data_sources",
            }


def global_loads(code):
    for instruction in dis.get_instructions(code):
        if instruction.opname == "LOAD_GLOBAL":
            yield instruction.argval
    for constant in code.co_consts:
        if isinstance(constant, CodeType):
            yield from global_loads(constant)


@pytest.mark.parametrize("name", SERVICE_MODULES + VIEW_MODULES)
def test_all_extracted_function_globals_are_bound(name):
    owner = module(name)
    for value in vars(owner).values():
        if inspect.isfunction(value) and value.__module__ == owner.__name__:
            original = inspect.unwrap(value)
            for symbol in global_loads(original.__code__):
                assert symbol in original.__globals__ or hasattr(builtins, symbol), (
                    name, original.__name__, symbol,
                )


@pytest.mark.parametrize("route,handler", [
    ("data-sources", "data_sources_view"),
    ("sources", "sources"),
    ("source-detail", "source_detail"),
    ("source-graph", "source_graph"),
    ("source-graph-3d", "source_graph_3d"),
    ("sources-action", "sources_action"),
    ("support-chat", "support_chat_view"),
    ("jira-hybrid-search", "jira_hybrid_search_view"),
    ("pdf-import-jobs", "pdf_import_jobs_view"),
    ("pdf-inventory", "pdf_inventory_view"),
    ("jobs", "jobs_view"),
])
def test_url_callbacks_are_the_exported_handlers(route, handler):
    args = ["source-id"] if route in {"source-detail", "source-graph", "source-graph-3d"} else []
    assert resolve(reverse(route, args=args)).func is getattr(views_data_sources, handler)


def test_service_facade_has_no_overridden_implementations():
    tree = ast.parse(Path(services.__file__).read_text())
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    assert len({node.name for node in functions}) == len(functions)
    # Only small signature-preserving adapter forwards remain, not business logic.
    for node in functions:
        assert len(node.body) == 2
        assert isinstance(node.body[0], ast.ImportFrom)
        assert isinstance(node.body[1], ast.Return)


def test_prompt_batch_keeps_templates_backlog_and_import_contract(tmp_path, monkeypatch):
    prompts = module("prompt_library")
    monkeypatch.setattr(prompts, "data_dir", lambda domain=None: tmp_path)
    monkeypatch.setattr(prompts, "display_data_path", str)
    questions = []
    imported = []

    def answer(question, **options):
        questions.append((question, options))
        return {"answer": "Generated answer", "model": "mock-model", "base_url": "mock"}

    def import_file(path, source_name):
        imported.append((path, source_name))
        assert path.is_file()
        return {"imported": 2}

    monkeypatch.setattr(prompts, "ollama_chat_answer", answer)
    monkeypatch.setattr(prompts, "import_markdown_file", import_file)
    backlog = "- [ ] special :: First question\n- [x] Already done\n- [ ] Second question\n"
    templates = "## special\nDomain {{domain}}: {{question}}\n## default\n{{question}}\n"
    services.save_prompt_library_documents(
        domain="alpha", backlog_content=backlog, templates_content=templates,
    )
    context = services.load_prompt_library_context("alpha")
    assert context["open_count"] == 2 and context["done_count"] == 1
    result = services.run_prompt_backlog_batch(
        domain="alpha", backlog_content=backlog, templates_content=templates,
        import_outputs=True,
    )
    assert result["processed"] == 2 and result["imported_records"] == 4
    assert [question for question, _ in questions] == [
        "Domain alpha: First question", "Second question",
    ]
    assert "[ ]" not in result["updated_backlog_content"]
    assert all(
        name == path.relative_to(tmp_path).as_posix()
        for path, name in imported
    )
    assert len(services.prompt_batch_outputs("alpha")) == 2
    assert all("Generated answer" in Path(path).read_text() for path in result["saved_files"])


def test_chat_service_preserves_provider_messages_and_markdown_output(tmp_path, monkeypatch):
    chat = module("chat_service")
    calls = []

    def respond(request):
        calls.append(request)
        return SimpleNamespace(
            message=SimpleNamespace(content="Answer"), model="mock-model",
        )

    monkeypatch.setattr(chat, "chat_client", lambda **options: SimpleNamespace(
        base_url="mock", chat=respond,
    ))
    monkeypatch.setattr(chat, "ollama_chat_dir", lambda domain: tmp_path)
    result = services.ollama_chat_answer(
        " Question ", system_prompt="System",
        history=[{"role": "user", "content": "Earlier"}, {"role": "invalid", "content": "skip"}],
    )
    assert [message.content for message in calls[0].messages] == ["System", "Earlier", "Question"]
    assert result["messages"][-1] == {"role": "assistant", "content": "Answer"}
    path = services.save_ollama_chat_markdown(
        domain="alpha", title="Conversation", question=result["question"],
        answer=result["answer"], model=result["model"], base_url=result["base_url"],
        messages=result["messages"],
    )
    assert path.parent == tmp_path
    assert "domain: alpha" in path.read_text() and "## Transcript" in path.read_text()
