import { useState, useEffect } from "react";
import { CheckCircle, XCircle, RefreshCw } from "lucide-react";

export default function HealthStatus() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastChecked, setLastChecked] = useState(null);

  async function check() {
    setLoading(true);
    try {
      const r = await fetch("/api/health");
      const data = await r.json();
      setStatus(data);
    } catch {
      setStatus({
        status: "degraded",
        mongo: "unreachable",
        elasticsearch: "unreachable",
        redis: "unreachable",
      });
    }
    setLastChecked(new Date());
    setLoading(false);
  }

  useEffect(() => {
    check();
  }, []);

  const services = [
    { key: "mongo", label: "MongoDB" },
    { key: "elasticsearch", label: "Elasticsearch" },
    { key: "redis", label: "Redis" },
  ];

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">System Health</h2>
        <button
          onClick={check}
          className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
      </div>

      {status && (
        <>
          {/* Overall badge */}
          <div
            className={`inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium ${status.status === "healthy" ? "bg-emerald-100 dark:bg-emerald-900 text-emerald-700 dark:text-emerald-300" : "bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-300"}`}
          >
            {status.status === "healthy" ? <CheckCircle size={16} /> : <XCircle size={16} />}
            {status.status === "healthy"
              ? "All systems operational"
              : "One or more services degraded"}
          </div>

          {/* Service cards */}
          <div className="grid gap-4 sm:grid-cols-3">
            {services.map(({ key, label }) => {
              const ok = status[key] === "ok";
              return (
                <div
                  key={key}
                  className="bg-white dark:bg-gray-800 rounded-xl p-5 border border-gray-200 dark:border-gray-700 shadow-sm"
                >
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-medium text-sm">{label}</span>
                    {ok ? (
                      <CheckCircle size={18} className="text-emerald-500" />
                    ) : (
                      <XCircle size={18} className="text-red-500" />
                    )}
                  </div>
                  <p className={`text-xs ${ok ? "text-emerald-500" : "text-red-400"}`}>
                    {status[key]}
                  </p>
                </div>
              );
            })}
          </div>

          {lastChecked && (
            <p className="text-xs text-gray-400">
              Last checked: {lastChecked.toLocaleTimeString()}
            </p>
          )}
        </>
      )}
    </div>
  );
}
