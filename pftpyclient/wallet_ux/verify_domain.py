import requests
import toml
import xrpl
from urllib.parse import urlparse
import socket

def is_valid_domain(domain):
    """
    Validates the domain to ensure it is:
    1. Well-formed and uses HTTPS.
    2. Resolves to a public IP (not private or internal).
    3. Matches specific allowed domain patterns (if applicable).
    """
    try:
        # Parse the domain to ensure it's properly structured
        parsed = urlparse(f"https://{domain}")
        if not (parsed.scheme == "https" and parsed.netloc):
            return False  # Ensure HTTPS is used and the domain is valid

        # Resolve the domain to an IP address
        ip_address = socket.gethostbyname(parsed.hostname)

        # Prevent SSRF by blocking private or internal IP ranges
        private_ip_ranges = [
            ("10.0.0.0", "10.255.255.255"),
            ("172.16.0.0", "172.31.255.255"),
            ("192.168.0.0", "192.168.255.255"),
            ("127.0.0.0", "127.255.255.255"),  # Loopback
        ]
        for start, end in private_ip_ranges:
            if ip_in_range(ip_address, start, end):
                return False  # Reject private/internal IPs

        # Optional: Enforce specific domain patterns if known
        allowed_suffixes = [".example.com", ".trusted.com"]  # Example
        if not any(parsed.hostname.endswith(suffix) for suffix in allowed_suffixes):
            return False  # Reject domains outside allowed patterns

        return True  # Passes all checks
    except (socket.gaierror, ValueError):
        return False  # Reject invalid or unresolvable domains

def ip_in_range(ip, start, end):
    """
    Checks if an IP address falls within a given range.
    """
    import ipaddress
    ip = ipaddress.ip_address(ip)
    return ipaddress.ip_address(start) <= ip <= ipaddress.ip_address(end)

def verify_account_domain(account):
    """
    Verifies the domain for a given XRP Ledger account using the xrp-ledger.toml file.
    """
    domain_hex = account.get("Domain")
    if not domain_hex:
        return "", False  # No domain provided

    # Decode the domain from its hex representation
    domain = xrpl.utils.hex_to_str(domain_hex)

    # Validate the domain structure
    if not is_valid_domain(domain):
        return "", False  # Reject invalid domains

    # Construct the URL for the xrp-ledger.toml file
    toml_url = f"https://{domain}/.well-known/xrp-ledger.toml"

    try:
        # Safely make the request with headers and timeout
        toml_response = requests.get(
            toml_url, 
            headers={"User-Agent": "MyApp/1.0"},  # Custom User-Agent
            timeout=5  # Limit request duration
        )
        toml_response.raise_for_status()  # Raise an error for HTTP codes >= 400
    except (requests.RequestException, requests.ConnectionError):
        return "", False  # Handle connection errors or invalid responses

    verified = False
    if toml_response.ok:
        try:
            # Parse the TOML file content
            parsed_toml = toml.loads(toml_response.text)
            toml_accounts = parsed_toml.get("ACCOUNTS", [])
            # Check if the account is listed in the TOML file
            for t_a in toml_accounts:
                if t_a.get("address") == account.get("Account"):
                    verified = True
                    break
        except toml.TomlDecodeError:  # Handle TOML parsing errors
            return "", False

    return domain, verified

if __name__ == "__main__":
    from argparse import ArgumentParser

    # Parse the command-line argument for the XRP account address
    parser = ArgumentParser()
    parser.add_argument("address", type=str,
                        help="Classic address to check domain verification of")
    args = parser.parse_args()

    # Initialize the XRPL client
    client = xrpl.clients.JsonRpcClient("https://xrplcluster.com")
    try:
        # Fetch account information from the ledger
        response = xrpl.account.get_account_info(
            args.address, client, ledger_index="validated"
        )
        account_data = response.result.get("account_data")
        if account_data:
            # Verify the account's domain
            domain, verified = verify_account_domain(account_data)
            print(f"Domain: {domain}\nVerified: {verified}")
        else:
            print("Account data not found.")
    except xrpl.clients.ClientError as e:
        print(f"Error fetching account info: {e}")
