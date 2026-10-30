# Models and limitations

## Allocation

Continuous quantity variables and binary supplier selection. Demand must be met exactly. Supplier awards cannot exceed quoted capacity times an explicit multiplier, or max_share times demand. Selected suppliers receive at least 1% of demand to avoid nominal selections. A configurable minimum/maximum supplier count and operationally qualified share are enforced. Purchases, logistics, fixed costs and noncash risk preference are exposed separately. Quantity discounts, whole-unit integrality, multi-item capacity sharing, FX uncertainty, default events, and executable awards are outside this single-item model.

The Python implementation solves a MILP with PuLP/CBC. The browser enumerates every allowed subset of up to four bidders and all vertices of its bounded LP with demand and qualification constraints. It returns the best feasible objective. Both implementations are tested against each other across ten categories and five parameter settings each, including infeasibility. Alternative solutions may share the same objective; allocation ties are not interpreted as unique business decisions.

## Monte Carlo

5,000 draws by default. Common price shock triangular(0.94,1,1.12), supplier price factor triangular(0.97,1,1.04), demand factor triangular(0.9,1,1.15). Fixed costs remain fixed. Savings use the same demand shock as the baseline. Outputs are fixed-mix stress costs, not proof that stressed demand respects original capacity. No probability-of-disruption claim. Public and Python random number generators differ; each is seeded and reproducible internally.

## Forecast

Monthly nominal spend, not unit demand. Thirty-six observations per category; six expanding one-step backtests. Compare additive-trend ETS with a 12-month seasonal-naive baseline using WAPE. Fit ETS on scaled values to avoid numeric instability and reject failed convergence. Select the lower-error model, then refit on all observations for six months. Approximate 90% bands use one-step RMSE x 1.645 x sqrt(horizon); multi-step coverage is uncalibrated. Synthetic uniform sample timing and category composition limit realism. No causal inference from the separate market indices is claimed.

## Evidence

Deterministic regular expressions for payment terms, lead time, ISO currency, Incoterm, service level. Each extracted field has source ID, exact text and offsets, method, null confidence (no invented calibrated score), and required review. A manually specified 50-field synthetic golden set includes missing fields and injection text. First matching field only; ambiguous/amended contracts require review. No LLM or semantic RAG is implemented. Optional future LLM extraction must preserve the same validation and evidence contract.
