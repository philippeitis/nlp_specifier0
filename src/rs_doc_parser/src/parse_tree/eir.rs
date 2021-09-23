use std::hash::Hash;

use chartparse::TreeWrapper;
use chartparse::production::{NonTerminal, Terminal as CTerminal};
use chartparse::tree::TreeNode;
use chartparse::grammar::ParseSymbol;

use crate::parse_tree::Terminal;
use crate::parse_tree::tree::TerminalSymbol;

#[derive(Hash, Copy, Clone, Debug, Eq, PartialEq)]
pub enum Symbol {
   S,
   MNN,
   TJJ,
   MJJ,
   MVB,
   IFF,
   EQTO,
   BITOP,
   ARITHOP,
   SHIFTOP,
   OP,
   OBJ,
   REL,
   MREL,
   PROP,
   PROP_OF,
   RSEP,
   RANGE,
   RANGEMOD,
   ASSERT,
   HASSERT,
   QUANT,
   QUANT_EXPR,
   QASSERT,
   MRET,
   BOOL_EXPR,
   COND,
   RETIF,
   SIDE,
   ASSIGN,
   EVENT,
   OBJV,
    NN,
    NNS,
    NNP,
    NNPS,
    VB,
    VBP,
    VBZ,
    VBN,
    VBG,
    VBD,
    JJ,
    JJR,
    JJS,
    RB,
    PRP,
    DT,
    IN,
    CC,
    MD,
    TO,
    RET,
    CODE,
    LIT,
    IF,
    FOR,
    ARITH,
    SHIFT,
    DOT,
    COMMA,
    EXCL,
    STR,
    CHAR,
}

impl From<TerminalSymbol> for Symbol {
    fn from(t: TerminalSymbol) -> Symbol {
        match t {
            TerminalSymbol::NN => Symbol::NN,
            TerminalSymbol::NNS => Symbol::NNS,
            TerminalSymbol::NNP => Symbol::NNP,
            TerminalSymbol::NNPS => Symbol::NNPS,
            TerminalSymbol::VB => Symbol::VB,
            TerminalSymbol::VBP => Symbol::VBP,
            TerminalSymbol::VBZ => Symbol::VBZ,
            TerminalSymbol::VBN => Symbol::VBN,
            TerminalSymbol::VBG => Symbol::VBG,
            TerminalSymbol::VBD => Symbol::VBD,
            TerminalSymbol::JJ => Symbol::JJ,
            TerminalSymbol::JJR => Symbol::JJR,
            TerminalSymbol::JJS => Symbol::JJS,
            TerminalSymbol::RB => Symbol::RB,
            TerminalSymbol::PRP => Symbol::PRP,
            TerminalSymbol::DT => Symbol::DT,
            TerminalSymbol::IN => Symbol::IN,
            TerminalSymbol::CC => Symbol::CC,
            TerminalSymbol::MD => Symbol::MD,
            TerminalSymbol::TO => Symbol::TO,
            TerminalSymbol::RET => Symbol::RET,
            TerminalSymbol::CODE => Symbol::CODE,
            TerminalSymbol::LIT => Symbol::LIT,
            TerminalSymbol::IF => Symbol::IF,
            TerminalSymbol::FOR => Symbol::FOR,
            TerminalSymbol::ARITH => Symbol::ARITH,
            TerminalSymbol::SHIFT => Symbol::SHIFT,
            TerminalSymbol::DOT => Symbol::DOT,
            TerminalSymbol::COMMA => Symbol::COMMA,
            TerminalSymbol::EXCL => Symbol::EXCL,
            TerminalSymbol::STR => Symbol::STR,
            TerminalSymbol::CHAR => Symbol::CHAR,
        }
    }
}

impl<S: AsRef<str>> From<S> for Symbol {
    fn from(nt: S) -> Self {
        if let Ok(termsym) = TerminalSymbol::from_terminal(&nt) {
            return termsym.into();
        }
        
        match nt.as_ref() {
            "S" => Symbol::S,
            "MNN" => Symbol::MNN,
            "TJJ" => Symbol::TJJ,
            "MJJ" => Symbol::MJJ,
            "MVB" => Symbol::MVB,
            "IFF" => Symbol::IFF,
            "EQTO" => Symbol::EQTO,
            "BITOP" => Symbol::BITOP,
            "ARITHOP" => Symbol::ARITHOP,
            "SHIFTOP" => Symbol::SHIFTOP,
            "OP" => Symbol::OP,
            "OBJ" => Symbol::OBJ,
            "REL" => Symbol::REL,
            "MREL" => Symbol::MREL,
            "PROP" => Symbol::PROP,
            "PROP_OF" => Symbol::PROP_OF,
            "RSEP" => Symbol::RSEP,
            "RANGE" => Symbol::RANGE,
            "RANGEMOD" => Symbol::RANGEMOD,
            "ASSERT" => Symbol::ASSERT,
            "HASSERT" => Symbol::HASSERT,
            "QUANT" => Symbol::QUANT,
            "QUANT_EXPR" => Symbol::QUANT_EXPR,
            "QASSERT" => Symbol::QASSERT,
            "MRET" => Symbol::MRET,
            "BOOL_EXPR" => Symbol::BOOL_EXPR,
            "COND" => Symbol::COND,
            "RETIF" => Symbol::RETIF,
            "SIDE" => Symbol::SIDE,
            "ASSIGN" => Symbol::ASSIGN,
            "EVENT" => Symbol::EVENT,
            "OBJV" => Symbol::OBJV,
            x => panic!("Unexpected symbol {}", x),
        }
    }
}
#[derive(Clone, Debug)]
pub enum SymbolTree {
    Terminal(Terminal),
    Branch(Symbol, Vec<SymbolTree>),
}

impl SymbolTree {
    pub(crate) fn from_iter<I: Iterator<Item=Terminal>, S: Eq + Clone + Hash + PartialEq + Into<Symbol>>(tree: TreeWrapper<S>, iter: &mut I) -> Self {
        match tree.inner {
            TreeNode::Terminal(_) => SymbolTree::Terminal(iter.next().unwrap()),
            TreeNode::Branch(nt, rest) => {
                let mut sym_trees = Vec::with_capacity(rest.len());
                for item in rest {
                    sym_trees.push(SymbolTree::from_iter(item, iter));
                }
                SymbolTree::Branch(
                    nt.symbol.into(),
                    sym_trees
                )
            }
        }
    }
}

impl SymbolTree {
    pub fn unwrap_terminal(self) -> Terminal {
        match self {
            SymbolTree::Terminal(t) => t,
            SymbolTree::Branch(_, _) => panic!("Called unwrap_terminal with non-terminal Tree"),
        }
    }

    pub fn unwrap_branch(self) -> (Symbol, Vec<SymbolTree>) {
        match self {
            SymbolTree::Terminal(_) => panic!("Called unwrap_branch with terminal Tree"),
            SymbolTree::Branch(sym, trees) => (sym, trees),
        }
    }
}

impl ParseSymbol for Symbol {
    type Error = ();

    fn parse_terminal(s: &str) -> Result<Self, Self::Error> {
        Ok(Self::from(s))
    }

    fn parse_nonterminal(s: &str) -> Result<Self, Self::Error> {
        Ok(Self::from(s))
    }
}