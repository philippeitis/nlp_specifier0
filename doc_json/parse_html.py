import itertools
import json
from pathlib import Path
from typing import List, Dict, Optional, Union
from multiprocessing import Pool
import subprocess

import astx
from lxml import etree
from lxml.html import parse

from pyrs_ast.docs import Docs
from py_cargo_utils import rustup_home

from pyrs_ast.lib import Crate, Fn, Struct, Method
from pyrs_ast.scope import Scope


def peek(it):
    first = next(it)
    return first, itertools.chain([first], it)


def remove_all_spans(item: etree.ElementBase):
    for val in item.findall("span"):
        if "since" in val.classes or "notable-traits-tooltip" in val.classes or "notable-traits" in val.classes:
            item.remove(val)


def remove_all_src_links(item: etree.ElementBase):
    for val in item.findall("a"):
        if "srclink" in val.classes:
            item.remove(val)
        if val.attrib["href"] == "javascript:void(0)":
            item.remove(val)


def find_with_class(item: etree.ElementBase, tag: str, class_: str):
    try:
        return next(find_with_class_iter(item, tag, class_))
    except StopIteration:
        return None


def find_with_class_iter(item: etree.ElementBase, tag: str, class_: str):
    for result in item.findall(tag):
        if class_ in result.classes:
            yield result


def text(item: etree.ElementBase) -> str:
    return etree.tostring(item, method="text", encoding="unicode")


def stringify(item: etree.ElementBase) -> str:
    s = ""
    itext = item.text or ""
    if item.tag == "code":
        s += f"`{itext}`"
    else:
        s += itext

    for sub in item.getchildren():
        s += stringify(sub)
        s += sub.tail or ""

    return s


class RList:
    def __init__(self, doc):
        self.items = []
        for item in doc:
            assert item.tag == "li"
            self.items.append(stringify(item))


class HasDoc:
    HEADER = {
        f"h{n}": "#" * n for n in range(1, 7)
    }

    @classmethod
    def parse_doc(cls, html_doc: etree.ElementBase) -> Docs:
        docs = Docs()
        if html_doc is None:
            return docs

        for item in html_doc:
            h = cls.HEADER.get(item.tag)
            if h and "section-header" in item.classes:
                docs.push_line(f"{h} {stringify(item)}")
            elif item.tag == "p":
                text_ = stringify(item)
                if text_:
                    docs.push_line(text_.replace("\n", " "))
                else:
                    docs.push_line("")
            elif item.tag == "div" and "example-wrap" in item.classes:
                docs.push_line(cls.parse_example(item))
            elif item.tag == "ul":
                for sub_item in RList(item).items:
                    docs.push_line("* " + sub_item.strip())
            elif item.tag == "ol":
                for n, sub_item in enumerate(RList(item).items):
                    docs.push_line("{n}. " + sub_item.strip())
            elif item.tag == "blockquote":
                docs.push_line(f"> {stringify(item)}")
            elif item.tag == "table":
                # Tables not handled. std::mem::size_of demonstrates usage.
                pass
            elif item.tag == "div" and "information" in item.classes:
                # Tooltips are not handled.
                pass
            else:
                print("Unknown item", item)
        docs.consolidate()
        return docs

    @classmethod
    def parse_example(cls, doc: etree.ElementBase) -> str:
        return "```CODE```"


class DocStruct(Struct):
    @classmethod
    def from_block(cls, body: etree.ElementBase, scope: Scope = None):
        type_decl = find_with_class(body, "div", "docblock")
        body.remove(type_decl)
        methods = []

        parent = find_with_class(body, "details", "top-doc")
        if parent is not None:
            doc = find_with_class(parent, "div", "docblock")
            docs = HasDoc.parse_doc(doc)
            body.remove(parent)
        else:
            docs = Docs()

        s = f"{docs}\n{stringify(type_decl)}"
        try:
            struct = cls(**json.loads(astx.parse_struct(s)), scope=scope or Scope())
        except json.decoder.JSONDecodeError:
            return

        impl_block = find_with_class(body, "details", "implementors-toggle")
        if impl_block is not None:
            for doc in find_with_class_iter(impl_block, "div", "impl-items"):
                struct.methods += struct.eat_impl_dispatch(doc, scope)
        return struct

    def eat_impls_old(self, doc: etree.ElementBase, doc_iter, scope: Scope) -> List["DocMethod"]:
        items = []
        while True:
            try:
                item, doc_iter = peek(doc_iter)
                if item.tag != "div":
                    return items + self.eat_impl(doc, doc_iter, scope)
                remove_all_spans(item)
                remove_all_src_links(item)
                name = stringify(item)
                next(doc_iter)
                doc.remove(item)
            except StopIteration:
                break

            try:
                item, doc_iter = peek(doc_iter)
                if "item-info" in item.classes:
                    next(doc_iter)
                else:
                    raise ValueError(str(set(item.classes)))
            except StopIteration:
                pass
            items.append(DocMethod.from_ident_and_docs(name, Docs(), parent_type=self, scope=scope))

        return items

    def eat_impl(self, doc: etree.ElementBase, doc_iter, scope: Scope) -> List["DocMethod"]:
        items = []
        while True:
            try:
                item, doc_iter = peek(doc_iter)
                if item.tag != "details":
                    return items + self.eat_impls_old(doc, doc_iter, scope)
                items.append(DocMethod.from_block(item, parent_type=self, scope=scope))
                next(doc_iter)
                doc.remove(item)

            except StopIteration:
                break
        return items

    def eat_impl_dispatch(self, doc: etree.ElementBase, scope: Scope) -> List["DocMethod"]:
        try:
            first = next(iter(doc))
            if "method" in first.classes:
                return self.eat_impls_old(doc, iter(doc), scope)
            return self.eat_impl(doc, iter(doc), scope)

        except StopIteration:
            return []


class DocFn(Fn):
    @classmethod
    def from_block(cls, body: etree.ElementBase, scope: Scope = None):
        fn_decl_block = find_with_class(body, "pre", "fn")
        remove_all_src_links(fn_decl_block)
        remove_all_spans(fn_decl_block)
        fn_decl = stringify(fn_decl_block) + " {}"
        body.remove(fn_decl_block)

        parent = find_with_class(body, "details", "rustdoc-toggle")
        if parent is None:
            docs = Docs()
        else:
            doc = find_with_class(parent, "div", "docblock")
            docs = HasDoc.parse_doc(doc)

        s = f"{docs}\n{fn_decl}"
        try:
            return cls(**json.loads(astx.parse_fn(s)), scope=scope or Scope())
        except json.decoder.JSONDecodeError:
            pass


class DocMethod(Method):
    @classmethod
    def from_ident_and_docs(cls, ident: str, docs: Docs, parent_type: Struct = None, scope: Scope = None):
        s = f"{docs}\n{ident} {{}}"
        try:
            return cls(**json.loads(astx.parse_impl_method(s)), parent_type=parent_type, scope=scope or Scope())
        except json.decoder.JSONDecodeError:
            pass

    @classmethod
    def from_block(cls, block, parent_type: Struct = None, scope: Scope = None) -> "DocMethod":
        name = block.find("summary/div")
        remove_all_src_links(name)
        remove_all_spans(name)
        name = stringify(name)
        docs = HasDoc.parse_doc(find_with_class(block, "div", "docblock"))
        return cls.from_ident_and_docs(name, docs, parent_type, scope)


DISPATCH = {
    "fn": DocFn.from_block,
    "struct": DocStruct.from_block,
}


class DocCrate(Crate):
    IGNORE = {
        "rust-by-example", "reference", "embedded-book", "edition-guide", "arch", "core_arch",
        "book", "nomicon", "unstable-book", "cargo", "rustc", "implementors", "rustdoc"
    }

    @classmethod
    def from_root_file(cls, path):
        pass

    @staticmethod
    def get_all_doc_files(path: Path) -> List[Path]:
        if path.is_dir() and path.name in DocCrate.IGNORE:
            return []

        choices = ("struct.", "fn.", "enum.", "constant.", "macro.", "trait.", "keyword.")

        items = []
        for child_path in path.iterdir():
            if child_path.is_dir():
                items += DocCrate.get_all_doc_files(child_path)
            else:
                name = child_path.name
                if any(name.startswith(choice) for choice in choices):
                    items.append(child_path)
                # can also have trait or macro
        return items


def files_into_dict(paths: List[Path]) -> Dict[str, List[Path]]:
    path_dict = {
        "fn": [],
        "struct": [],
        "enum": [],
        "constant": [],
        "macro": [],
        "trait": [],
        "keyword": [],
    }
    for path in paths:
        path_dict[path.name.split(".")[0]].append(path)
    return path_dict


def parse_file(path: Path) -> Optional[Union[Struct, Fn]]:
    with open(path, "r") as file:
        soup = parse(file)
        title = soup.find("head/title")
        if title.text == "Redirection":
            return
        body = soup.find("body/section")
        return DISPATCH.get(
            path.stem.split(".", 1)[0],
            # Default case: return None
            lambda *args, **kwargs: None
        )(body)


def _get_all_files_st(toolchain_root: Path):
    target_dir = (toolchain_root / Path("share/doc/rust/html/")).expanduser()
    files = files_into_dict(DocCrate.get_all_doc_files(target_dir))
    targets = files["fn"] + files["struct"]
    return [(file, path) for file, path in zip(map(parse_file, targets), targets) if file]


def get_all_files(toolchain_root: Path, num_processes: int = 12):
    target_dir = (toolchain_root / Path("share/doc/rust/html/")).expanduser()
    files = files_into_dict(DocCrate.get_all_doc_files(target_dir))

    # For debugging purposes
    if num_processes == 1:
        return _get_all_files_st(toolchain_root)

    with Pool(num_processes) as p:
        targets = files["fn"] + files["struct"]
        return [(file, path) for file, path in zip(p.map(parse_file, targets), targets) if file]


def main(toolchain_root: Path):
    for file, path in get_all_files(toolchain_root):
        print(path)
        print(file)
        if isinstance(file, Struct):
            for method in file.methods:
                print(method)


def choose_random_items(toolchain_root: Path):
    import random
    import webbrowser

    target_dir = (Path(toolchain_root) / Path("share/doc/rust/html/")).expanduser()
    files = files_into_dict(DocCrate.get_all_doc_files(target_dir))

    selected = random.choices(files["struct"], k=25)
    for item in selected:
        webbrowser.open(str(item))
        file = parse_file(item)
        if file:
            print(item)
            print(file)
            if isinstance(file, Struct):
                for method in file.methods:
                    print(method)
            input()


def get_toolchains() -> List[Path]:
    root = Path(rustup_home()) / Path("toolchains")
    paths = subprocess.run(["rustup", "toolchain", "list"], capture_output=True).stdout.splitlines()
    return [
        root / Path(p.removesuffix(b" (default)").strip().decode("utf-8"))
        for p in paths
    ]


if __name__ == '__main__':
    main(get_toolchains()[0])

    # make section 1 intro / problem statement / high level approach
    # diagram of process eg. tokenizer -> parser -> specifier -> search
    # section 1.1. motivate sequence of problems
    # sections 1.2. high level details - methods used and why
    # section 3. specific details
    # mention that documentation is incomplete spec
    # explain that target is verifier, and not all things are supported (eg. sideeffectful operations)
    # squares connecting each component
