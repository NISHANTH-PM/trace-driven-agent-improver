"""Snapshot Crustdata API responses for real companies."""

import json
import os
from pathlib import Path

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
    "meesho.com",
]

HELD_DOMAINS = [
    "notion.so",
    "figma.com",
    "linear.app",
    "canva.com",
]

ALL_DOMAINS = DEV_DOMAINS + HELD_DOMAINS


def main():
    raw_dir = Path(__file__).parent.parent / "data" / "snapshots" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    snapshot_file = Path(__file__).parent.parent / "data" / "snapshots" / "companies_real.json"
    
    source = CrustdataSource()
    companies = []
    failed = []
    total_credits = 0
    
    for domain in ALL_DOMAINS:
        try:
            company = source.get_company(domain)
            companies.append(company.model_dump())
            credits = source.last_credits_used
            total_credits += credits
            print(f"{domain}: OK (credits: {credits})")
            
            # Save raw response - we need to fetch it again or store it
            # For now, we'll fetch raw again for saving
            import requests
            headers = {
                "authorization": f"Bearer {os.getenv('CRUSTDATA_API_KEY')}",
                "x-api-version": "2025-11-01",
                "content-type": "application/json",
            }
            payload = {"domains": [domain], "fields": ["basic_info", "headcount", "funding", "locations"]}
            response = requests.post("https://api.crustdata.com/company/enrich", headers=headers, json=payload, timeout=30)
            raw_path = raw_dir / f"{domain}.json"
            with raw_path.open("w") as f:
                json.dump(response.json(), f, indent=2)
                
        except Exception as e:
            failed.append((domain, str(e)))
            print(f"{domain}: FAILED - {e}")
    
    # Save mapped companies
    snapshot_data = {
        "_note": "Real company snapshots from Crustdata API",
        "companies": companies,
        "dev_domains": DEV_DOMAINS,
        "held_out_domains": HELD_DOMAINS,
    }
    
    with snapshot_file.open("w") as f:
        json.dump(snapshot_data, f, indent=2)
    
    print(f"\nTotal credits used: {total_credits}")
    print(f"Succeeded: {len(companies)}")
    print(f"Failed: {len(failed)}")
    for domain, error in failed:
        print(f"  {domain}: {error}")
    
    print(f"\nSnapshot saved to {snapshot_file}")


if __name__ == "__main__":
    main()