import os
import json
from typing import Dict, List, Tuple
from neo4j import Driver

def load_metadata(metadata_path: str) -> List[Dict]:
    if not os.path.exists(metadata_path):
        return []
    with open(metadata_path, "r", encoding="utf-8") as f:
        return json.load(f)

def keyword_filter(docs: List[Dict], query: str, top_k: int = 5) -> List[Dict]:
    q = query.lower()
    scored = []
    for d in docs:
        text = (d.get("overview_summary") or "") + " " + " ".join(d.get("industry_tags", {}).get("domains", []))
        score = text.lower().count(q)
        if q in (d.get("filename", "").lower()):
            score += 2
        if score > 0:
            scored.append((score, d))
    scored.sort(key=lambda x: -x[0])
    return [d for _, d in scored[:top_k]]

def neo4j_related(driver: Driver, current_doc_id: str, top_k: int = 8) -> List[Tuple[str, str]]:
    # Find documents connected via shared Industry/Technology/Client
    query = """
    MATCH (d:Document {id: $doc_id})-[]->(x)<-[]-(other:Document)
    WHERE other.id <> $doc_id
    RETURN other.filename AS filename, labels(x)[0] AS via_label
    LIMIT $top_k
    """
    with driver.session() as sess:
        res = sess.run(query, doc_id=current_doc_id, top_k=top_k)
        return [(r["filename"], r["via_label"]) for r in res]

def build_context_snippets(docs: List[Dict], filenames: List[str]) -> str:
    by_name = {d.get("filename"): d for d in docs}
    lines = []
    for fn in filenames:
        d = by_name.get(fn)
        if not d: 
            continue
        lines.append(f"- {fn} | Summary: {d.get('overview_summary','')}")
        industries = d.get("industry_tags", {}).get("industries", [])
        domains = d.get("industry_tags", {}).get("domains", [])
        ents = d.get("entities", {})
        techs = ents.get("technologies", [])
        lines.append(f"  Industries: {', '.join(industries) or 'n/a'}; Domains: {', '.join(domains) or 'n/a'}; Tech: {', '.join(techs) or 'n/a'}")
    return "\n".join(lines)