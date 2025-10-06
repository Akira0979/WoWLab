import os, json
from collections import defaultdict
from flask import render_template
from neo4j import GraphDatabase
from modules.ollama_helper import ask_llama

def render_classification_tables(docs, driver):
    rel_lines = []
    with driver.session() as sess:
        result = sess.run("MATCH ()-[r]->() RETURN type(r) AS rel_name, count(r) AS cnt")
        for rec in result:
            rel_lines.append(f"{rec['rel_name']}: {rec['cnt']}")
    rel_summary = "Graph Relations:\n" + "\n".join(rel_lines) if rel_lines else "Graph Relations: (none found)"

    group_counts, sector_counts, service_counts = defaultdict(int), defaultdict(int), defaultdict(int)
    for d in docs:
        cls = d.get("classification", {}) or {}
        grp = cls.get("group_priority", "Unknown")
        sect = cls.get("sector", "Unknown")
        svcs = cls.get("service_offerings", [])
        if not isinstance(svcs, (list, tuple)):
            svcs = [svcs or "Unknown"]
        group_counts[grp] += 1
        sector_counts[sect] += 1
        for svc in svcs:
            service_counts[svc] += 1

    return render_template(
        "graph_summary.html",
        rel_summary=rel_summary,
        group_summary=[{"name": k, "count": v} for k, v in group_counts.items()],
        sector_summary=[{"name": k, "count": v} for k, v in sector_counts.items()],
        service_summary=[{"name": k, "count": v} for k, v in service_counts.items()]
    )

def summarize_with_llama(docs):
    prompt = "Summarize the following documents by group priority, sector, and service offering:\n\n"
    for d in docs:
        prompt += f"- {d['filename']}: {d.get('overview_summary','')[:100]}...\n"
    return ask_llama(prompt)