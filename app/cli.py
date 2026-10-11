import argparse
import json
import os
from datetime import datetime

from app.observability import initialize_neatlogs, shutdown_neatlogs
from app.service import run_improvement_cycle
from app.pack.service import run_pack_improvement_cycle


def run_ticket_task():
    initialize_neatlogs()
    try:
        result = run_improvement_cycle()
        print(
            json.dumps(
                {
                    "baseline": {
                        key: result["baseline"][key]["success_rate"]
                        for key in ["development", "held_out"]
                    },
                    "candidate": {
                        key: result["candidate"][key]["success_rate"]
                        for key in ["development", "held_out"]
                    },
                    "proposals": result["proposals"],
                    "promotion": result["promotion"],
                    "active_version": result["active_version"],
                    "note": result["note"],
                },
                indent=2,
            )
        )
    finally:
        shutdown_neatlogs()


def run_pack_task():
    initialize_neatlogs()
    try:
        result = run_pack_improvement_cycle()

        # Compact summary for stdout
        summary = {
            "baseline": {
                "development": {
                    "success_rate": result["baseline"]["development"]["success_rate"],
                    "successes": f"{result['baseline']['development']['successes']}/{result['baseline']['development']['total']}",
                    "failure_counts": result["baseline"]["development"]["failure_counts"],
                },
                "held_out": {
                    "success_rate": result["baseline"]["held_out"]["success_rate"],
                    "successes": f"{result['baseline']['held_out']['successes']}/{result['baseline']['held_out']['total']}",
                    "failure_counts": result["baseline"]["held_out"]["failure_counts"],
                },
            },
            "candidate": {
                "development": {
                    "success_rate": result["candidate"]["development"]["success_rate"],
                    "successes": f"{result['candidate']['development']['successes']}/{result['candidate']['development']['total']}",
                    "failure_counts": result["candidate"]["development"]["failure_counts"],
                },
                "held_out": {
                    "success_rate": result["candidate"]["held_out"]["success_rate"],
                    "successes": f"{result['candidate']['held_out']['successes']}/{result['candidate']['held_out']['total']}",
                    "failure_counts": result["candidate"]["held_out"]["failure_counts"],
                },
            },
            "proposals": result["proposals"],
            "promotion": result["promotion"],
            "active_version": result["active_version"],
            "cost": result["cost"],
        }
        print(json.dumps(summary, indent=2))

        # Write full result to evidence/
        os.makedirs("evidence", exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        evidence_path = f"evidence/pack_run_{timestamp}.json"
        with open(evidence_path, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\nFull result written to {evidence_path}")
    finally:
        shutdown_neatlogs()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=["ticket", "pack"], default="ticket")
    args = parser.parse_args()

    if args.task == "ticket":
        run_ticket_task()
    else:
        run_pack_task()
