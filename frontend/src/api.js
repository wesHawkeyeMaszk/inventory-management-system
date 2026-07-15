const BASE = "/api";

export async function fetchProducts(page = 1, limit = 20, sort = "product_name", order = "asc") {
  const r = await fetch(`${BASE}/products?page=${page}&limit=${limit}&sort=${sort}&order=${order}`);
  return r.json();
}

export async function fetchProduct(id) {
  const r = await fetch(`${BASE}/products/${id}`);
  return r.json();
}

export async function searchProducts(query, filters = {}) {
  const params = new URLSearchParams({ query, ...filters });
  const r = await fetch(`${BASE}/products/search?${params}`);
  return r.json();
}

export async function suggestProducts(q) {
  const r = await fetch(`${BASE}/products/suggest?q=${encodeURIComponent(q)}`);
  return r.json();
}

export async function fetchAnalytics() {
  const r = await fetch(`${BASE}/products/analytics`);
  return r.json();
}

export async function fetchHistory(id) {
  const r = await fetch(`${BASE}/products/${id}/history`);
  return r.json();
}

export async function createProduct(data) {
  const r = await fetch(`${BASE}/products`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return r.json();
}

export async function updateProduct(id, data) {
  const r = await fetch(`${BASE}/products/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return r.json();
}

export async function deleteProduct(id) {
  const r = await fetch(`${BASE}/products/${id}`, { method: "DELETE" });
  return r.json();
}

export async function startGameSession(data) {
  const r = await fetch(`${BASE}/game/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return r.json();
}

export async function getGameSession(sessionId) {
  const r = await fetch(`${BASE}/game/sessions/${sessionId}`);
  return r.json();
}

export async function submitGameGuess(sessionId, data) {
  const r = await fetch(`${BASE}/game/sessions/${sessionId}/guess`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return r.json();
}

export async function fetchLeaderboard(limit = 10) {
  const r = await fetch(`${BASE}/game/leaderboard?limit=${limit}`);
  return r.json();
}
