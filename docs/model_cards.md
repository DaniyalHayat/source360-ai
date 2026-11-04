# Models and limitations

## Allocation

Continuous quantity variables and binary supplier selection. Demand must be met exactly. Supplier awards cannot exceed quoted capacity times an explicit multiplier, or max_share times demand. Selected suppliers receive at least 1% of demand to avoid nominal selections. A configurable minimum/maximum supplier count and operationally qualified share are enforced. Purchases, logistics, fixed costs and noncash risk preference are exposed separately. Quantity discounts, whole-unit integrality, multi-item capacity sharing, FX uncertainty, default events, and executable awards are outside this single-item model.

The Python implementation solves a MILP with PuLP/CBC. The browser enumerates every allowed subset of up to four bidders and all vertices of its bounded LP with demand and qualification constraints. It returns the best feasible objective. Both implementations are tested against each other across ten categories and five parameter settings each, including infeasibility. Alternative solutions may share the same objective; allocation ties are not interpreted as unique business decisions.

## Monte Carlo

5,000 draws by default. Common price shock triangular(0.94,1,1.12), supplier price factor triangular(0.97,1,1.04), demand factor triangular(0.9,1,1.15). Fixed costs remain fixed. Savings use the same demand shock as the baseline. Outputs are fixed-mix stress costs, not proof that stressed demand respects original capacity. No probability-of-disruption claim. Public and Python random number generators differ; each is seeded and reproducible internally.

## Forecast

Monthly nominal spend, not unit demand. A minimum of 24 observations is required, including six expanding one-step origins. Compare additive-trend ETS with a seasonal-naive baseline using WAPE, then refit on available history. Horizon-specific empirical absolute residuals supply approximate prediction bands; every residual and sample count is returned for inspection. These retrospective bands share history with model selection and do not establish future 90% coverage. Synthetic timing and composition limit realism. No causal market inference is claimed.

## Evidence

Deterministic extraction covers payment terms, lead time, ISO currency, Incoterm and service level against a 50-field synthetic golden set. Separately, extensions/rag/assistant.py implements MiniLM semantic retrieval and FLAN-T5 generation. The local models were rerun on November 4 with five retrieval and answer checks passing. Source offsets are preserved, numerical tokens are checked, and human review remains required. First-match extraction and retrieval do not resolve conflicting amendments or guarantee semantic correctness. The public browser edition replays recorded results; the local API can answer new questions.
