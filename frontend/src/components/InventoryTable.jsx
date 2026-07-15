import { useState, useEffect, useCallback } from "react";
import {
  Plus,
  Pencil,
  Trash2,
  ChevronUp,
  ChevronDown,
  AlertTriangle,
  X,
  Check,
  History,
} from "lucide-react";
import { fetchProducts, createProduct, updateProduct, deleteProduct, fetchHistory } from "../api";

const EMPTY_FORM = {
  product_name: "",
  product_category: "",
  price: "",
  available_quantity: "",
  description: "",
};
const CATEGORIES = ["Electronics", "Clothing", "Books", "Food", "Tools", "Other"];

function StatTile({ label, value, sub }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm border border-gray-200 dark:border-gray-700">
      <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}

export default function InventoryTable() {
  const [data, setData] = useState({ products: [], total: 0, pages: 1 });
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState("product_name");
  const [order, setOrder] = useState("asc");
  const [modal, setModal] = useState(null); // null | 'create' | {product}
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [historyProduct, setHistoryProduct] = useState(null);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    fetchProducts(page, 20, sort, order)
      .then(setData)
      .catch(() => setError("Failed to load products"));
  }, [page, sort, order]);

  useEffect(() => {
    load();
  }, [load]);

  function toggleSort(field) {
    if (sort === field) setOrder((o) => (o === "asc" ? "desc" : "asc"));
    else {
      setSort(field);
      setOrder("asc");
    }
    setPage(1);
  }

  function SortIcon({ field }) {
    if (sort !== field) return null;
    return order === "asc" ? <ChevronUp size={13} /> : <ChevronDown size={13} />;
  }

  function openCreate() {
    setForm(EMPTY_FORM);
    setModal("create");
  }
  function openEdit(p) {
    setForm({ ...p });
    setModal(p);
  }

  async function openHistory(p) {
    const h = await fetchHistory(p.product_id);
    setHistory(h);
    setHistoryProduct(p);
  }

  async function handleSave() {
    setSaving(true);
    try {
      if (modal === "create") {
        await createProduct({
          ...form,
          price: parseFloat(form.price),
          available_quantity: parseInt(form.available_quantity),
        });
      } else {
        await updateProduct(modal.product_id, {
          ...form,
          price: parseFloat(form.price),
          available_quantity: parseInt(form.available_quantity),
        });
      }
      setModal(null);
      load();
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id) {
    if (!confirm("Delete this product?")) return;
    await deleteProduct(id);
    load();
  }

  const lowStockCount = data.products.filter((p) => p.available_quantity <= 10).length;

  return (
    <div className="space-y-5">
      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatTile label="Total Products" value={data.total} />
        <StatTile label="This Page" value={data.products.length} />
        <StatTile label="Low Stock" value={lowStockCount} sub="≤ 10 units" />
        <StatTile label="Page" value={`${page} / ${data.pages}`} />
      </div>

      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Products</h2>
        <button
          onClick={openCreate}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          <Plus size={15} /> Add Product
        </button>
      </div>

      {error && <p className="text-red-500 text-sm">{error}</p>}

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-800 text-gray-500 dark:text-gray-400 text-xs uppercase">
            <tr>
              {[
                ["product_name", "Name"],
                ["product_category", "Category"],
                ["price", "Price"],
                ["available_quantity", "Qty"],
              ].map(([field, label]) => (
                <th
                  key={field}
                  className="px-4 py-3 text-left cursor-pointer hover:text-gray-800 dark:hover:text-gray-200"
                  onClick={() => toggleSort(field)}
                >
                  <span className="flex items-center gap-1">
                    {label}
                    <SortIcon field={field} />
                  </span>
                </th>
              ))}
              <th className="px-4 py-3 text-left">Description</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
            {data.products.map((p) => (
              <tr
                key={p.product_id}
                className={`bg-white dark:bg-gray-900 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors ${p.available_quantity <= 10 ? "border-l-4 border-l-amber-400" : ""}`}
              >
                <td className="px-4 py-3 font-medium">
                  {p.product_name}
                  {p.available_quantity <= 10 && (
                    <span className="ml-2 inline-flex items-center gap-1 text-amber-500 text-xs">
                      <AlertTriangle size={11} />
                      Low
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <span className="bg-indigo-100 dark:bg-indigo-900 text-indigo-700 dark:text-indigo-300 text-xs px-2 py-0.5 rounded-full">
                    {p.product_category}
                  </span>
                </td>
                <td className="px-4 py-3 font-mono">${p.price.toFixed(2)}</td>
                <td className="px-4 py-3">{p.available_quantity}</td>
                <td className="px-4 py-3 text-gray-400 truncate max-w-xs">
                  {p.description?.slice(0, 60)}
                  {p.description?.length > 60 ? "…" : ""}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-end gap-2">
                    <button
                      onClick={() => openHistory(p)}
                      className="p-1.5 text-gray-400 hover:text-indigo-500 transition-colors"
                      title="History"
                    >
                      <History size={14} />
                    </button>
                    <button
                      onClick={() => openEdit(p)}
                      className="p-1.5 text-gray-400 hover:text-blue-500 transition-colors"
                      title="Edit"
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      onClick={() => handleDelete(p.product_id)}
                      className="p-1.5 text-gray-400 hover:text-red-500 transition-colors"
                      title="Delete"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between text-sm text-gray-500">
        <span>{data.total} total products</span>
        <div className="flex gap-2">
          <button
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            className="px-3 py-1 rounded border border-gray-200 dark:border-gray-700 disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            Prev
          </button>
          <button
            disabled={page >= data.pages}
            onClick={() => setPage((p) => p + 1)}
            className="px-3 py-1 rounded border border-gray-200 dark:border-gray-700 disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            Next
          </button>
        </div>
      </div>

      {/* Create/Edit Modal */}
      {modal !== null && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">
                {modal === "create" ? "Add Product" : "Edit Product"}
              </h3>
              <button onClick={() => setModal(null)}>
                <X size={18} />
              </button>
            </div>
            <div className="space-y-3">
              {[
                ["product_name", "Name", "text"],
                ["price", "Price", "number"],
                ["available_quantity", "Quantity", "number"],
              ].map(([key, label, type]) => (
                <div key={key}>
                  <label className="text-xs text-gray-500 mb-1 block">{label}</label>
                  <input
                    type={type}
                    value={form[key]}
                    onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                    className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              ))}
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Category</label>
                <select
                  value={form.product_category}
                  onChange={(e) => setForm((f) => ({ ...f, product_category: e.target.value }))}
                  className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">Select…</option>
                  {CATEGORIES.map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Description</label>
                <textarea
                  rows={3}
                  value={form.description}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                  className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button
                onClick={() => setModal(null)}
                className="px-4 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-4 py-2 text-sm rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white flex items-center gap-2 disabled:opacity-60"
              >
                <Check size={14} />
                {saving ? "Saving…" : "Save"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* History Modal */}
      {historyProduct && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">
                Change History — {historyProduct.product_name}
              </h3>
              <button onClick={() => setHistoryProduct(null)}>
                <X size={18} />
              </button>
            </div>
            {history.length === 0 ? (
              <p className="text-gray-400 text-sm">No changes recorded yet.</p>
            ) : (
              <div className="space-y-2 max-h-80 overflow-y-auto">
                {history.map((h, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between text-sm border-b border-gray-100 dark:border-gray-700 pb-2"
                  >
                    <div>
                      <span className="font-medium capitalize">{h.field}</span>
                      <span className="text-gray-400 mx-2">·</span>
                      <span className="line-through text-red-400">{h.old_value}</span>
                      <span className="mx-2">→</span>
                      <span className="text-green-500">{h.new_value}</span>
                    </div>
                    <span className="text-gray-400 text-xs">
                      {new Date(h.changed_at).toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
