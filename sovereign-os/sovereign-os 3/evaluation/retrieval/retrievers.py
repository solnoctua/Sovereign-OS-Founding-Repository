"""Relevance functions compared by Benchmark 0003. Evaluation only: the application never imports this.

A retriever here only *scores text*. Everything else stays production code: candidate selection
(`Vault.context_candidates`: one read snapshot, the per-kind cutoff, provenance-linked claims) and every
policy decision (`context.build_bundle`: authority, sensitivity, disclosure, duplicates, budget). So an
experiment can change which candidates surface and in what order, and nothing else:
retrieval ≠ authority ≠ disclosure ≠ inference.

Each retriever is built once over a read-only snapshot of the evaluation vault (`documents`) and gives,
per question, a `score(text) -> (score, matched_terms)` exactly like `context.scorer`. The derived
indexes are in-memory SQLite databases that are discarded with the retriever; nothing is written to
the vault.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
import sqlite3
from typing import Callable

from sovereign.context import STOPWORDS, scorer as production_scorer, terms_of

Score = Callable[[str], tuple[float, tuple[str, ...]]]
_WORD = re.compile(r"\w+")    # the production word pattern (context._WORD)
PORTER = "porter unicode61"
UNICODE = "unicode61"


@dataclass(frozen=True)
class Document:
    id: str
    kind: str                       # "source" | "claim"
    text: str
    created_at: str
    links: tuple[str, ...]          # source: the record it corrects, if any; claim: the records it cites


def documents(snapshot: dict) -> list[Document]:
    """Every record (active or superseded) and claim of a `Vault.export()` snapshot."""
    docs = [Document(r["id"], "source", r["content"], r["created_at"], (r["supersedes_id"],) if r["supersedes_id"] else ())
            for r in snapshot["records"]]
    docs += [Document(c["id"], "claim", c["text"], c["created_at"], tuple(c["source_ids"])) for c in snapshot["claims"]]
    return sorted(docs, key=lambda d: d.id)


def neighbours(docs: list[Document]) -> dict[str, frozenset[str]]:
    """One hop along links storage already holds: claim → cited record, record → citing claim, and a
    record's correction ↔ the record it corrects. No inference, no new store (ADR-0005 §8.1's
    `SUPPORTED_BY` and `CORRECTS`; claim supersession is not used)."""
    found: dict[str, set[str]] = {d.id: set() for d in docs}
    for d in docs:
        for other in d.links:
            if other in found:
                found[d.id].add(other)
                found[other].add(d.id)
    return {k: frozenset(v) for k, v in found.items()}


def query_words(question: str) -> list[str]:
    """The production query filter, before any stemming: lower-case words of two or more characters that are not stopwords."""
    return sorted({w for w in _WORD.findall(question.lower()) if len(w) >= 2 and w not in STOPWORDS})


def tokenize(texts: list[str], tokenizer: str) -> list[frozenset[str]]:
    """The set of terms SQLite FTS5's `tokenizer` produces for each text (fts5vocab 'instance')."""
    db = sqlite3.connect(":memory:")
    try:
        db.execute(f"CREATE VIRTUAL TABLE ft USING fts5(body, tokenize='{tokenizer}')")
        db.execute("CREATE VIRTUAL TABLE vocab USING fts5vocab(ft, 'instance')")
        db.executemany("INSERT INTO ft(rowid, body) VALUES (?, ?)", list(enumerate(texts, 1)))
        terms: list[set[str]] = [set() for _ in texts]
        for term, doc in db.execute("SELECT term, doc FROM vocab"):
            terms[doc - 1].add(term)
        return [frozenset(t) for t in terms]
    finally:
        db.close()


class Aliases:
    """A fixed alias map (aliases.json): each group is rewritten to its first member, keeping a regular inflection."""

    def __init__(self, groups: list[list[str]]):
        members = sorted(((m, g[0]) for g in groups for m in g), key=lambda p: (-len(p[0]), p[0]))
        self._pattern = re.compile(r"\b(" + "|".join(re.escape(m) for m, _ in members) + r")(s|es|ed|ing)?\b")
        self._canonical = dict(members)

    def __call__(self, text: str) -> str:
        return self._pattern.sub(lambda m: self._canonical[m.group(1)] + (m.group(2) or ""), text.lower())


def _identity(text: str) -> str:
    return text


def _rounded(value: float) -> float:
    return round(value, 6)   # stable ordering across platforms; scores only rank


class Retriever:
    name: str
    description: str
    production = False

    def scorer(self, question: str) -> Score:
        raise NotImplementedError


class Baseline(Retriever):
    """The merged Context Compiler V0 retrieval, unchanged: `context.scorer`."""
    name = "baseline"
    description = ("Merged V0: distinct question terms matched (lower-case \\w+ words, English stopwords, one "
                   "plural 's' trimmed); ties newest first. Evaluated through `compile_context` itself.")
    production = True

    def scorer(self, question: str) -> Score:
        return production_scorer(question)


class TermMatch(Retriever):
    """Distinct-term matching over Porter-stemmed FTS5 tokens, counted or IDF-weighted."""

    def __init__(self, name: str, description: str, docs: list[Document], weighting: str,
                 rewrite: Callable[[str], str] = _identity):
        self.name, self.description, self._weighting, self._rewrite = name, description, weighting, rewrite
        terms = tokenize([rewrite(d.text) for d in docs], PORTER)
        self._terms = {d.text: t for d, t in zip(docs, terms)}
        frequency: dict[str, int] = {}
        for t in terms:
            for term in t:
                frequency[term] = frequency.get(term, 0) + 1
        n = len(docs)
        # BM25's IDF, always positive: rare terms count for more than common ones.
        self._idf = {term: math.log(1 + (n - df + 0.5) / (df + 0.5)) for term, df in frequency.items()}

    def scorer(self, question: str) -> Score:
        words = query_words(self._rewrite(question))
        wanted = tokenize([" ".join(words)], PORTER)[0] if words else frozenset()

        def score(text: str) -> tuple[float, tuple[str, ...]]:
            matched = tuple(sorted(wanted & self._terms[text]))
            if self._weighting == "count":
                return len(matched), matched
            return _rounded(sum(self._idf[t] for t in matched)), matched
        return score


class ExactStem(Retriever):
    """Exact matches first, Porter-stem matches second (evaluation candidate, not a proposal).

    The question's terms are the production ones (`context.terms_of`). For a text, each distinct term
    counts once: as an **exact** match if the text's production terms contain it (so the exact count is
    precisely the baseline score), otherwise as a **stem** match if the Porter stem of a question word
    that produced the term is among the Porter stems of the text. The score is the pair (exact, stem)
    in lexicographic order, encoded as `exact + stem / (terms + 1)`: any extra exact match outranks every
    stem match, stems only break ties between equal exact counts or rescue texts with no exact match,
    and ties keep the production order (newest first, then id). The score depends on the question and
    the text alone, never on other documents, so an unrelated write cannot change it.

    With `admit_stem_only=False` stems only order texts that already match exactly: the set of relevant
    texts (and so the relevance gate) is exactly the baseline's.
    """

    def __init__(self, name: str, description: str, docs: list[Document], admit_stem_only: bool = True):
        self.name, self.description, self._admit = name, description, admit_stem_only
        texts = [d.text for d in docs]
        self._exact = {t: frozenset(terms_of(t)) for t in texts}
        self._stems = dict(zip(texts, tokenize(texts, PORTER)))

    def scorer(self, question: str) -> Score:
        wanted = terms_of(question)
        words = query_words(question)
        stems: dict[str, set[str]] = {t: set() for t in wanted}
        for word, stemmed in zip(words, tokenize(words, PORTER) if words else []):
            for t in terms_of(word):
                stems[t] |= stemmed
        tiers = len(wanted) + 1

        def score(text: str) -> tuple[float, tuple[str, ...]]:
            exact = [t for t in wanted if t in self._exact[text]]
            stem = [t for t in wanted if t not in self._exact[text] and stems[t] & self._stems[text]]
            if not exact and not self._admit:
                return 0, ()
            return _rounded(len(exact) + len(stem) / tiers), tuple(exact) + tuple(f"~{t}" for t in stem)
        return score


class BM25(Retriever):
    """SQLite FTS5 full-text search ranked by its built-in bm25() over every record and claim text."""

    def __init__(self, name: str, description: str, docs: list[Document], tokenizer: str,
                 rewrite: Callable[[str], str] = _identity):
        self.name, self.description, self._rewrite = name, description, rewrite
        self._texts = [d.text for d in docs]
        self._db = sqlite3.connect(":memory:")
        self._db.execute(f"CREATE VIRTUAL TABLE ft USING fts5(body, tokenize='{tokenizer}')")
        self._db.executemany("INSERT INTO ft(rowid, body) VALUES (?, ?)",
                             [(i, rewrite(t)) for i, t in enumerate(self._texts, 1)])

    def scorer(self, question: str) -> Score:
        words = query_words(self._rewrite(question))
        found: dict[str, float] = {}
        if words:
            query = " OR ".join(f'"{w}"' for w in words)   # \w+ words: nothing to escape
            for rowid, rank in self._db.execute("SELECT rowid, bm25(ft) FROM ft WHERE ft MATCH ?", (query,)):
                found[self._texts[rowid - 1]] = _rounded(-rank)   # bm25() is lower-is-better

        def score(text: str) -> tuple[float, tuple[str, ...]]:
            return found.get(text, 0.0), ()
        return score


class Provenance(Retriever):
    """Diagnostic, not a proposal: one hop of relevance along links storage already holds.

    A document with no direct match inherits half the best direct score among its neighbours: the
    records a claim cites and the claims citing a record, and a record's correction and the record it
    corrects. This changes only relevance; authority, sensitivity and disclosure are still decided by
    the compiler. It measures what a graph-like signal would add (ADR-0004 founder decision 3 makes
    provenance-only claims `not_relevant`, so adopting it would change that decision).
    """

    def __init__(self, name: str, description: str, inner: Retriever, docs: list[Document]):
        self.name, self.description, self._inner, self._docs = name, description, inner, docs
        self._neighbours = neighbours(docs)

    def scorer(self, question: str) -> Score:
        direct = self._inner.scorer(question)
        own = {d.id: direct(d.text) for d in self._docs}
        found: dict[str, tuple[float, tuple[str, ...]]] = {}
        for d in self._docs:
            points, terms = own[d.id]
            if not points:
                inherited = max((own[n][0] for n in self._neighbours[d.id]), default=0)
                points, terms = _rounded(inherited / 2), ()
            found[d.text] = (points, terms)

        def score(text: str) -> tuple[float, tuple[str, ...]]:
            return found[text]
        return score


def build(docs: list[Document], aliases: Aliases) -> list[Retriever]:
    """The fixed experiment ladder, in report order."""
    best = BM25("fts5_porter_bm25", "SQLite FTS5 (Porter stemming) ranked by bm25().", docs, PORTER)
    exact_stem = ExactStem("exact_stem", "Exact production-term matches first; Porter-stem matches only as a "
                           "secondary signal (ties and texts with no exact match).", docs)
    return [
        Baseline(),
        TermMatch("porter_count", "Baseline scoring (distinct terms matched) over Porter-stemmed tokens: normalisation only.",
                  docs, "count"),
        TermMatch("porter_idf", "Porter-stemmed terms, each match weighted by its IDF: normalisation + term weighting.",
                  docs, "idf"),
        BM25("fts5_bm25", "SQLite FTS5 (unicode61, no stemming) ranked by bm25(): weighting and length normalisation only.",
             docs, UNICODE),
        best,
        BM25("fts5_porter_bm25_aliases", "fts5_porter_bm25 with the fixed alias map applied to questions and texts.",
             docs, PORTER, aliases),
        Provenance("fts5_porter_bm25_provenance", "Diagnostic: fts5_porter_bm25 plus one hop of relevance along "
                   "citation and correction links.", best, docs),
        exact_stem,
        ExactStem("exact_stem_tiebreak", "exact_stem without admission: stems only order texts that already match "
                  "exactly, so the relevance gate stays the baseline's.", docs, admit_stem_only=False),
        Provenance("baseline_provenance", "Counterfactual context admission: the merged baseline plus one hop of "
                   "relevance along citation and correction links.", Baseline(), docs),
        Provenance("exact_stem_provenance", "Counterfactual: exact_stem plus one hop of relevance along citation and "
                   "correction links.", exact_stem, docs),
    ]
