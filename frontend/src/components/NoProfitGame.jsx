import { useEffect, useState } from "react";
import {
  Coins,
  Trophy,
  Minus,
  Plus,
  RotateCcw,
  TrendingDown,
  TrendingUp,
  Flame,
} from "lucide-react";
import { startGameSession, submitGameGuess, fetchLeaderboard } from "../api";

const POOL_SIZE = 10;

const MODIFIER_STYLES = {
  sale: {
    card: "border-emerald-400 dark:border-emerald-500 ring-1 ring-emerald-300/60 dark:ring-emerald-600/40 bg-emerald-50/50 dark:bg-emerald-950/20",
    badge: "text-emerald-700 dark:text-emerald-400",
    icon: TrendingDown,
    label: "On sale",
  },
  increase: {
    card: "border-rose-400 dark:border-rose-500 ring-1 ring-rose-300/60 dark:ring-rose-600/40 bg-rose-50/50 dark:bg-rose-950/20",
    badge: "text-rose-700 dark:text-rose-400",
    icon: TrendingUp,
    label: "Price up",
  },
};

function QuantityStepper({ value, onChange }) {
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={() => onChange(Math.max(0, value - 1))}
        className="w-7 h-7 flex items-center justify-center rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700"
      >
        <Minus size={14} />
      </button>
      <input
        type="number"
        min="0"
        value={value}
        onChange={(e) => onChange(Math.max(0, parseInt(e.target.value, 10) || 0))}
        className="w-14 text-center border border-gray-300 dark:border-gray-600 rounded-lg py-1 text-sm bg-white dark:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
      />
      <button
        type="button"
        onClick={() => onChange(value + 1)}
        className="w-7 h-7 flex items-center justify-center rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700"
      >
        <Plus size={14} />
      </button>
    </div>
  );
}

function ItemCard({ item, value, onChange }) {
  const style = MODIFIER_STYLES[item.modifier];
  const Icon = style?.icon;
  return (
    <div
      className={`bg-white dark:bg-gray-800 rounded-xl p-4 border shadow-sm space-y-3 ${style?.card || "border-gray-200 dark:border-gray-700"}`}
    >
      <div>
        <div className="flex items-start justify-between mb-1 gap-2">
          <span className="font-medium text-sm">{item.product_name}</span>
          <span className="bg-indigo-100 dark:bg-indigo-900 text-indigo-700 dark:text-indigo-300 text-xs px-2 py-0.5 rounded-full whitespace-nowrap">
            {item.product_category}
          </span>
        </div>
        {item.description && (
          <p className="text-gray-500 dark:text-gray-400 text-xs line-clamp-2">
            {item.description}
          </p>
        )}
        {style && (
          <p className={`text-xs font-semibold flex items-center gap-1 mt-1.5 ${style.badge}`}>
            <Icon size={13} /> {style.label}
          </p>
        )}
      </div>
      <QuantityStepper value={value} onChange={onChange} />
    </div>
  );
}

function Leaderboard({ entries }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm border border-gray-200 dark:border-gray-700">
      <h3 className="text-sm font-semibold mb-4 text-gray-600 dark:text-gray-300 uppercase tracking-wide flex items-center gap-2">
        <Trophy size={15} /> Leaderboard
      </h3>
      {entries.length === 0 ? (
        <p className="text-gray-400 text-sm">No runs finished yet — be the first!</p>
      ) : (
        <ol className="space-y-2">
          {entries.map((e, i) => (
            <li key={e.session_id} className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-2">
                <span className="text-gray-400 w-4">{i + 1}.</span>
                <span className="font-medium">{e.player_name}</span>
              </span>
              <span className="text-gray-500 dark:text-gray-400">
                <strong className="text-gray-900 dark:text-gray-100">{e.rounds_survived}</strong>{" "}
                round{e.rounds_survived !== 1 ? "s" : ""}
                <span className="text-gray-400"> · {e.margin_pct}% margin</span>
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

export default function NoProfitGame() {
  const [phase, setPhase] = useState("landing"); // landing | playing | revealed
  const [playerName, setPlayerName] = useState("");
  const [session, setSession] = useState(null);
  const [round, setRound] = useState(null);
  const [nextRound, setNextRound] = useState(null);
  const [quantities, setQuantities] = useState({});
  const [leaderboard, setLeaderboard] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchLeaderboard(10).then(setLeaderboard);
  }, []);

  async function handleStart(e) {
    e?.preventDefault();
    setLoading(true);
    const data = await startGameSession({
      player_name: playerName || "Anonymous",
      pool_size: POOL_SIZE,
    });
    setSession(data.session);
    setRound(data.round);
    setNextRound(null);
    setQuantities({});
    setPhase("playing");
    setLoading(false);
  }

  async function handleSubmit() {
    setLoading(true);
    const guesses = Object.fromEntries(Object.entries(quantities).filter(([, qty]) => qty > 0));
    const data = await submitGameGuess(session.session_id, {
      player_name: playerName || undefined,
      guesses,
    });
    setSession(data.session);
    setRound(data.round);
    setNextRound(data.next_round);
    setPhase("revealed");
    setLoading(false);
    if (data.session.status === "lost") fetchLeaderboard(10).then(setLeaderboard);
  }

  function handleContinue() {
    setRound(nextRound);
    setNextRound(null);
    setQuantities({});
    setPhase("playing");
  }

  if (phase === "landing") {
    return (
      <div className="space-y-6">
        <div className="text-center space-y-2 max-w-lg mx-auto">
          <Coins className="mx-auto text-indigo-600 dark:text-indigo-400" size={36} />
          <h2 className="text-2xl font-bold">No Profit</h2>
          <p className="text-gray-500 dark:text-gray-400 text-sm">
            Each round we&rsquo;ll give you a budget and {POOL_SIZE} items with their prices hidden.
            Buy quantities to land as close to the budget as you can. Clear a round and you move on
            — but your margin for error shrinks every time, and some items will go on sale or spike
            in price. How many rounds can you survive?
          </p>
        </div>

        <form onSubmit={handleStart} className="max-w-sm mx-auto flex gap-2">
          <input
            value={playerName}
            onChange={(e) => setPlayerName(e.target.value)}
            placeholder="Your name"
            className="flex-1 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <button
            type="submit"
            disabled={loading}
            className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-5 py-2 rounded-lg transition-colors disabled:opacity-50"
          >
            {loading ? "Starting…" : "Start Run"}
          </button>
        </form>

        <div className="max-w-sm mx-auto">
          <Leaderboard entries={leaderboard} />
        </div>
      </div>
    );
  }

  if (phase === "playing") {
    return (
      <div className="space-y-5">
        <div className="bg-indigo-600 text-white rounded-xl p-5 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-wide text-indigo-200">
                Round {session.round_number}
              </p>
              <p className="text-3xl font-bold">${round.target.toFixed(2)}</p>
            </div>
            <div className="text-right">
              <p className="text-xs uppercase tracking-wide text-indigo-200 flex items-center gap-1 justify-end">
                <Flame size={12} /> Margin for error
              </p>
              <p className="text-2xl font-bold">{round.margin_pct}%</p>
            </div>
          </div>
          <p className="text-sm text-indigo-100">
            Prices are hidden. Pick quantities to land within {round.margin_pct}% of the budget.
            {round.round_number > 1 &&
              " Green-bordered items are on sale, red-bordered items just got pricier."}
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {round.pool.map((item) => (
            <ItemCard
              key={item.product_id}
              item={item}
              value={quantities[item.product_id] || 0}
              onChange={(v) => setQuantities((q) => ({ ...q, [item.product_id]: v }))}
            />
          ))}
        </div>

        <button
          onClick={handleSubmit}
          disabled={loading}
          className="w-full bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-5 py-3 rounded-xl transition-colors disabled:opacity-50"
        >
          {loading ? "Scoring…" : "Lock In Guess"}
        </button>
      </div>
    );
  }

  // phase === "revealed"
  const passed = round.passed;
  return (
    <div className="space-y-5">
      <div className="text-center space-y-1">
        <p
          className={`text-xl font-bold ${passed ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}`}
        >
          {passed ? `Round ${round.round_number} cleared!` : "Missed the margin — run over"}
        </p>
        <p className="text-gray-500 dark:text-gray-400 text-sm">
          Budget ${round.target.toFixed(2)} · You spent ${round.total_spent.toFixed(2)} · Off by{" "}
          <strong className="text-gray-900 dark:text-gray-100">{round.difference_pct}%</strong>{" "}
          (margin was {round.margin_pct}%)
        </p>
        <p className="text-gray-500 dark:text-gray-400 text-sm">
          Rounds survived:{" "}
          <strong className="text-gray-900 dark:text-gray-100">{session.rounds_survived}</strong>
        </p>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-900 text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wide">
            <tr>
              <th className="text-left px-4 py-2">Item</th>
              <th className="text-right px-4 py-2">Price</th>
              <th className="text-right px-4 py-2">Qty</th>
              <th className="text-right px-4 py-2">Subtotal</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
            {round.breakdown.map((row) => {
              const style = MODIFIER_STYLES[row.modifier];
              return (
                <tr key={row.product_id} className={row.quantity > 0 ? "" : "text-gray-400"}>
                  <td className="px-4 py-2">
                    {row.product_name}
                    {style && (
                      <span className={`ml-2 text-xs font-medium ${style.badge}`}>
                        {style.label}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-right">${row.price.toFixed(2)}</td>
                  <td className="px-4 py-2 text-right">{row.quantity}</td>
                  <td className="px-4 py-2 text-right">${row.subtotal.toFixed(2)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {passed ? (
        <button
          onClick={handleContinue}
          className="w-full bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-5 py-3 rounded-xl transition-colors"
        >
          Continue to Round {session.round_number}
        </button>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          <button
            onClick={handleStart}
            disabled={loading}
            className="flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-5 py-3 rounded-xl transition-colors disabled:opacity-50"
          >
            <RotateCcw size={15} /> Play Again
          </button>
          <Leaderboard entries={leaderboard} />
        </div>
      )}
    </div>
  );
}
