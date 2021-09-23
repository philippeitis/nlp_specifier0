import time
from collections import defaultdict
import logging
from pathlib import Path
from typing import Collection

from nltk import Tree
import click

from pyrs_ast.lib import LitAttr, Fn, HasItems, Crate, Struct, Mod
from pyrs_ast.scope import Scope
from pyrs_ast import AstFile

DIR_PATH = Path(__file__).parent.resolve()

# This is a bit of a hack for running things in PyCharm
try:
    from doc_parser import Parser, GRAMMAR_PATH, is_quote
    from fn_calls import InvocationFactory, Invocation
    from grammar import Specification, generate_constructor_from_grammar
    from nlp_query import query_from_sentence, Phrase, Word, SimPhrase
except ImportError:
    import sys

    sys.path.insert(0, str(DIR_PATH))
    from doc_parser.doc_parser import Parser, GRAMMAR_PATH, is_quote
    from doc_parser.fn_calls import InvocationFactory, Invocation
    from doc_parser.grammar import Specification, generate_constructor_from_grammar
    from doc_parser.nlp_query import query_from_sentence, Phrase, Word, SimPhrase

TESTCASE_PATH = DIR_PATH / "base_grammar_test_cases.txt"
LOGGER = logging.getLogger(__name__)


def tree_references_fn(fn: Fn, tree: Tree) -> bool:
    """Determines whether the tree references the provided fn."""
    fn_name = f"{fn.ident}"
    if isinstance(tree, str):
        label = tree
    else:
        label: str = tree.label()

    if label.startswith("FN_"):
        name, _ = label.rsplit("_", 1)
        _, name = name.split("_", 1)

        if name == fn_name:
            return True

    if isinstance(tree, str):
        return False

    return any(tree_references_fn(fn, child) for child in tree)


def tree_contains_fn_call(tree: Tree) -> bool:
    """Determines whether the tree references the provided fn."""
    if isinstance(tree, str):
        return tree == "FNCALL"

    if tree.label() == "FNCALL":
        return True

    return any(tree_contains_fn_call(child) for child in tree)


def apply_specifications(fn: Fn, parser: Parser, scope: Scope, invoke_factory):
    """Creates a specification for the function, using all available sentences.
    Each sentence is cross-referenced with the grammar to form a syntax tree. If a syntax tree can be formed,
    this is treated as a valid specification, and is compiled into the Prusti annotation format.

    Prefers non-self-referential trees wherever possible.

    If no tree can be found for a particular sentence, no specification is added.
    """

    if not fn.should_specify():
        LOGGER.info(f"fn {fn.ident} is not annotated with #[specify], and will not be specified.")
        return

    fn_idents = set(ty.ident for ty in fn.inputs)
    sections = fn.docs.sections()
    for section in sections:
        if section.header is not None:
            continue
        LOGGER.info(f"Specifying documentation section {section.header} of {fn.ident}")
        for sentence in section.sentences:
            try:
                skipped_self_ref = []
                skipped_fn_call = []
                parse_it = parser.parse_tree(sentence, idents=fn_idents)
                spec = None
                for tree in parse_it:
                    if tree_references_fn(fn, tree):
                        LOGGER.info("Skipping tree due to self-reference.")
                        skipped_self_ref.append(tree)
                    elif tree_contains_fn_call(tree):
                        LOGGER.info("Skipping tree due to self-reference.")
                        skipped_fn_call.append(tree)
                    else:
                        LOGGER.info("Found tree without self-reference, applying.")
                        spec = Specification(tree, invoke_factory).as_spec()
                        break

                if spec is None:
                    LOGGER.info("Attempting to use specification with function call.")
                    spec = Specification(next(iter(skipped_fn_call)), invoke_factory).as_spec()
                    # spec = Specification(next(iter(skipped)), invoke_factory).as_spec()

                attr = LitAttr(spec)

                LOGGER.info(f"[{sentence}] was transformed into the following specification: {attr}")
                fn.attrs.append(attr)
            except ValueError as v:
                LOGGER.error(f"While specifying [{sentence}], error occurred: {v}")
                LOGGER.info(
                    f"[{sentence}] has the following tags: {parser.tokenize(sentence, idents=fn_idents).tags}"
                )
            except StopIteration as s:
                LOGGER.info(f"No specification could be generated for [{sentence}]")
                LOGGER.info(
                    f"[{sentence}] has the following tags: {parser.tokenize(sentence, idents=fn_idents).tags}"
                )
                query = query_from_sentence(sentence, parser)
                LOGGER.info("Found phrases: " + ", ".join(str(x) for x in query.fields))
                for fn in scope.find_fn_matches(query):
                    LOGGER.info(f"Found match: {fn.sig_str()}")


def specify_item(item: HasItems, parser: Parser, scope: Scope, invoke_factory):
    if isinstance(item, Mod) and item.items is None:
        return

    for sub_item in item.value_iter():
        if isinstance(sub_item, Fn):
            apply_specifications(sub_item, parser, scope, invoke_factory)
        elif isinstance(sub_item, HasItems):
            specify_item(sub_item, parser, scope, invoke_factory)


def find_specifying_sentence(fn: Fn, parser: Parser, invoke_factory: InvocationFactory, word_replacements,
                             sym_replacements):
    """Finds the sentence that specifies the function, and adds it to InvokeFactory.
    NOTE: Currently, the first sentence is treated as the specifying sentence. This is obviously not a robust
    metric, and should be updated.

    Factors which might be considered could be the function's name (for instance, Vec::remove), the number of unique
    idents, incidence of important words.
    """
    sections = fn.docs.sections()
    fn_idents = set(ty.ident for ty in fn.inputs)
    LOGGER.info(f"Searching for explicit invocations for fn {fn.ident}")

    for attr in fn.attrs:
        if str(attr.ident) == "invoke":
            invoke = str(attr.tokens[1].val.strip("\" "))
            LOGGER.info(f"Found invocation [{invoke}] for fn {fn.ident}")
            invoke_factory.add_invocation(fn, Invocation.from_sentence(fn, invoke))

    for section in sections:
        if section.header is not None:
            continue
        LOGGER.info(f"Determining descriptive sentence for {fn.ident}")
        descriptive_sentence = section.sentences[0]
        sent = parser.tokenize(descriptive_sentence, idents=fn_idents)
        for sym, word in zip(sent.tags, sent.words):
            if is_quote(word):
                continue

            word_replacements[word].add(sym)
            sym_replacements[sym].add(word)

        invoke_factory.add_fuzzy_invocation(fn, sent.tags, sent.words)


def populate_grammar_helper(item: HasItems, parser: Parser, invoke_factory, word_replacements, sym_replacements):
    if isinstance(item, Mod) and item.items is None:
        return

    for sub_item in item.value_iter():
        if isinstance(sub_item, Fn):
            find_specifying_sentence(sub_item, parser, invoke_factory, word_replacements, sym_replacements)
        elif isinstance(sub_item, HasItems):
            populate_grammar_helper(sub_item, parser, invoke_factory, word_replacements, sym_replacements)


def generate_grammar(ast, helper_fn=populate_grammar_helper):
    """Iterates through all items in the ast, adds relevant invocations from functions into the grammar,
    and returns a grammar with all invocations, as well as an InvocationFactory to dynamically dispatch
    a particular invocation to the relevant constructor.
    """

    word_replacements = defaultdict(set)
    sym_replacements = defaultdict(set)
    invoke_factory = InvocationFactory(generate_constructor_from_grammar)
    helper_fn(ast, Parser.default(), invoke_factory, word_replacements, sym_replacements)

    grammar = invoke_factory.grammar()
    replacement_grammar = ""

    if "PRP$" in sym_replacements:
        sym_replacements["PRPS"] = sym_replacements.pop("PRP$")

    word_filter = lambda word: not set(",`!.();:*<>=+-?&%'\"\\[]{}#").isdisjoint(word)
    for word, syms in word_replacements.items():
        if word_filter(word):
            continue
        if "PRP$" in syms:
            syms.remove("PRP$")
            syms.add("PRP")

        syms = " | ".join(f"\"{word}_{sym}\"" for sym in syms)
        grammar = grammar.replace(f"\"{word}\"", f"WD_{word}")
        replacement_grammar += f"WD_{word} -> {syms}\n"
    for sym, words in sym_replacements.items():
        if sym in {"COMMA", "DOT", "EXCL", "-LRB-", "-RRB-", ":", ".", ",", "$", "(", ")"}:
            continue
        syms = " | ".join(f"\"{word}_{sym}\"" for word in words if not word_filter(word))
        # grammar = grammar.replace(f"{sym} -> \"{sym}\"", "")
        replacement_grammar += f"{sym} -> {syms} | \"{sym}\"\n"

    with open(GRAMMAR_PATH) as f:
        full_grammar = f.read() + "\n# FUNCTION INVOCATIONS\n\n" + grammar + "\n\n# Word Replacements\n\n" + replacement_grammar

    return full_grammar, invoke_factory


def invoke_helper(invocations: Collection, invocation_triples=None, use_invokes=False):
    """Demonstrates creation of invocations from specifically formatted strings, as well as usage."""

    from nltk import Tree
    from grammar import UnsupportedSpec

    class FnMock:
        def __init__(self, ident: str):
            self.ident = ident

    def populate_grammar_helper(sentences, parser: Parser, invoke_factory, word_replacements, sym_replacements):
        for sentence in sentences:
            if isinstance(sentence, tuple):
                invoke_factory.add_invocation(
                    FnMock(sentence[0]),
                    Invocation.from_sentence(FnMock(sentence[0]), sentence[1])
                )
                sentence = sentence[2]

            sent = parser.tokenize(sentence)
            for sym, word in zip(sent.tags, sent.words):
                if is_quote(word):
                    continue
                word_replacements[word].add(sym)
                sym_replacements[sym].add(word)

    invocation_triples = invocation_triples or []
    if use_invokes:
        grammar, factory = generate_grammar(invocation_triples + invocations, populate_grammar_helper)
        parser = Parser(grammar)
    else:
        parser = Parser.default()
        factory = None

    ntrees = 0
    nspecs = 0
    num_sents = len(invocations) + len(invocation_triples)
    successful_sents = 0
    unsucessful_sents = []
    specified_sents = 0
    start = time.time()
    sentences = list(invocations)
    parser.stokenize(sentences)
    end = time.time()
    print("Time to tokenize sentences:", end - start)

    start = time.time()
    for sentence in sentences:
        # print("=" * 80)
        # print("Sentence:", sentence)
        # print("    Tags:", parser.tokenize(sentence).tags)
        # print("=" * 80)
        specs = []
        trees = []
        try:
            for tree in parser.parse_tree(sentence, attach_tags=use_invokes):
                tree: Tree = tree
                trees.append(tree)
                specs.append(None)
                try:
                    specs[-1] = Specification(tree, factory).as_spec()
                except LookupError as e:
                    # print(f"No specification found: {e}")
                    pass
                except UnsupportedSpec as s:
                    # print(f"Specification element not supported ({s})")
                    pass
        except ValueError as e:
            pass
            # print(f"Grammar: ({e})")
        if specs:
            # print("=" * 80)
            # print("Sentence:", sentence)
            # print("    Tags:", parser.tokenize(sentence).tags)
            # print("=" * 80)
            # for tree, spec in zip(trees, specs):
            #     print(tree)
            #     print(spec)
            # print()
            successful_sents += 1
        else:
            unsucessful_sents.append(sentence)
        nspecs += len([spec for spec in specs if spec])
        ntrees += len(trees)
        if len([spec for spec in specs if spec]) != 0:
            specified_sents += 1
    import random
    # for sentence in random.choices(unsucessful_sents, k=50):
    # print("=" * 80)
    # print("Sentence:", sentence)
    # print("    Tags:", parser.tokenize(sentence).tags)
    # print("=" * 80)
    end = time.time()
    print("          Sentences:", num_sents)
    print("Successfully parsed:", successful_sents)
    print("              Trees:", ntrees)
    print("     Specifications:", nspecs)
    print("Specified Sentences:", specified_sents)
    print("       Time elapsed:", end - start)

    return successful_sents, nspecs, ntrees, num_sents, specified_sents


def invoke_demo():
    """Demonstrates creation of invocations from specifically formatted strings, as well as usage."""

    invocation_triples = [
        ("print", "Prints {item:OBJ}", "Prints 0u32"),
        ("print", "Really prints {item:OBJ}", "Really prints \"HELLO WORLD\""),
        ("print", "Prints {item:OBJ} in {mod:ENUM}", "Really prints \"HELLO WORLD\""),
        ("print", "{item:OBJ} is printed", "`self.x()` is printed"),
        ("add", "{self:OBJ} is incremented by {rhs:IDENT}", "`self` is incremented by 1"),
        ("contains", "{self:OBJ} {MD} contain {item:OBJ}", "`self` must contain 0u32"),
        ("contains", "{self:OBJ} contains {item:OBJ}", "`self` contains 0u32"),
        ("contains", "contain {item:OBJ} {self:OBJ} {MD}", "contain 0u32, `self` will")
    ]

    invocations = [
        "Returns `true` if `self` is green.",
        "Returns `true` if `self` contains 0u32",
        "Returns the reciprocal of `self`"
    ]

    invoke_helper(invocations, invocation_triples)


def profiling(statement: str):
    import cProfile
    import pstats
    cProfile.run(statement, "stats")
    pstats.Stats("stats").sort_stats(pstats.SortKey.TIME).print_stats(20)


@click.group()
def cli():
    pass


@cli.command()
@click.option('--path', "-p", default=DIR_PATH / "../data/test3.rs", help='Source file to specify.', type=Path)
def end_to_end(path: Path):
    """Demonstrates entire pipeline from end to end on provided file."""
    ast = AstFile.from_path(path)
    grammar, invoke_factory = generate_grammar(ast)

    parser = Parser(grammar)
    print(grammar)
    specify_item(ast, parser, ast.scope, invoke_factory)
    print(ast)


@cli.group()
def specify():
    """Creates specifications for a variety of sources."""
    pass


@specify.command("sentence")
@click.argument("sentence")
def specify_sentence(sentence: str):
    """Specifies the sentence, and prints the specification to the console."""
    parser = Parser.default()
    tree = next(
        parser.parse_tree(sentence, attach_tags=False)
    )
    print(Specification(tree, None).as_spec())


@specify.command("file")
@click.option('--path', "-p", default=DIR_PATH / "../data/test3.rs", help='Source file to specify.', type=Path)
@click.option('--dest', "-d", default=None, type=Path,
              help='Output file path. If not specified, defaults to --path variable, adding _specified suffix.'
              )
def specify_file(path: Path, dest: Path):
    """Specifies the items in the file at path, and writes a copy of the file with specifications included to
    `dest`."""
    ast = AstFile.from_path(path)
    grammar, invoke_factory = generate_grammar(ast)

    parser = Parser(grammar)
    specify_item(ast, parser, ast.scope, invoke_factory)

    if dest is None:
        dest = path.parent / Path(path.stem + "_specified.rs")
    dest.write_text(str(ast))


@specify.command("docs")
@click.option('--path', default=None, help='Path to documentation.', type=Path)
def specify_docs(path: Path):
    """Specifies each item in the documentation at the given path.
    Documentation can be generated using `cargo doc`, or can be downloaded via `rustup`.

    By default, specifies items in toolchain documentation.
    """
    from doc_json import get_all_files, get_toolchains
    path = path or get_toolchains()[0] / Path("share/doc/rust/html/")
    files = get_all_files(path)

    sentences = []
    for item in files.values():
        if isinstance(item, Struct):
            for method in item.methods:
                sections = method.docs.sections()
                if len(sections):
                    sentences += sections[0].sentences
        elif isinstance(item, Fn):
            sections = item.docs.sections()
            if len(sections):
                sentences += sections[0].sentences
    sentences = set(sentences)
    print(invoke_helper(sentences))


@specify.command("testcases")
@click.option('--path', default=TESTCASE_PATH, help='Path to test cases.', type=Path)
def specify_testcases(path: Path):
    """Specifies each newline separated sentence in the provided file."""
    with open(path, "r") as file:
        invoke_helper([line.strip() for line in file.readlines()])



def tokenize_all_sents():
    parser = Parser.default()
    sentences = list(
        set([line.strip() for line in Path("./doc_parser/rs_doc_parser/sents.txt").read_text().splitlines()]))
    start = time.time()
    # tokens = [parser.tokenize(sentence) for sentence in sentences]
    sents = parser.stokenize(sentences)
    end = time.time()
    for sent in sents[0:250]:
        print('"' + " ".join(sent.tags) + '",')
    exit()
    # print([(sent.tags, sent.words) for sent in sents[0:20]])
    # print(set(item for sent in sents for item in sent.tags))
    unique_lits = []
    for sent in sents:

        for tag, word in zip(sent.tags, sent.words):
            if tag == "LIT":
                print(" ".join(sent.words))
                print(word)
                break

    print(unique_lits)
    # print("\n".join(str(x.tags) for x in tokens))
    print(end - start)

    start = time.time()
    tokens = parser.stokenize(sentences)
    # tokens = [parser.tokenize(sentence) for sentence in sentences]
    end = time.time()

    # print("\n".join(str(x.tags) for x in tokens))
    print(end - start)


if __name__ == '__main__':
    formatter = logging.Formatter('[%(name)s/%(funcName)s] %(message)s')
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    sh.setLevel(logging.INFO)
    logging.getLogger().addHandler(sh)
    logging.getLogger().setLevel(logging.WARNING)
    cli()

    # bert library
    # search around

    # TODO: Detect duplicate invocations.
    # TODO: keyword in fn name, capitalization?
    # TODO: similarity metrics (capitalization, synonym distance via wordnet)
    # TODO: Decide spurious keywords

    # TODO: Mechanism to evaluate code quality
    # TODO: Add type to CODE item? eg. CODE_USIZE, CODE_BOOL, CODE_STR, then make CODE accept all of these
    #  std::any::type_name_of_val
    # TODO: allow specifying default value in #[invoke]
    #  eg. #[invoke(str, arg1 = 1usize, arg2 = ?, arg3 = ?)]

    # TODO:
    #  Implement two piece grammar & code-gen (yeet comma / excl / dot rules, fn_calls.py)
    #  Test FNVHasher / alternatives for CFG
    #  Finish porting grammar.py (yeet lemmatizer.py, grammar.py)
