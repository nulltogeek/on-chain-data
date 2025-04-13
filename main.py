from hexbytes import HexBytes
from web3 import Web3
from datetime import datetime, timedelta
import json
import os
from dotenv import load_dotenv
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from utils.utils import decode_erc20_transfer_amount

# === Load environment variables ===
load_dotenv()
QUICKNODE_HTTP_ENDPOINT = os.getenv("QUICK_NODE_API_URL")
OUTPUT_DIR = "recent_transactions"

# === Connect to Web3 ===
web3 = Web3(Web3.HTTPProvider(QUICKNODE_HTTP_ENDPOINT))
if not web3.is_connected():
    raise Exception("Web3 not connected.")

# === Thread-safe structures ===
tx_lock = Lock()


# === Helpers ===
def get_block_by_timestamp(target_ts):
    low, high = 0, web3.eth.block_number
    while low <= high:
        mid = (low + high) // 2
        block = web3.eth.get_block(mid)
        if block.timestamp < target_ts:
            low = mid + 1
        else:
            high = mid - 1
    return low


def process_block(block_num):
    local_txs = []
    try:
        block = web3.eth.get_block(block_num, full_transactions=True)
        for tx in block.transactions:
            if tx["input"] and tx["input"] != HexBytes("0x"):
                amount, recipient = decode_erc20_transfer_amount(tx["input"])
                if amount is not None:
                    tx_data = {
                        "tx_hash": tx["hash"].hex(),
                        "from": tx["from"],
                        "to": recipient,  # The actual recipient from input data
                        "contract_address": tx["to"],  # The token contract address
                        "amount": amount,
                        "datetime": datetime.utcfromtimestamp(block.timestamp).strftime(
                            "%Y-%m-%d %H:%M:%S UTC"
                        ),
                        "block_number": block_num,
                    }
                    local_txs.append(tx_data)
    except Exception as e:
        print(f"Error in block {block_num}: {e}")
    return local_txs


def scan_blocks(start_block, end_block, max_workers=4):
    block_range = list(range(start_block, end_block + 1))
    all_transactions = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_block, block): block for block in block_range
        }
        for future in tqdm(
            as_completed(futures), total=len(futures), desc="Scanning blocks", ncols=80
        ):
            block_txs = future.result()
            if block_txs:
                with tx_lock:
                    all_transactions.extend(block_txs)

    return all_transactions


def save_to_file(transactions, start_block, end_block):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Get the datetime range from the first and last transactions
    if transactions:
        start_date = transactions[0]["datetime"].split()[0]  # Extract date part
        end_date = transactions[-1]["datetime"].split()[0]
        filename = (
            f"txs_{start_date}_to_{end_date}_block_{start_block}_to_{end_block}.json"
        )
    else:
        filename = f"txs_block_{start_block}_to_{end_block}.json"

    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w") as f:
        json.dump(transactions, f, indent=2)
    return path


def main():
    try:
        start_input = input("Enter start datetime (e.g., 2024-04-10 00:00:00): ")
        end_input = input("Enter end datetime (e.g., 2024-04-12 23:59:59): ")

        # Parse datetimes
        start_dt = datetime.strptime(start_input, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(end_input, "%Y-%m-%d %H:%M:%S")

        if start_dt >= end_dt:
            raise ValueError("Start datetime must be earlier than end datetime.")

        # Convert to timestamps
        start_ts = int(start_dt.timestamp())
        end_ts = int(end_dt.timestamp())

        # Find the blocks
        start_block = get_block_by_timestamp(start_ts)
        end_block = get_block_by_timestamp(end_ts)

        print(
            f"Scanning from block {start_block} to {end_block} using multi-threading..."
        )

        transactions = scan_blocks(start_block, end_block)

        # Print transaction hashes
        print(f"\n🔍 Transaction Hashes:")
        for tx in transactions:
            print(f" - {tx['tx_hash']}")

        output_file = save_to_file(transactions, start_block, end_block)
        print(f"\n✅ {len(transactions)} transactions found.")
        print(f"📁 Saved to: {output_file}")

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
