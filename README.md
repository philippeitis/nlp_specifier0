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

| Dependency | Required | Purpose |
| :--- | :---: | :--- |
| python3-dev | Yes | embed a Python interpreter into the Rust executable |
| spaCy (via pip) | Yes | NLP Processing |
| spaCy.en_core_web_lg | Yes | Language model |
| unidecode (via pip) | Yes | Cleaning input to spaCy and JML NLP |
| requests (via pip) | Yes | Interfacing with JML NLP |
| nltk (via pip) | No (dev) | code-generation | 
| networkx (via pip) | No (dev) | detecting cycles in code-generation |
| graphviz | No | Rendering parse-trees |
| click | No | Visualization CLI interface |

Optionally, it may be useful to review these links:

https://www.nltk.org/install.html
https://spacy.io/usage

### WordNet POS tags reference
This link provides a useful reference for the POS tags generated by spaCy:
http://erwinkomen.ruhosting.nl/eng/2014_Longdale-Labels.htm

[comment]: <> (### Launching NLP Server &#40;For WordNet parsing&#41;)

[comment]: <> (This command will launch StanfordCoreNLP. This is not necessary to use the NLP parser.)

[comment]: <> (```bash)

[comment]: <> (java -mx4g -cp "*" edu.stanford.nlp.pipeline.StanfordCoreNLPServer -port 9000 -timeout 15000)

[comment]: <> (```)



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
