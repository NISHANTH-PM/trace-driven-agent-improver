"""Snapshot Crustdata API responses for real companies."""

import argparse
import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

from app.pack.crustdata import CrustdataSource
from app.pack.models import CompanyData


DEV_DOMAINS = [
    "razorpay.com",
    "postman.com",
    "browserstack.com",
    "freshworks.com",
    "swiggy.com",
    "chargebee.com",
]

HELD_DOMAINS = [
    "figma.com",
    "linear.app",
    "canva.com",
    "notion.com",
]

ALL_DOMAINS = DEV_DOMAINS + HELD_DOMAINS

EXISTING_RAW = {
    "razorpay.com",
    "postman.com",
    "browserstack.com",
    "freshworks.com",
    "swiggy.com",
}

DOMAINS_TO_FETCH = [d for d in ALL_DOMAINS if d not in EXISTING_RAW]


def normalize_domain(d: str) -> str:
    d = d.lower().strip()
    if d.startswith("www."):
        d = d[4:]
    return d


def fetch_with_retry(headers: dict, payload: dict, max_retries: int = 2) -> requests.Response:
    for attempt in range(max_retries + 1):
        response = requests.post(
            "https://api.crustdata.com/company/enrich",
            headers=headers,
            json=payload,
            timeout=30,
        )
        if response.status_code == 429 and attempt < max_retries:
            print(f"  Rate limited (429), waiting 15s before retry {attempt + 1}/{max_retries}...")
            time.sleep(15)
            continue
        return response
    return response


def check_acceptance(company_data: dict, requested_domain: str) -> tuple[bool, str]:
    basic_info = company_data.get("basic_info", {})
    headcount = company_data.get("headcount", {})
    locations = company_data.get("locations", {})

    primary_domain = basic_info.get("primary_domain", "")
    if primary_domain:
        if normalize_domain(primary_domain) != normalize_domain(requested_domain):
            matched_name = basic_info.get("name", "unknown")
            return False, f"domain mismatch: primary_domain={primary_domain} != {requested_domain} (matched: {matched_name})"

    if headcount.get("total") is None:
        matched_name = basic_info.get("name", "unknown")
        return False, f"missing headcount.total (matched: {matched_name})"

    if basic_info.get("year_founded") is None:
        matched_name = basic_info.get("name", "unknown")
        return False, f"missing basic_info.year_founded (matched: {matched_name})"

    if not locations.get("headquarters"):
        matched_name = basic_info.get("name", "unknown")
        return False, f"missing locations.headquarters (matched: {matched_name})"

    return True, ""


def rebuild_from_raw(raw_dir: Path, snapshot_file: Path) -> tuple[list, dict, list, list]:
    """Rebuild snapshot from existing raw files without HTTP calls."""
    companies = []
    accepted_domains = {"development": [], "held_out": []}
    skipped = []
    total_credits = 0

    for domain in ALL_DOMAINS:
        raw_path = raw_dir / f"{domain}.json"
        if not raw_path.exists():
            skipped.append((domain, "no raw file"))
            print(f"{domain}: SKIPPED - no raw file")
            continue

        with raw_path.open() as f:
            data = json.load(f)

        if not isinstance(data, list) or len(data) == 0:
            skipped.append((domain, "invalid raw format"))
            print(f"{domain}: SKIPPED - invalid raw format")
            continue

        result = data[0]
        matches = result.get("matches", [])
        if not matches:
            skipped.append((domain, "no matches in raw"))
            print(f"{domain}: SKIPPED - no matches in raw")
            continue

        best_match = max(matches, key=lambda m: m.get("confidence_score", 0))
        company_data = best_match.get("company_data", {})

        accepted, reason = check_acceptance(company_data, domain)
        matched_name = company_data.get("basic_info", {}).get("name", "unknown")

        if accepted:
            try:
                company = CrustdataSource().get_company(domain)
                companies.append(company.model_dump())
                split = "development" if domain in DEV_DOMAINS else "held_out"
                accepted_domains[split].append(domain)
                old_hq = None
                # Get old hq_city from existing snapshot if available
                if snapshot_file.exists():
                    with snapshot_file.open() as f:
                        existing = json.load(f)
                    for c in existing.get("companies", []):
                        if c["domain"] == domain:
                            old_hq = c.get("hq_city")
                            break
                new_hq = company.hq_city
                if old_hq and old_hq != new_hq:
                    print(f"{domain}: OK (rebuilt) - {matched_name} | hq_city: {old_hq!r} -> {new_hq!r}")
                else:
                    print(f"{domain}: OK (rebuilt) - {matched_name} | hq_city: {new_hq!r}")
            except Exception as e:
                skipped.append((domain, f"mapping error: {e}"))
                print(f"{domain}: SKIPPED - mapping error: {e}")
        else:
            skipped.append((domain, reason))
            print(f"{domain}: SKIPPED - {reason}")

    # Check minimum requirements
    dev_count = len(accepted_domains["development"])
    held_count = len(accepted_domains["held_out"])

    print(f"\nAccepted DEV: {dev_count}/6")
    print(f"Accepted HELD-OUT: {held_count}/4")

    if dev_count < 6 or held_count < 4:
        print("\nERROR: Insufficient accepted companies!")
        print(f"  DEV domains accepted: {accepted_domains['development']}")
        print(f"  HELD-OUT domains accepted: {accepted_domains['held_out']}")
        print(f"  Skipped: {skipped}")
        raise SystemExit(1)

    return companies, accepted_domains, skipped, total_credits


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-raw", action="store_true", help="Rebuild snapshot from existing raw files without HTTP calls")
    args = parser.parse_args()

    raw_dir = Path(__file__).parent.parent / "data" / "snapshots" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    snapshot_file = Path(__file__).parent.parent / "data" / "snapshots" / "companies_real.json"

    if args.from_raw:
        print("Rebuilding snapshot from raw files (no HTTP calls)...")
        companies, accepted_domains, skipped, total_credits = rebuild_from_raw(raw_dir, snapshot_file)

        # Save mapped companies
        snapshot_data = {
            "_note": "Real company snapshots from Crustdata API (rebuilt from raw with city preference)",
            "companies": companies,
            "dev_domains": accepted_domains["development"],
            "held_out_domains": accepted_domains["held_out"],
        }

        with snapshot_file.open("w") as f:
            json.dump(snapshot_data, f, indent=2)

        print(f"\nTotal credits used: {total_credits}")
        print(f"Accepted: {len(companies)}")
        print(f"Skipped: {len(skipped)}")
        for domain, reason in skipped:
            print(f"  {domain}: {reason}")

        print(f"\nSnapshot saved to {snapshot_file}")
        return

    # Original fetch logic
    # Load existing snapshot to preserve accepted companies
    existing_companies = []
    existing_dev = []
    existing_held = []
    if snapshot_file.exists():
        with snapshot_file.open() as f:
            existing = json.load(f)
        existing_companies = existing.get("companies", [])
        existing_dev = existing.get("dev_domains", [])
        existing_held = existing.get("held_out_domains", [])

    # Load existing raw files for companies we're keeping
    existing_raw_data = {}
    for domain in EXISTING_RAW:
        raw_path = raw_dir / f"{domain}.json"
        if raw_path.exists():
            with raw_path.open() as f:
                existing_raw_data[domain] = json.load(f)

    headers = {
        "authorization": f"Bearer {os.getenv('CRUSTDATA_API_KEY')}",
        "x-api-version": "2025-11-01",
        "content-type": "application/json",
    }

    companies = []
    accepted_domains = {"development": [], "held_out": []}
    skipped = []
    failed = []
    total_credits = 0

    # First, process existing raw files (for domains we're keeping)
    for domain in EXISTING_RAW:
        if domain not in ALL_DOMAINS:
            continue
        if domain not in existing_raw_data:
            print(f"{domain}: no existing raw file, will fetch")
            continue

        data = existing_raw_data[domain]
        if not isinstance(data, list) or len(data) == 0:
            print(f"{domain}: invalid raw format")
            continue

        result = data[0]
        matches = result.get("matches", [])
        if not matches:
            print(f"{domain}: no matches in raw")
            continue

        best_match = max(matches, key=lambda m: m.get("confidence_score", 0))
        company_data = best_match.get("company_data", {})

        accepted, reason = check_acceptance(company_data, domain)
        matched_name = company_data.get("basic_info", {}).get("name", "unknown")

        if accepted:
            try:
                company = CrustdataSource().get_company(domain)
                companies.append(company.model_dump())
                credits = 0  # already counted before
                total_credits += credits
                split = "development" if domain in DEV_DOMAINS else "held_out"
                accepted_domains[split].append(domain)
                print(f"{domain}: OK (cached, credits: {credits}) - {matched_name}")
            except Exception as e:
                print(f"{domain}: ERROR mapping cached data - {e}")
                failed.append((domain, str(e)))
        else:
            skipped.append((domain, reason))
            print(f"{domain}: SKIPPED - {reason}")

    # Fetch missing domains
    for i, domain in enumerate(DOMAINS_TO_FETCH):
        payload = {
            "domains": [domain],
            "fields": ["basic_info", "headcount", "funding", "locations"],
            "exact_match": True,
        }

        print(f"Fetching {domain}...")
        response = fetch_with_retry(headers, payload)

        raw_path = raw_dir / f"{domain}.json"
        with raw_path.open("w") as f:
            json.dump(response.json(), f, indent=2)

        if response.status_code != 200:
            failed.append((domain, f"HTTP {response.status_code}"))
            print(f"{domain}: FAILED - HTTP {response.status_code}")
            if i < len(DOMAINS_TO_FETCH) - 1:
                time.sleep(1.5)
            continue

        try:
            data = response.json()
        except ValueError:
            failed.append((domain, "invalid JSON response"))
            print(f"{domain}: FAILED - invalid JSON")
            if i < len(DOMAINS_TO_FETCH) - 1:
                time.sleep(1.5)
            continue

        if not isinstance(data, list) or len(data) == 0:
            failed.append((domain, "unexpected response format"))
            print(f"{domain}: FAILED - unexpected format")
            if i < len(DOMAINS_TO_FETCH) - 1:
                time.sleep(1.5)
            continue

        result = data[0]
        matches = result.get("matches", [])
        if not matches:
            failed.append((domain, "no match"))
            print(f"{domain}: FAILED - no match")
            if i < len(DOMAINS_TO_FETCH) - 1:
                time.sleep(1.5)
            continue

        best_match = max(matches, key=lambda m: m.get("confidence_score", 0))
        company_data = best_match.get("company_data", {})

        # Read credits from header
        credits_header = response.headers.get("X-Credits-Used")
        if credits_header:
            try:
                total_credits += int(credits_header)
            except ValueError:
                pass

        accepted, reason = check_acceptance(company_data, domain)
        matched_name = company_data.get("basic_info", {}).get("name", "unknown")

        if accepted:
            try:
                company = CrustdataSource().get_company(domain)
                companies.append(company.model_dump())
                split = "development" if domain in DEV_DOMAINS else "held_out"
                accepted_domains[split].append(domain)
                print(f"{domain}: OK (credits: {credits_header or '?'}) - {matched_name}")
            except Exception as e:
                failed.append((domain, f"mapping error: {e}"))
                print(f"{domain}: FAILED mapping - {e}")
        else:
            skipped.append((domain, reason))
            print(f"{domain}: SKIPPED - {reason}")

        if i < len(DOMAINS_TO_FETCH) - 1:
            time.sleep(1.5)

    # Remove old raw files for domains no longer in our list
    for raw_file in raw_dir.glob("*.json"):
        domain = raw_file.stem
        if domain not in ALL_DOMAINS:
            raw_file.unlink()
            print(f"Removed old raw file: {domain}.json")

    # Check minimum requirements
    dev_count = len(accepted_domains["development"])
    held_count = len(accepted_domains["held_out"])

    print(f"\nAccepted DEV: {dev_count}/6")
    print(f"Accepted HELD-OUT: {held_count}/4")

    if dev_count < 6 or held_count < 4:
        print("\nERROR: Insufficient accepted companies!")
        print(f"  DEV domains accepted: {accepted_domains['development']}")
        print(f"  HELD-OUT domains accepted: {accepted_domains['held_out']}")
        print(f"  Skipped: {skipped}")
        print(f"  Failed: {failed}")
        raise SystemExit(1)

    # Save mapped companies
    snapshot_data = {
        "_note": "Real company snapshots from Crustdata API (with exact_match and acceptance filtering)",
        "companies": companies,
        "dev_domains": accepted_domains["development"],
        "held_out_domains": accepted_domains["held_out"],
    }

    with snapshot_file.open("w") as f:
        json.dump(snapshot_data, f, indent=2)

    print(f"\nTotal credits used: {total_credits}")
    print(f"Accepted: {len(companies)}")
    print(f"Skipped: {len(skipped)}")
    for domain, reason in skipped:
        print(f"  {domain}: {reason}")
    print(f"Failed: {len(failed)}")
    for domain, error in failed:
        print(f"  {domain}: {error}")

    print(f"\nSnapshot saved to {snapshot_file}")


if __name__ == "__main__":
    main()