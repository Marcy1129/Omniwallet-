# OmniWallet – FULL (Auto-import assets + Send/Receive)
# Runs locally (Android Termux/Pydroid, macOS, Windows, Linux)
# Keys are stored ONLY on your device in omniwallet_key.json

import os, json, time
from dataclasses import dataclass
from typing import Optional, Dict, Any
from flask import Flask, request, jsonify, send_from_directory, render_template
from eth_account import Account
from web3 import Web3
import requests

app = Flask(__name__, static_folder="static", template_folder="templates")

# ---- Config (set via environment or defaults) ----
DEFAULT_ADDRESS = os.getenv("DEFAULT_ADDRESS", "0x1985EA6E9c68E1C272d8209f3B478AC2Fdb25c87")
COVALENT_KEY = os.getenv("COVALENT_KEY", "YOUR_COVALENT_KEY")
ETH_RPC = os.getenv("ETH_RPC", "https://mainnet.infura.io/v3/YOUR_INFURA_ID")
BASE_RPC = os.getenv("BASE_RPC", "https://mainnet.base.org")

KEY_FILENAME_ANDROID = "/storage/emulated/0/Download/omniwallet_key.json"
KEY_FILENAME_LOCAL = "./omniwallet_key.json"

def load_local_wallet() -> Optional[Dict[str, str]]:
    """Load a locally-stored keyfile; if none exists, return None."""
    path = KEY_FILENAME_ANDROID if os.path.exists(KEY_FILENAME_ANDROID) else KEY_FILENAME_LOCAL
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
                # Expecting {"address": "0x...", "private_key": "0x..."}
                if "address" in data and "private_key" in data:
                    return data
        except Exception:
            return None
    return None

def create_wallet_if_missing() -> Dict[str, str]:
    """Create a fresh wallet ONLY if no keyfile exists. Saves locally."""
    existing = load_local_wallet()
    if existing:
        return existing
    acct = Account.create()
    keyfile = {"address": acct.address, "private_key": acct.key.hex()}
    path = KEY_FILENAME_ANDROID if os.path.exists(os.path.dirname(KEY_FILENAME_ANDROID)) else KEY_FILENAME_LOCAL
    with open(path, "w") as f:
        json.dump(keyfile, f)
    return keyfile

def active_address() -> str:
    """Prefer local keyfile address; otherwise default address (user's main)."""
    w = load_local_wallet()
    if w and "address" in w:
        return w["address"]
    return DEFAULT_ADDRESS

def w3_for_chain(chain: str) -> Web3:
    if chain.lower() == "base":
        return Web3(Web3.HTTPProvider(BASE_RPC))
    return Web3(Web3.HTTPProvider(ETH_RPC))

def covalent_balances(address: str, chain: str = "eth-mainnet") -> Dict[str, Any]:
    """Fetch balances via Covalent (requires COVALENT_KEY)."""
    if COVALENT_KEY == "YOUR_COVALENT_KEY":
        # Placeholder response to avoid accidental rate-limit; instruct user to set key.
        return {"error": "Missing Covalent API key. Set COVALENT_KEY env var.", "items": []}
    # Map short names to Covalent chain IDs
    chain_map = {
        "eth": "eth-mainnet",
        "ethereum": "eth-mainnet",
        "base": "base-mainnet"
    }
    chain_id = chain_map.get(chain.lower(), chain)
    url = f"https://api.covalenthq.com/v1/{chain_id}/address/{address}/balances_v2/?key={COVALENT_KEY}"
    r = requests.get(url, timeout=30)
    return r.json()

@app.route("/")
def home():
    return render_template("index.html")

@app.get("/api/address")
def api_address():
    return jsonify({"address": active_address()})

@app.get("/api/portfolio")
def api_portfolio():
    address = request.args.get("address") or active_address()
    chain = request.args.get("chain", "eth")
    data = covalent_balances(address, chain)
    return jsonify(data)

@app.post("/api/send")
def api_send():
    """Send native ETH/Base. Body: {chain, to, amount_eth, gas_price_gwei?}"""
    body = request.json or {}
    chain = (body.get("chain") or "eth").lower()
    to = body.get("to")
    amount_eth = body.get("amount_eth")
    if not to or not amount_eth:
        return jsonify({"error": "Missing 'to' or 'amount_eth'."}), 400

    keyfile = load_local_wallet()
    if not keyfile:
        return jsonify({"error": "No local key found. Generate/import first."}), 400

    w3 = w3_for_chain(chain)
    acct = w3.eth.account.from_key(keyfile["private_key"])

    try:
        nonce = w3.eth.get_transaction_count(acct.address)
        gas_price = body.get("gas_price_gwei")
        if gas_price is None:
            gas_price = w3.eth.gas_price / (10**9)
        gas_price_wei = int(float(gas_price) * (10**9))

        tx = {
            "to": Web3.to_checksum_address(to),
            "value": int(float(amount_eth) * (10**18)),
            "nonce": nonce,
            "gas": 21000,
            "gasPrice": gas_price_wei,
            "chainId": w3.eth.chain_id
        }
        signed = w3.eth.account.sign_transaction(tx, private_key=keyfile["private_key"])
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        return jsonify({"tx_hash": tx_hash.hex()})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == "__main__":
    # Ensure a wallet exists locally so balances + send work out-of-the-box
    create_wallet_if_missing()
    app.run(host="0.0.0.0", port=5000, debug=False)
