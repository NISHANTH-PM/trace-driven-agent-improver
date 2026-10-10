import json
from app.service import run_improvement_cycle

if __name__ == "__main__":
    result = run_improvement_cycle()
    print(json.dumps({
        "baseline": {k: result["baseline"][k]["success_rate"] for k in ["development", "held_out"]},
        "candidate": {k: result["candidate"][k]["success_rate"] for k in ["development", "held_out"]},
        "proposals": result["proposals"], "promotion": result["promotion"],
        "active_version": result["active_version"], "note": result["note"]
    }, indent=2))
