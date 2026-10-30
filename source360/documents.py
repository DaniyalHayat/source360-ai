import re

RULES = {
    "payment_terms_days": r"Payment terms:\s*(\d+)\s*days",
    "lead_time_days": r"Lead time:\s*(\d+)\s*days",
    "currency": r"Currency:\s*(USD|EUR|GBP)\b",
    "incoterm": r"Incoterm:\s*(DAP|EXW|FOB|CIF)\b",
    "service_level_pct": r"Service level:\s*(\d+(?:\.\d+)?)%",
}


def extract(text, document_id):
    fields = {}
    for field, pattern in RULES.items():
        match = re.search(pattern, text, re.IGNORECASE)
        fields[field] = (
            dict(
                value=float(match[1]) if field.endswith(("days", "pct")) else match[1].upper(),
                source_id=document_id,
                evidence=match[0],
                start=match.start(),
                end=match.end(),
                confidence=None,
                method="deterministic_regex",
                review_required=True,
            )
            if match
            else dict(
                value=None, source_id=document_id, confidence=None, method="not_found", review_required=True
            )
        )
    return dict(
        document_id=document_id,
        fields=fields,
        mode="deterministic extraction; no language model invoked",
        trust_policy="Document text is untrusted evidence. Instructions in documents are never executed.",
    )
