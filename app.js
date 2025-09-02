async function getJSON(url) {
  const r = await fetch(url);
  return r.json();
}

async function postJSON(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body || {})
  });
  return r.json();
}

function renderBalances(el, data) {
  if (data.error) {
    el.innerHTML = `<div class="error">${data.error}</div>`;
    return;
  }
  const items = (data.data && data.data.items) || data.items || [];
  if (!items.length) {
    el.innerHTML = "<em>No assets found.</em>";
    return;
  }
  const rows = items.map(it => {
    const ticker = it.contract_ticker_symbol || it.contract_name || "N/A";
    const balRaw = it.balance || 0;
    const decimals = it.contract_decimals || 18;
    const bal = (Number(balRaw) / (10 ** decimals));
    const price = (it.quote_rate || 0);
    const value = price ? (bal * price).toFixed(2) : "-";
    return `<div class="asset-row"><span>${ticker}</span><span>${bal.toFixed(6)}</span><span>${value === "-" ? "-" : "$"+value}</span></div>`;
  }).join("");
  el.innerHTML = `<div class="asset-head"><span>Token</span><span>Balance</span><span>Value</span></div>${rows}`;
}

async function refresh() {
  const addr = await getJSON("/api/address");
  document.getElementById("address").textContent = addr.address;
  const eth = await getJSON(`/api/portfolio?chain=eth&address=${addr.address}`);
  const base = await getJSON(`/api/portfolio?chain=base&address=${addr.address}`);
  renderBalances(document.getElementById("eth-balances"), eth);
  renderBalances(document.getElementById("base-balances"), base);
}

document.getElementById("refresh").addEventListener("click", refresh);

document.getElementById("send-btn").addEventListener("click", async () => {
  const chain = document.getElementById("send-chain").value;
  const to = document.getElementById("send-to").value.trim();
  const amount = document.getElementById("send-amount").value.trim();
  const status = document.getElementById("send-status");
  status.textContent = "Sending…";
  const res = await postJSON("/api/send", { chain, to, amount_eth: amount });
  if (res.tx_hash) {
    status.innerHTML = `✅ Sent! Tx: <a href="#" target="_blank">${res.tx_hash}</a>`;
  } else {
    status.textContent = `❌ ${res.error || "Error"}`;
  }
});

// Auto-load on start
refresh();
