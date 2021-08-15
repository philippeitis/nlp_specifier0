import jsons as jsons
import json

from pyrs_ast import AstFile
import astx

from pyrs_ast.lib import HasAttrs, HasItems
from pyrs_ast.scope import Scope


class LexError(ValueError):
    pass


def read_ast_from_str(s: str) -> AstFile:
    result = astx.ast_from_str(s)
    try:
        return AstFile(scope=Scope(), **jsons.loads(result))
    except json.decoder.JSONDecodeError:
        pass
    raise LexError(result)


def read_ast_from_path(path):
    with open(path, "r") as file:
        code = file.read()
    return read_ast_from_str(code)


def print_ast_docs(ast: HasItems):
    for item in ast.items:
        if isinstance(item, HasAttrs):
            docs = item.extract_docs()
            for section in docs.sections():
                print(section.header)
                print(section.body)
        if isinstance(item, HasItems):
            print_ast_docs(item)


def print_ast(ast: AstFile):
    for attr in ast.attrs:
        print(attr)

    for item in ast.items:
        print(item)
        print()


if __name__ == '__main__':
    from scope import Query, QueryField, FnArg, Word, Phrase
    from scope import is_synonym
    ast = read_ast_from_path("test2.rs")
    words = [Word("Hello", False, False), Word("globe", True, False)]
    items = ast.scope.find_fn_matches(Query([Phrase(words)]))
    for item in items:
        print(item)
    print(is_synonym("world", "globe"))