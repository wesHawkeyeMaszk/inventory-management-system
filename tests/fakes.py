"""In-memory test doubles for external services.

These aren't full reimplementations of Elasticsearch/Redis/Mongo - they
implement just enough of the client surface that app/services/*.py calls,
with query semantics that match closely enough for deterministic tests.
"""


class NotFoundError(Exception):
    pass


class _FakeIndices:
    def __init__(self, store):
        self._store = store

    def exists(self, index):
        return index in self._store

    def create(self, index, mappings=None):
        self._store.setdefault(index, {})

    def delete(self, index):
        self._store.pop(index, None)


class FakeElasticsearch:
    """Minimal in-memory stand-in for the elasticsearch-py client.

    Supports the query shapes es_service.py actually builds: multi_match,
    match_phrase_prefix, and a bool query with must/filter (term, range).
    """

    def __init__(self):
        self._docs = {}  # index -> {id: document}
        self.indices = _FakeIndices(self._docs)

    def index(self, index, id, document):
        self._docs.setdefault(index, {})[id] = dict(document)

    def delete(self, index, id):
        docs = self._docs.get(index, {})
        if id not in docs:
            raise NotFoundError(f"{id} not found in {index}")
        del docs[id]

    def search(self, index, query, source=None, size=10, from_=0):
        docs = list(self._docs.get(index, {}).values())
        matches = [d for d in docs if self._matches(d, query)]
        total = len(matches)
        page = matches[from_:from_ + size]
        hits = []
        for doc in page:
            src = doc if source is None else {k: doc.get(k) for k in source}
            hits.append({"_source": src})
        return {"hits": {"total": {"value": total}, "hits": hits}}

    def _matches(self, doc, query):
        if "match_phrase_prefix" in query:
            field, spec = next(iter(query["match_phrase_prefix"].items()))
            text = str(doc.get(field, "")).lower()
            return text.startswith(spec["query"].lower())

        if "bool" in query:
            must = query["bool"].get("must", [])
            filters = query["bool"].get("filter", [])
            if must and not all(self._matches(doc, clause) for clause in must):
                return False
            return all(self._matches_filter(doc, clause) for clause in filters)

        if "multi_match" in query:
            spec = query["multi_match"]
            needle = spec["query"].lower()
            return any(needle in str(doc.get(f, "")).lower() for f in spec["fields"])

        raise NotImplementedError(f"FakeElasticsearch cannot evaluate query: {query}")

    def _matches_filter(self, doc, clause):
        if "term" in clause:
            field, spec = next(iter(clause["term"].items()))
            value = spec["value"] if isinstance(spec, dict) else spec
            case_insensitive = isinstance(spec, dict) and spec.get("case_insensitive")
            actual = doc.get(field)
            if case_insensitive:
                return str(actual).lower() == str(value).lower()
            return actual == value

        if "range" in clause:
            field, bounds = next(iter(clause["range"].items()))
            actual = doc.get(field)
            if actual is None:
                return False
            if "gte" in bounds and actual < bounds["gte"]:
                return False
            if "lte" in bounds and actual > bounds["lte"]:
                return False
            return True

        raise NotImplementedError(f"FakeElasticsearch cannot evaluate filter: {clause}")
