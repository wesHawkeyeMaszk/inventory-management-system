import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { TrendingUp, Package, DollarSign, AlertTriangle } from "lucide-react";
import { fetchAnalytics } from "../api";

const COLORS = ["#6366f1", "#8b5cf6", "#ec4899", "#f59e0b", "#10b981"];

function KpiCard({ icon: Icon, label, value, sub, color }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-200 dark:border-gray-700 flex items-start gap-4">
      <div className={`p-2.5 rounded-lg ${color}`}>
        <Icon size={20} className="text-white" />
      </div>
      <div>
        <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">{label}</p>
        <p className="text-2xl font-bold mt-0.5">{value}</p>
        {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

export default function AnalyticsDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAnalytics().then((d) => {
      setData(d);
      setLoading(false);
    });
  }, []);

  if (loading)
    return (
      <div className="flex items-center justify-center h-48 text-gray-400">Loading analytics…</div>
    );

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold">Analytics Overview</h2>

      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          icon={Package}
          label="Total Products"
          value={data.total_count}
          color="bg-indigo-500"
        />
        <KpiCard
          icon={DollarSign}
          label="Avg Price"
          value={`$${data.average_price}`}
          sub={`$${data.min_price} – $${data.max_price}`}
          color="bg-emerald-500"
        />
        <KpiCard
          icon={TrendingUp}
          label="Top Category"
          value={data.most_popular_category}
          color="bg-violet-500"
        />
        <KpiCard
          icon={AlertTriangle}
          label="Low Stock"
          value={data.low_stock_count}
          sub={`≤ ${data.low_stock_threshold} units`}
          color="bg-amber-500"
        />
      </div>

      {/* Category chart */}
      <div className="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-200 dark:border-gray-700">
        <h3 className="text-sm font-semibold mb-4 text-gray-600 dark:text-gray-300 uppercase tracking-wide">
          Products by Category
        </h3>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart
            data={data.category_breakdown}
            margin={{ top: 0, right: 10, left: -10, bottom: 0 }}
          >
            <XAxis dataKey="category" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} allowDecimals={false} />
            <Tooltip
              contentStyle={{
                backgroundColor: "var(--tw-prose-body)",
                borderRadius: "8px",
                border: "none",
                fontSize: "12px",
              }}
              formatter={(v) => [v, "Products"]}
            />
            <Bar dataKey="count" radius={[6, 6, 0, 0]}>
              {data.category_breakdown.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
