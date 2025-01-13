import requests
import toml
import xrpl
from urllib.parse import urlparse
import socket

def is_valid_domain(domain):
    """
    Validates the domain to ensure it is well-formed, secure, and resolves to a public IP.

    Params:
        domain: str - The domain to validate
    Returns:
        bool - True if the domain is valid, False otherwise
    """
    try:
        # Parse the domain
        parsed = urlparse(f"https://{domain}")
        if not (parsed.scheme == "https" and parsed.netloc):
            return False  # Must use HTTPS and have a valid hostname

        # Resolve the domain to an IP address
        ip_address = socket.gethostbyname(parsed.hostname)
        # Ensure the resolved IP is not private or internal
        private_ip_ranges = [
            ("10.0.0.0", "10.255.255.255"),
            ("172.16.0.0", "172.31.255.255"),
            ("192.168.0.0", "192.168.255.255"),
            ("127.0.0.0", "127.255.255.255"),  # Loopback
        ]
        for start, end in private_ip_ranges:
            if ip_in_range(ip_address, start, end):
                return False
        return True
    except (socket.gaierror, ValueError):
        return False

def ip_in_range(ip, start, end):
    """
    Check if an IP is in a given range.
    """
    import ipaddress
    ip = ipaddress.ip_address(ip)
    return ipaddress.ip_address(start) <= ip <= ipaddress.ip_address(end)

def verify_account_domain(account):
    """
    Verify an account using an xrp-ledger.toml file.

    Params:
        account: dict - The AccountRoot object to verify
    Returns:
        (domain: str, verified: bool) - The domain and whether the account is verified
    """
    domain_hex = account.get("Domain")
    if not domain_hex:
        return "", False

    domain = xrpl.utils.hex_to_str(domain_hex)

    # Validate the domain structure
    if not is_valid_domain(domain):
        return "", False

    toml_url = f"https://{domain}/.well-known/xrp-ledger.toml"
    try:
        toml_response = requests.get(toml_url, timeout=5)  # Add timeout for safety
        toml_response.raise_for_status()  # Raise exception for non-2xx responses
    except (requests.RequestException, requests.ConnectionError):
        return "", False

    verified = False
    if toml_response.ok:
        try:
            parsed_toml = toml.loads(toml_response.text)  # Parse the TOML content
            toml_accounts = parsed_toml.get("ACCOUNTS", [])
            for t_a in toml_accounts:
                if t_a.get("address") == account.get("Account"):
                    verified = True
                    break
        except toml.TomlDecodeError:  # Handle TOML parsing errors
            return "", False

    return domain, verified

if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument("address", type=str,
                        help="Classic address to check domain verification of")
    args = parser.parse_args()

    # Initialize the XRPL client
    client = xrpl.clients.JsonRpcClient("https://xrplcluster.com")
    try:
        response = xrpl.account.get_account_info(
            args.address, client, ledger_index="validated"
        )
        account_data = response.result.get("account_data")
        if account_data:
            domain, verified = verify_account_domain(account_data)
            print(f"Domain: {domain}\nVerified: {verified}")
        else:
            print("Account data not found.")
    except xrpl.clients.ClientError as e:
        print(f"Error fetching account info: {e}")
