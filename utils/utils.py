from hexbytes import HexBytes

def decode_erc20_transfer_amount(tx_input):
    # ERC-20 transfer method signature
    TRANSFER_SIGNATURE = HexBytes('0xa9059cbb')
    
    # Handle empty or invalid input
    if not tx_input or tx_input == HexBytes('0x'):
        return None, None
    
    # Check if it's a transfer call
    if not tx_input.startswith(TRANSFER_SIGNATURE):
        return None, None
    
    # Minimum length check
    if len(tx_input) < 68:  # 4 (signature) + 32 (address) + 32 (amount)
        return None, None
    
    try:
        # Extract recipient address (bytes 4-35)
        recipient_bytes = tx_input[4:36]
        recipient = '0x' + recipient_bytes[-20:].hex()  # Take last 20 bytes
        
        # Extract amount (last 32 bytes)
        amount_bytes = tx_input[-32:]
        raw_amount = int.from_bytes(amount_bytes, 'big')
        
        # Convert to decimal format (assuming 18 decimals)
        formatted_amount = raw_amount / (10 ** 18)
        return formatted_amount, recipient
    except:
        return None, None