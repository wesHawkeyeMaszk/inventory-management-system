import { useState, useEffect } from "react";
import { Package, BarChart2, Search, Moon, Sun, Activity, Coins } from "lucide-react";
import InventoryTable from "./components/InventoryTable";
import AnalyticsDashboard from "./components/AnalyticsDashboard";
import SearchPanel from "./components/SearchPanel";
import HealthStatus from "./components/HealthStatus";
import NoProfitGame from "./components/NoProfitGame";

const TABS = [
  { id: "inventory", label: "Inventory", icon: Package },
  { id: "analytics", label: "Analytics", icon: BarChart2 },
  { id: "search", label: "Search", icon: Search },
  { id: "game", label: "No Profit", icon: Coins },
  { id: "health", label: "System", icon: Activity },
];

export default function App() {
  const [tab, setTab] = useState("inventory");
  const [dark, setDark] = useState(() => localStorage.getItem("theme") === "dark");

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 transition-colors">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Package className="text-indigo-600 dark:text-indigo-400" size={28} />
            <span className="text-xl font-bold tracking-tight">Inventory Manager</span>
          </div>
          <button
            onClick={() => setDark((d) => !d)}
            className="p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            title="Toggle dark mode"
          >
            {dark ? <Sun size={20} /> : <Moon size={20} />}
          </button>
        </div>

        {/* Tab bar */}
        <nav className="max-w-7xl mx-auto px-4 flex gap-1 pb-0">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                tab === id
                  ? "border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400"
                  : "border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
              }`}
            >
              <Icon size={15} />
              {label}
            </button>
          ))}
        </nav>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        {tab === "inventory" && <InventoryTable />}
        {tab === "analytics" && <AnalyticsDashboard />}
        {tab === "search" && <SearchPanel />}
        {tab === "game" && <NoProfitGame />}
        {tab === "health" && <HealthStatus />}
      </main>
    </div>
  );
}
