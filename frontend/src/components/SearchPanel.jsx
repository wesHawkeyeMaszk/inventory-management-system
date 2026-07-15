import { useState, useEffect, useRef } from "react";
import { Search, SlidersHorizontal } from "lucide-react";
import { searchProducts, suggestProducts } from "../api";

export default function SearchPanel() {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState({ category: "", min_price: "", max_price: "" });
  const suggestTimer = useRef(null);

  // Debounced autocomplete
  useEffect(() => {
    if (suggestTimer.current) clearTimeout(suggestTimer.current);
    if (query.length < 2) {
      setSuggestions([]);
      return;
    }
    suggestTimer.current = setTimeout(async () => {
      const s = await suggestProducts(query);
      setSuggestions(s);
    }, 250);
  }, [query]);

  async function handleSearch(e) {
    e.preventDefault();
    if (!query.trim()) return;
    setSuggestions([]);
    setLoading(true);
    const activeFilters = Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== ""));
    const data = await searchProducts(query, activeFilters);
    setResults(data);
    setLoading(false);
  }

  function pickSuggestion(name) {
    setQuery(name);
    setSuggestions([]);
  }

  return (
    <div className="space-y-5">
      <h2 className="text-lg font-semibold">Full-Text Search</h2>

      <form onSubmit={handleSearch} className="space-y-3">
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search products by name or description…"
            className="w-full pl-9 pr-4 py-2.5 border border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-800 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          {/* Suggestions dropdown */}
          {suggestions.length > 0 && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-lg z-10 overflow-hidden">
              {suggestions.map((s) => (
                <button
                  key={s.product_id}
                  type="button"
                  onClick={() => pickSuggestion(s.product_name)}
                  className="w-full text-left px-4 py-2.5 text-sm hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center justify-between"
                >
                  <span>{s.product_name}</span>
                  <span className="text-xs text-gray-400">{s.product_category}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Filters toggle */}
        <div className="flex items-center gap-3">
          <button
            type="submit"
            className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-5 py-2 rounded-lg transition-colors"
          >
            Search
          </button>
          <button
            type="button"
            onClick={() => setShowFilters((s) => !s)}
            className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
          >
            <SlidersHorizontal size={14} /> Filters
          </button>
        </div>

        {showFilters && (
          <div className="grid grid-cols-3 gap-3 bg-gray-50 dark:bg-gray-800 p-4 rounded-xl border border-gray-200 dark:border-gray-700">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Category</label>
              <input
                value={filters.category}
                onChange={(e) => setFilters((f) => ({ ...f, category: e.target.value }))}
                placeholder="e.g. Electronics"
                className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm bg-white dark:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Min Price</label>
              <input
                type="number"
                value={filters.min_price}
                onChange={(e) => setFilters((f) => ({ ...f, min_price: e.target.value }))}
                placeholder="0"
                className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm bg-white dark:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Max Price</label>
              <input
                type="number"
                value={filters.max_price}
                onChange={(e) => setFilters((f) => ({ ...f, max_price: e.target.value }))}
                placeholder="9999"
                className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm bg-white dark:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>
        )}
      </form>

      {/* Results */}
      {loading && <p className="text-gray-400 text-sm">Searching…</p>}

      {results && !loading && (
        <div className="space-y-3">
          <p className="text-sm text-gray-500">
            {results.total} result{results.total !== 1 ? "s" : ""} for{" "}
            <strong>&quot;{query}&quot;</strong>
          </p>
          {results.products.length === 0 ? (
            <p className="text-gray-400 text-sm">No products found.</p>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {results.products.map((p) => (
                <div
                  key={p.product_id}
                  className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700 shadow-sm"
                >
                  <div className="flex items-start justify-between mb-2">
                    <span className="font-medium text-sm">{p.product_name}</span>
                    <span className="bg-indigo-100 dark:bg-indigo-900 text-indigo-700 dark:text-indigo-300 text-xs px-2 py-0.5 rounded-full">
                      {p.product_category}
                    </span>
                  </div>
                  <p className="text-gray-500 dark:text-gray-400 text-xs mb-3 line-clamp-2">
                    {p.description}
                  </p>
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-bold text-indigo-600 dark:text-indigo-400">
                      ${p.price.toFixed(2)}
                    </span>
                    <span className="text-gray-400">{p.available_quantity} in stock</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
