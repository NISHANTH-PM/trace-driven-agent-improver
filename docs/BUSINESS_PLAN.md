# Business plan (built with cfo.ai)

The full model is in `docs/cfo_plan/` (Excel exports from cfo.ai: Base, Growth, Low-volume stress). This page summarizes it. Inputs marked **assumption** are not measured.

## Product and customers

An agent that turns live company data into a one-page briefing (Word, optionally PowerPoint and Excel) and checks the key figures against the source before delivering. Target users:

- **Students** preparing for placements and interviews (low price, high volume).
- **Small businesses** researching competitors or prospects (higher price, lower volume).

## Pricing (assumption)

| Tier | Price per briefing | Share of volume |
|---|---|---|
| Student | about $0.55 (roughly Rs 49) | 80% |
| Business | about $2.20 (roughly Rs 199) | 20% |

Blended revenue per briefing: $0.88.

## Cost per briefing

| Line | Per briefing | Status |
|---|---|---|
| Company data API | 2 credits x $0.02 x 1.3 calls = $0.052 | **assumption**: credit price not yet confirmed |
| LLM (Nova Lite) | $0.00013 in the plan | **measured**: runs cost about $0.00008 per briefing (10 cases: $0.000799), so the plan is conservative |
| Retries | 0.3 extra calls per briefing, folded into the 1.3 calls factor | assumption |
| Hosting | $15 per month | assumption |
| Monitoring and tooling | $0 (free tiers) | assumption |

Variable cost per briefing in the plan: $0.0521. The data API is more than 99% of it, so margin is decided by the data price, not the model.

## Scenarios (from the cfo.ai model)

| | Base | Growth | Low-volume stress |
|---|---|---|---|
| Briefings per month | 100 | 1,000 | 10 |
| Revenue | $88.00 | $880.00 | $8.80 |
| Variable cost | $5.21 | $52.13 | $0.52 |
| Fixed costs | $15.00 | $15.00 | $15.00 |
| Profit per month | $67.79 | $812.87 | -$6.72 |
| Gross margin | 94.08% | 94.08% | 94.08% |
| Break-even briefings per month | 19 | 19 | 19 |

Starting cash $2,000, no salaries. Payment fees, customer acquisition and taxes are excluded. Runway figures only describe constant-burn arithmetic and are not a demand forecast.

## Sensitivity to the data price (same formulas)

| API credit price | Variable cost per briefing | Blended margin | Break-even briefings | Student-tier-only margin |
|---|---|---|---|---|
| $0.02 (plan) | $0.052 | 94.1% | 19 | 90.5% |
| $0.05 | $0.130 | 85.2% | 20 | 76.3% |
| $0.10 | $0.260 | 70.4% | 25 | 52.7% |
| $0.20 | $0.520 | 40.9% | 42 | 5.4% |

The business survives a 5x higher data price on the blended mix. A student-only product would not survive a 10x price.

## What is measured and what is assumed

- Measured: LLM tokens and cost per briefing, success rates, retry behavior (see `EVIDENCE.md`).
- Assumed: all prices, the 80/20 mix, the data credit price, hosting, demand.
- Not validated: willingness to pay, repeat use, and whether commercial reuse of the data is permitted under Crustdata's terms. These are the first things to confirm.
