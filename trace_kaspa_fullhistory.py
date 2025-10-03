import requests
import time
import os
import json
import pandas as pd
from datetime import datetime, timezone

API_BASE = "https://api.kaspa.org"
DATA_DIR = "flow_data_fullhistory"
os.makedirs(DATA_DIR, exist_ok=True)

# wallet #2
ROOTS = ["kaspa:qpz2vgvlxhmyhmt22h538pjzmvvd52nuut80y5zulgpvyerlskvvwm7n4uk5a"]

def format_timestamp(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()

CUTOFF_DATE = datetime(2022, 1, 1)

def is_before_cutoff(timestamp):
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return dt < CUTOFF_DATE
    except Exception as e:
        print("Timestamp parsing failed:", timestamp)
        return False

def fetch_transactions(address, max_pages=100000):
    records = []
    before = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    foundcutoff = False
    
    for _ in range(max_pages):
        url = (
            f"{API_BASE}/addresses/{address}/full-transactions-page"
            f"?limit=500&before={before}&resolve_previous_outpoints=full&acceptance=accepted"
        )
        print(f"📦 Fetching before={before} for {address}")
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"❌ Error fetching transactions: {e}")
            break

        if not isinstance(data, list) or not data:
            print("✅ No more transactions.")
            break

        for tx in data:
            if not isinstance(tx, dict):
                print(f"⚠️ Skipping non-dict entry: {tx}")
                continue

            tx_id = tx.get("transaction_id", tx.get("txId", "UNKNOWN"))
            timestamp = format_timestamp(tx.get("block_time", 0))
            inputs = tx.get("inputs") or []
            # inputs = tx.get("inputs", [])
            # outputs = tx.get("outputs", [])
            outputs = tx.get("outputs") or []

            if is_before_cutoff(timestamp):
                print("Reached cutoff date at:", timestamp)
                foundcutoff = True
                break
            
            for inp in inputs:
                sender = inp.get("previous_outpoint_address", "UNKNOWN")
                for out in outputs:
                    recipient = out.get("script_public_key_address", "UNKNOWN")
                    amount_kas = int(out.get("amount", 0)) / 1e8
                    records.append({
                        "tx_id": tx_id,
                        "timestamp": timestamp,
                        "sender": sender,
                        "recipient": recipient,
                        "amount_kas": amount_kas
                    })

        if foundcutoff: break
        
        before = data[-1].get("block_time", before)

    return pd.DataFrame(records)

def fetch_transactions_all_participants(address, max_pages=100000):
    """
    Fetch transactions involving the specified address, but return all inputs and outputs
    from those transactions — regardless of whether each individual input/output is related to the address.
    """
    records = []
    before = int(datetime.now(tz=timezone.utc).timestamp() * 1000)

    for _ in range(max_pages):
        url = (
            f"{API_BASE}/addresses/{address}/full-transactions-page"
            f"?limit=500&before={before}&resolve_previous_outpoints=full&acceptance=accepted"
        )
        print(f"📦 Fetching before={before} for {address}")
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"❌ Error fetching transactions: {e}")
            break

        if not isinstance(data, list) or not data:
            print("✅ No more transactions.")
            break

        for tx in data:
            if not isinstance(tx, dict):
                print(f"⚠️ Skipping non-dict entry: {tx}")
                continue

            tx_id = tx.get("transaction_id", tx.get("txId", "UNKNOWN"))
            timestamp = format_timestamp(tx.get("block_time", 0))
            inputs = tx.get("inputs") or [] # inputs = tx.get("inputs", [])
            outputs = tx.get("outputs") or [] # outputs = tx.get("outputs", [])

            # Build full input set (transaction-level context)
            input_summary = {}
            for inp in inputs:
                sender = inp.get("previous_outpoint_address", "UNKNOWN")
                input_summary[sender] = input_summary.get(sender, 0) + int(inp.get("previous_outpoint_amount", 0))

            total_input_sompi = sum(input_summary.values())
            if total_input_sompi == 0:
                continue  # avoid divide-by-zero

            # For each output, record proportional attribution from each sender
            for out in outputs:
                recipient = out.get("script_public_key_address", "UNKNOWN")
                amount_sompi = int(out.get("amount", 0))
                for sender, contribution in input_summary.items():
                    weight = contribution / total_input_sompi
                    records.append({
                        "tx_id": tx_id,
                        "timestamp": timestamp,
                        "sender": sender,
                        "recipient": recipient,
                        "amount_kas": amount_sompi * weight / 1e8
                    })

        before = data[-1].get("block_time", before)

    return pd.DataFrame(records)

def trace_wallet(address):
    print(f"🔍 Fetching full transaction set for {address} (all participants mode)")
    txs = fetch_transactions_all_participants(address)
    print(f"📥 {len(txs)} total sender→recipient records collected")

    txs_filtered = txs
    
    try:
        # Only keep transactions involving the address directly
        txs_filtered = txs[(txs["sender"] == address) | (txs["recipient"] == address)]
        print(f"🔎 {len(txs_filtered)} filtered records where {address} was sender or recipient")
    except:
        print('no transactions')
        
    # Save the full and filtered dataset
    full_outpath = os.path.join(DATA_DIR, f"{address.replace(':', '_')}_all_participants.csv")
    filtered_outpath = os.path.join(DATA_DIR, f"{address.replace(':', '_')}_involving.csv")

    txs.to_csv(full_outpath, index=False)
    txs_filtered.to_csv(filtered_outpath, index=False)

    print(f"✅ Saved full transaction data to {full_outpath}")
    print(f"✅ Saved filtered personal transaction data to {filtered_outpath}")
    
if __name__ == "__main__":
    for addr in ROOTS:
        trace_wallet(addr)
    print("✅ Completed full non-recursive transaction history export.")
