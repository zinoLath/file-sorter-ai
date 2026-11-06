from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from core import config
from core.budget import estimate_tokens

ROOT_TAG = "targets"
INVALID_CHARS = '/\\:*?"<>|'
VALID_TAG = re.compile(r"^[A-Za-z_][\w.-]*$")


@dataclass
class FolderNode:
    name: str
    prompt: str = ""
    children: list["FolderNode"] = field(default_factory=list)

    def iter_paths(self, parent: str = "") -> list[tuple[str, str]]:
        path = f"{parent}/{self.name}" if parent else self.name
        result = [(path, self.prompt)]
        for child in self.children:
            result.extend(child.iter_paths(path))
        return result

    def iter_leaves(self, parent: str = "") -> list[tuple[str, str]]:
        path = f"{parent}/{self.name}" if parent else self.name
        if not self.children:
            return [(path, self.prompt)]
        result: list[tuple[str, str]] = []
        for child in self.children:
            result.extend(child.iter_leaves(path))
        return result


@dataclass(frozen=True)
class SchemaIssue:
    severity: str
    code: str
    path: str
    message: str


class SchemaValidationError(ValueError):
    def __init__(self, issues: list[SchemaIssue]) -> None:
        self.issues = issues
        details = "; ".join(f"{issue.path}: {issue.message}" for issue in issues)
        super().__init__(f"schema inválido: {details}")


def sanitize_name(name: str) -> str:
    cleaned = name.strip().strip(".")
    cleaned = "".join("-" if char in INVALID_CHARS else char for char in cleaned)
    return cleaned or "pasta"


def _parse_element(element: ET.Element) -> FolderNode:
    return FolderNode(
        name=element.get("name", element.tag),
        prompt=element.get("prompt", ""),
        children=[_parse_element(child) for child in element],
    )


def parse_schema(text: str) -> list[FolderNode]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        raise SchemaValidationError(
            [SchemaIssue("error", "invalid_xml", "/", str(error))]
        ) from error
    if root.tag == ROOT_TAG:
        return [_parse_element(child) for child in root]
    return [_parse_element(root)]


def load_schema(path: str | Path) -> list[FolderNode]:
    return parse_schema(Path(path).read_text(encoding="utf-8"))


def _is_valid_tag(name: str) -> bool:
    return bool(VALID_TAG.match(name))


def _folder_to_element(folder: FolderNode) -> ET.Element:
    if _is_valid_tag(folder.name):
        element = ET.Element(folder.name, {"prompt": folder.prompt})
    else:
        element = ET.Element("pasta", {"name": folder.name, "prompt": folder.prompt})
    for child in folder.children:
        element.append(_folder_to_element(child))
    return element


def dump_schema(roots: list[FolderNode]) -> str:
    root_element = ET.Element(ROOT_TAG)
    for folder in roots:
        root_element.append(_folder_to_element(folder))
    ET.indent(root_element)
    return ET.tostring(root_element, encoding="unicode", short_empty_elements=True) + "\n"


def save_schema(path: str | Path, roots: list[FolderNode]) -> None:
    Path(path).write_text(dump_schema(roots), encoding="utf-8")


def iter_folders(roots: list[FolderNode]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for root in roots:
        pairs.extend(root.iter_paths())
    return pairs


def iter_leaf_folders(roots: list[FolderNode]) -> list[tuple[str, str]]:
    """Pastas-folha: únicas opções válidas no modo flat.

    Pasta com filhos é agrupamento (o router a alcança via `__manter__`), não
    destino; oferecê-la junto dos filhos fazia o pai engolir as subpastas.
    """
    pairs: list[tuple[str, str]] = []
    for root in roots:
        pairs.extend(root.iter_leaves())
    return pairs


def _node_path(parent: str, name: str) -> str:
    if not name:
        name = "<sem nome>"
    return f"{parent}/{name}" if parent else name


def _error(code: str, path: str, message: str) -> SchemaIssue:
    return SchemaIssue("error", code, path, message)


def _warning(code: str, path: str, message: str) -> SchemaIssue:
    return SchemaIssue("warning", code, path, message)


def _validate_name(node: FolderNode, path: str) -> list[SchemaIssue]:
    name = node.name
    if not name or not name.strip():
        return [_error("empty_name", path, "nome de pasta vazio")]
    if (
        name.strip() != name
        or name in {".", ".."}
        or any(char in INVALID_CHARS for char in name)
    ):
        return [_error("invalid_name", path, f"nome de pasta inválido: {name!r}")]
    if name in config.RESERVED_NAMES:
        return [_error("reserved_name", path, f"nome de pasta reservado: {name!r}")]
    return []


def _validate_siblings(nodes: list[FolderNode], path: str) -> list[SchemaIssue]:
    issues: list[SchemaIssue] = []
    seen: set[str] = set()
    duplicates: set[str] = set()
    for node in nodes:
        if node.name in seen:
            duplicates.add(node.name)
        seen.add(node.name)
    for name in sorted(duplicates):
        issues.append(_error("duplicate_siblings", path, f"irmãos duplicados: {name!r}"))
    return issues


def _validate_node(node: FolderNode, parent_path: str) -> list[SchemaIssue]:
    path = _node_path(parent_path, node.name)
    issues = _validate_name(node, path)
    if not node.prompt.strip():
        issues.append(_error("empty_prompt", path, "toda pasta precisa de prompt"))
    if len(node.children) > config.MAX_NON_ROOT_CHILDREN:
        issues.append(
            _error(
                "too_many_options",
                path,
                f"{len(node.children)} filhos; o limite é "
                f"{config.MAX_NON_ROOT_CHILDREN}",
            )
        )
    issues.extend(_validate_siblings(node.children, path))
    for child in node.children:
        issues.extend(_validate_node(child, path))
    return issues


def _iter_nodes(nodes: list[FolderNode], parent_path: str) -> Iterator[tuple[str, FolderNode]]:
    for node in nodes:
        path = _node_path(parent_path, node.name)
        yield path, node
        yield from _iter_nodes(node.children, path)


def _combined_warning(nodes: list[FolderNode], path: str, *, keep: bool) -> list[SchemaIssue]:
    combined = estimate_tokens(config.INSTRUCTIONS)
    combined += sum(estimate_tokens(node.prompt) for node in nodes)
    if keep:
        combined += estimate_tokens(config.KEEP_DESCRIPTION)
    if combined <= config.MAX_COMBINED_TOKENS:
        return []
    return [
        _warning(
            "prompt_budget",
            path or "/",
            f"pergunta + opções somam {combined} tokens "
            f"(teto {config.MAX_COMBINED_TOKENS})",
        )
    ]


def validate_schema(roots: list[FolderNode]) -> list[SchemaIssue]:
    issues: list[SchemaIssue] = []
    if len(roots) > config.MAX_ROOT_CHILDREN:
        issues.append(
            _error(
                "too_many_options",
                "/",
                f"{len(roots)} pastas na raiz; o limite é {config.MAX_ROOT_CHILDREN}",
            )
        )
    issues.extend(_validate_siblings(roots, "/"))
    for node in roots:
        issues.extend(_validate_node(node, ""))

    all_nodes = list(_iter_nodes(roots, ""))
    for path, node in all_nodes:
        tokens = estimate_tokens(node.prompt)
        if tokens > config.MAX_OPTION_TOKENS:
            issues.append(
                _warning(
                    "option_budget",
                    path,
                    f"prompt com {tokens} tokens (teto {config.MAX_OPTION_TOKENS})",
                )
            )

    total = len(all_nodes)
    if total > config.MAX_FLAT_FOLDERS:
        issues.append(
            _warning(
                "router_enabled",
                "/",
                f"{total} pastas; classificação usará o router hierárquico",
            )
        )
        issues.extend(_combined_warning(roots, "/", keep=False))
        for path, node in all_nodes:
            if node.children:
                issues.extend(_combined_warning(node.children, path, keep=True))
    else:
        issues.extend(_combined_warning([node for _, node in all_nodes], "/", keep=False))
    return issues
