import pytest

from core.schema import (
    FolderNode,
    SchemaValidationError,
    dump_schema,
    iter_folders,
    iter_leaf_folders,
    load_schema,
    parse_schema,
    save_schema,
    validate_schema,
)

EXAMPLE = """<documentos prompt="Documentos importantes">
  <contas prompt="Contas de água, luz, internet" />
  <comprovantes prompt="Comprovantes bancários" />
</documentos>"""


def errors(roots):
    return [issue for issue in validate_schema(roots) if issue.severity == "error"]


def warnings(roots):
    return [issue for issue in validate_schema(roots) if issue.severity == "warning"]


def test_parse_single_root():
    roots = parse_schema(EXAMPLE)
    assert len(roots) == 1
    assert roots[0].name == "documentos"
    assert roots[0].prompt == "Documentos importantes"
    assert [child.name for child in roots[0].children] == ["contas", "comprovantes"]


def test_invalid_xml_is_a_schema_error():
    with pytest.raises(SchemaValidationError) as error:
        parse_schema("<targets>")
    assert error.value.issues[0].code == "invalid_xml"


def test_parse_targets_root():
    roots = parse_schema(f"<targets>{EXAMPLE}</targets>")
    assert len(roots) == 1
    assert roots[0].name == "documentos"


def test_parse_preserves_name_attribute():
    roots = parse_schema('<targets><pasta name="2024" prompt="ano" /></targets>')
    assert roots[0].name == "2024"


def test_iter_folders_paths():
    folders = dict(iter_folders(parse_schema(EXAMPLE)))
    assert folders["documentos/contas"] == "Contas de água, luz, internet"
    assert "documentos" in folders


def test_iter_leaf_folders_excludes_parents():
    folders = dict(iter_leaf_folders(parse_schema(EXAMPLE)))
    assert "documentos" not in folders
    assert "documentos/contas" in folders
    assert "documentos/comprovantes" in folders


def test_round_trip(tmp_path):
    roots = parse_schema(EXAMPLE)
    target = tmp_path / "schema.xml"
    save_schema(target, roots)
    assert iter_folders(load_schema(target)) == iter_folders(roots)
    assert load_schema(target)[0].prompt == "Documentos importantes"


def test_dump_always_uses_targets_root():
    text = dump_schema([FolderNode("documentos", "docs")])
    assert text.startswith("<targets>")
    assert parse_schema(text)[0].name == "documentos"


def test_dump_preserves_name_when_tag_is_invalid():
    text = dump_schema([FolderNode("2024", "ano")])
    assert 'name="2024"' in text
    assert parse_schema(text)[0].name == "2024"


def test_valid_example_has_no_errors():
    roots = parse_schema(
        '<targets><a prompt="a"><b prompt="b" /></a><c prompt="c" /></targets>'
    )
    assert errors(roots) == []


def test_empty_prompt_is_error():
    issues = errors([FolderNode("a", "")])
    assert [issue.code for issue in issues] == ["empty_prompt"]


def test_prompt_is_required_even_with_children():
    issues = errors([FolderNode("a", "", [FolderNode("b", "b")])])
    assert {issue.code for issue in issues} == {"empty_prompt"}


def test_reserved_names_are_errors():
    roots = [
        FolderNode("__manter__", "y"),
        FolderNode("_nao_classificados", "z"),
    ]
    assert {issue.code for issue in errors(roots)} == {"reserved_name"}


@pytest.mark.parametrize("name", ["", "..", "a/b", "a\\b", "a:b", "a*b"])
def test_invalid_names_are_errors(name):
    assert errors([FolderNode(name, "x")])[0].code in {"empty_name", "invalid_name"}


def test_duplicate_siblings_are_errors():
    roots = [FolderNode("a", "x"), FolderNode("a", "y")]
    assert [issue.code for issue in errors(roots)] == ["duplicate_siblings"]


def test_too_many_root_folders_is_error():
    roots = [FolderNode(f"pasta{i}", "x") for i in range(21)]
    codes = {issue.code for issue in errors(roots)}
    assert "too_many_options" in codes


def test_too_many_children_is_error():
    children = [FolderNode(f"filha{i}", "x") for i in range(20)]
    roots = [FolderNode("raiz", "x", children)]
    codes = {issue.code for issue in errors(roots)}
    assert "too_many_options" in codes


def test_more_than_20_folders_warns_router():
    roots = [FolderNode(f"pasta{i}", "x") for i in range(21)]
    assert "router_enabled" in {issue.code for issue in warnings(roots)}


def test_long_prompt_warns_about_budget():
    roots = [FolderNode("a", "palavra " * 40)]
    assert "option_budget" in {issue.code for issue in warnings(roots)}
