import re
import asyncio
from typing import List, Dict
import spacy

# Load spaCy model once at module level
nlp = spacy.load("en_core_web_sm")

INDUSTRY_KEYWORDS = {
    "Finance": ["investment", "banking", "portfolio", "equity", "trading", "fintech"],
    "Healthcare": ["patient", "clinical", "diagnosis", "hospital", "biotech", "pharma"],
    "Education": ["curriculum", "learning", "pedagogy", "school", "university", "edtech"],
    "Manufacturing": ["supply chain", "factory", "production", "automation", "lean"],
    "Technology": ["AI", "machine learning", "cloud", "data", "software", "IoT"],
    "Retail": ["ecommerce", "inventory", "POS", "customer", "store", "shopping"],
    "Legal": ["compliance", "contract", "litigation", "regulation", "law", "jurisdiction"]
}

# -----------------------------
# Async wrappers
# -----------------------------
async def extract_industry_keywords(text: str) -> List[str]:
    def _extract():
        text_lower = text.lower()
        found_keywords = set()
        for industry, keywords in INDUSTRY_KEYWORDS.items():
            for keyword in keywords:
                if re.search(rf"\b{re.escape(keyword.lower())}\b", text_lower):
                    found_keywords.add(industry)
                    break
        return list(found_keywords)
    return await asyncio.to_thread(_extract)

async def extract_entities(text: str) -> Dict[str, List[str]]:
    def _extract():
        doc = nlp(text)
        entities = {
            "clients": [],
            "products": [],
            "technologies": [],
            "partners": []
        }
        for ent in doc.ents:
            if ent.label_ in ["ORG", "PRODUCT"]:
                entities["clients"].append(ent.text)
                entities["partners"].append(ent.text)
                entities["products"].append(ent.text)
        for token in doc:
            if token.pos_ == "PROPN" and token.text.lower() in ["azure", "terraform", "kubernetes"]:
                entities["technologies"].append(token.text)
        # Deduplicate
        for key in entities:
            entities[key] = list(set(entities[key]))
        return entities
    return await asyncio.to_thread(_extract)

async def extract_domain_tags(text: str) -> List[str]:
    def _extract():
        doc = nlp(text)
        return list(set([chunk.text for chunk in doc.noun_chunks if len(chunk.text.split()) <= 3]))
    return await asyncio.to_thread(_extract)

# -----------------------------
# Main async enrichment
# -----------------------------
async def enrich_text(text: str, page_count: int) -> Dict:
    industries, domains, entities = await asyncio.gather(
        extract_industry_keywords(text),
        extract_domain_tags(text),
        extract_entities(text)
    )
    word_count = len(text.split())

    return {
        "content_summary": {
            "summary": text[:300].replace("\n", " ") + "...",  # placeholder
            "word_count": word_count,
            "page_count": page_count
        },
        "classification": {
            "document_type": "RFX Response",  # placeholder
            "sub_type": "Technical Proposal"  # placeholder
        },
        "industry_tags": {
            "industries": industries,
            "domains": domains[:10]  # limit to top 10
        },
        "entities": entities
    }