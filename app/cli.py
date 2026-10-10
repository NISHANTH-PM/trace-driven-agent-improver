import json

from app.observability import initialize_neatlogs, shutdown_neatlogs
from app.service import run_improvement_cycle


if __name__ == "__main__":
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
