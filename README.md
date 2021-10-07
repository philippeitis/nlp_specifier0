# Installation
Python 3.6+ and Rust should already be installed for the parsing steps. To perform verification of output specifcations, Prusti should also be installed.
Dependencies for individual components of the system are specified below, or are otherwise manually installed using provided `setup.sh` scripts.
Note that all .sh files and commands provided are specific to Linux. 

Also note that to avoid contaminating your Python installation, it is best to use `venv`.

## Python Implementation
The python implementation is available at https://github.com/philippeitis/nlp_specifier/tree/62d4d51a30c173f65daaf631b7acca0ffbf572a3

## Specifying Documentation
This project allows specifying both Rust documentation pages (produced through `cargo doc`, or downloaded from `rustup`) and Rust source code. This functionality
is primarily available through [src/doc_parser/](src/doc_parser/). To build this executable for your system, use 
```bash
cd ./src/doc_parser/ && cargo build --release ; cd ..
```

## NLP Processing
The NLP parsing code tokenizes, assigns parts of speech tags to tokens, and detects named entities using spaCy. To set up the dependencies, run [src/setup.sh](src/setup.sh):
```bash
cd ./src/ && sudo chmod +x ./setup.sh && ./setup.sh && cd .
```

This installs:

| Dependency | Feature | Purpose |
| :--- | :---: | :--- |
| python3-dev | Core | embed a Python interpreter into the Rust executable |
| spaCy (via pip) | Core | NLP Processing |
| spaCy.en_core_web_lg | Core | Language model |
| unidecode (via pip) | Core | Cleaning input to spaCy and JML NLP |
| gfortran | Search | Build optimized BLAS routines for sentence similarity methods |
| requests (via pip) | NER/SRL | Interfacing with JML NLP |
| nltk (via pip) | Dev | code-generation | 
| networkx (via pip) | Dev | detecting cycles in code-generation |
| graphviz | Visualization | Rendering parse-trees |
| click | Visualization | Visualization CLI interface |

Optionally, it may be useful to review these links:

https://www.nltk.org/install.html
https://spacy.io/usage
https://pyo3.rs/v0.14.5/index.html#using-python-from-rust

### WordNet POS tags reference
This link provides a useful reference for the POS tags generated by spaCy:
http://erwinkomen.ruhosting.nl/eng/2014_Longdale-Labels.htm

## Named-entity Recognition and Semantic Role Labelling
### Requirements
To use NER and SRL analysis for documentation, Docker and Docker Compose must be installed. Additionally, downloading the relevant models requires installing Git and Git LFS. All other dependencies for this are set up using [jml_nlp/setup.sh](jml_nlp/setup.sh).
```bash
cd ./jml_nlp/ && sudo chmod +x ./setup.sh && ./setup.sh && cd .
```
After running this script, the SRL service will be available at 127.0.0.8:701, and the NER service will be available at 127.0.0.8:702.
[src/nlp/ner.py](src/nlp/ner.py) provides functions for annotating text using these services. The Tokenizer class in [src/nlp/tokenizer.py](doc_parser/doc_parser.py) transforms these annotations to a format that can be rendered by spaCy's displaCy tool.

The NER and SRL models are sourced from `Combining formal and machine learning techniques for the generation of JML specifications`.

# Usage
Once installation is complete, this project can be used through `doc_parser`. To run the program, use `./doc_parser`, or `cargo run --release` at the 
appropriate locations. Run the following command to see a list of all possible commands.
```console
foo@bar:~$ ./doc_parser -h
doc_parser

USAGE:
    doc_parser <SUBCOMMAND>

FLAGS:
    -h, --help       Print help information
    -V, --version    Print version information

SUBCOMMANDS:
    end-to-end    Demonstrates entire pipeline from start to end on provided file, writing
                  output to terminal
    help          Print this message or the help of the given subcommand(s)
    render        Visualization of various components in the system's pipeline
    specify       Creates specifications for a variety of sources
```

To see more specific help, do the following:
```console
foo@bar:~$ ./doc_parser end-to-end --help
doc_parser-end-to-end 

Demonstrates entire pipeline from start to end on provided file, writing output to terminal

USAGE:
    doc_parser end-to-end [OPTIONS]

FLAGS:
    -h, --help       Print help information
    -V, --version    Print version information

OPTIONS:
    -p, --path <PATH>    Source file to specify [default: ../../data/test3.rs]
```

## Major TODOs:
- Build server interface for NLP
- Tree formatting
- Convert codegen to Rust build.rs (to ensure that we don't introduce inconsistencies when parsing grammar)
- Build synonym sets for this problem domain
- Train model which correctly tags VB cases (currently tagged as "NN")
- Build pseudo-compiler to iteratively resolve specification

- Detect fn purity
- Build tool to clean up resulting specifications
- Detect vacuously true specifications
- Quality of specification?
- Desugar for loops?

## Plan
1. Straight up search using current methods, and plug in symbols
- No slotting at all (but methods / struct fields should be attached as .x, while lone functions are wrapping)
2. Provide API, create Docker interface for this project

## Examples of unaccepted (maybe should be accepted?)
- Replaces first N matches of a pattern with another string
- `::ffff:a.b.c.d` becomes `a.b.c.d`
- The elements are passed in opposite order from their order in the slice , so if `same_bucket(a, b)` returns `true` , `a` is moved at the end of the slice
- Returns the capacity this `OsString` can hold without reallocating
- Note that the capacity of `self` does not change
- Returns `true` if the associated `Once` was poisoned prior to the invocation of the closure passed to `Once::call_once_force()`

## Examples of Unverifiable spec
- `replace_with` does not need to be the same length as `range`
- This method is equivalent to `CString::new` except that no runtime assertion is made that `v` contains no 0 bytes , and it requires an actual byte vector , not anything that can be converted to one with Into
- See `send` for notes about guarantees of whether the receiver has received the data or not if this function is successful


## Options
- Find matches which do not include the sentence (this approach does not handle interior skipwords)
- Preprocess sentence before tree - detect and remove common fillers (already done in part with SPACE)
- Process fragments, have grammar for interior fragments (eg. "otherwise x is true")
- Allow chaining (requires Context)
