import re

from sentence_transformers import SentenceTransformer
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from source360.database import read


class EvidenceAssistant:
    def __init__(self):
        self.embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        self.generator = None
        self.chunks = []
        for doc in read("contracts").to_dict("records"):
            for match in re.finditer(r"[^.]+(?:\.|$)", doc["text"]):
                text = match[0].strip()
                if text:
                    leading = len(match[0]) - len(match[0].lstrip())
                    trailing = len(match[0]) - len(match[0].rstrip())
                    self.chunks.append(
                        {
                            "source_id": doc["document_id"],
                            "supplier_id": doc["supplier_id"],
                            "text": text,
                            "start": match.start() + leading,
                            "end": match.end() - trailing,
                        }
                    )
        self.vectors = self.embedder.encode([c["text"] for c in self.chunks], normalize_embeddings=True)

    def retrieve(self, question, supplier_id=None, top_k=3):
        query = self.embedder.encode([question], normalize_embeddings=True)[0]
        scores = self.vectors @ query
        candidates = [
            i for i, c in enumerate(self.chunks) if supplier_id is None or c["supplier_id"] == supplier_id
        ]
        selected = sorted(candidates, key=lambda i: float(scores[i]), reverse=True)[:top_k]
        return [{**self.chunks[i], "retrieval_score": float(scores[i])} for i in selected]

    def answer(self, question, supplier_id=None):
        evidence = self.retrieve(question, supplier_id)
        if self.generator is None:
            self.tokenizer = AutoTokenizer.from_pretrained("google/flan-t5-small")
            self.generator = AutoModelForSeq2SeqLM.from_pretrained("google/flan-t5-small")
            self.generator.eval()
        context = evidence[0]["text"] if evidence else "Insufficient evidence"
        prompt = f"Answer using the context.\nContext: {context}\nQuestion: {question}\nAnswer:"
        tokens = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
        output = self.generator.generate(**tokens, max_new_tokens=70, do_sample=False)
        answer = self.tokenizer.decode(output[0], skip_special_tokens=True)
        context_numbers = set(re.findall(r"\d+(?:\.\d+)?", context))
        missing = [n for n in re.findall(r"\d+(?:\.\d+)?", answer) if n not in context_numbers]
        invalid = bool(missing) or bool(re.fullmatch(r"\s*(?:\[\d+\])?\s*", answer))
        return {
            "answer": answer,
            "evidence": evidence,
            "cited_source": evidence[0] if evidence else None,
            "model": "google/flan-t5-small",
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "review_required": True,
            "unsupported_numeric_tokens": missing,
            "validation_status": "rejected" if invalid else "human_review_required",
            "limitations": "Retrieval similarity is not confidence. Numeric grounding does not establish semantic correctness. No financial calculations or awards are delegated to this model.",
        }
