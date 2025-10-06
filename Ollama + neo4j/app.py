import os
import json
import asyncio
import time
import hashlib
from datetime import datetime, timezone
from typing import List
from modules.ollama_helper import ask_llama
from modules.graph_summary import render_classification_tables, summarize_with_llama

from flask import (
    Flask, jsonify, render_template, request,
    redirect, url_for, send_from_directory, session
)
import fitz  # PyMuPDF
from langdetect import detect
from werkzeug.utils import secure_filename

from neo4j import GraphDatabase
from modules.neo4j_handler import Neo4jHandler
from modules import metadata_extractors  # async enrich_text(text, page_count)

# -----------------------------
# App config
# -----------------------------
app = Flask(__name__)
app.secret_key = "change-this-secret-key"

# Hardcoded paths
ROOT_FOLDER = r"C:\Users\ANIRUGHO\Desktop\Python\WOW_DEMO_LAB\Ollama + neo4j\KM_folder"
METADATA_DIR = r"C:\Users\ANIRUGHO\Desktop\Python\WOW_DEMO_LAB\Ollama + neo4j\metadata"
SITEMAP_DIR = r"C:\Users\ANIRUGHO\Desktop\Python\WOW_DEMO_LAB\Ollama + neo4j\sitemaps"
UPLOADS_DIR = os.path.join(ROOT_FOLDER, "uploaded")           # for admin folder uploads (multiple files)
USER_RFP_DIR = os.path.join(ROOT_FOLDER, "user_rfp_uploads")  # for user RFP uploads (single file)

os.makedirs(SITEMAP_DIR, exist_ok=True)
os.makedirs(METADATA_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(USER_RFP_DIR, exist_ok=True)

# Hardcoded Neo4j credentials
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "graph@123"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
handler = Neo4jHandler(driver)

# -----------------------------
# Utility functions
# -----------------------------
def infer_tags(path: str):
    parts = path.replace("\\", "/").split("/")
    return {
        "domain": parts[0] if len(parts) > 0 else "Unknown",
        "region": parts[1] if len(parts) > 1 else "Unknown",
        "client": parts[2] if len(parts) > 2 else "Unknown"
    }

def file_hash(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def detect_language(text: str) -> str:
    try:
        return detect(text)
    except Exception:
        return "unknown"

def generate_quick_overview(text: str, max_chars: int = 500) -> str:
    return text.strip().replace("\n", " ")[:max_chars]

# -----------------------------
# Sitemap builder
# -----------------------------
def build_sitemap(root_folder: str) -> List[dict]:
    entries = []
    for dirpath, _, filenames in os.walk(root_folder):
        print(f"Scanning: {dirpath}, found {len(filenames)} files")
        for fname in filenames:
            print(f"  -> {fname}")
            ext = os.path.splitext(fname)[1].lower()
            if ext != ".pdf":
                continue
            full_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(full_path, root_folder)
            tags = infer_tags(rel_path)
            stat = os.stat(full_path)
            try:
                with fitz.open(full_path) as doc:
                    page_count = doc.page_count
                    text = doc[0].get_text("text") if page_count > 0 else ""
            except Exception:
                page_count = 0
                text = ""
            entries.append({
                "id": file_hash(full_path)[:12],
                "filename": fname,
                "absolute_path": full_path,
                "relative_path": rel_path,
                "extension": ext,
                "domain": tags["domain"],
                "region": tags["region"],
                "client": tags["client"],
                "file_size_bytes": stat.st_size,
                "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "page_count": page_count,
                "quick_overview": generate_quick_overview(text)
            })
    print(f"Total PDFs found: {len(entries)}")
    return entries

# -----------------------------
# PDF metadata extractor
# -----------------------------
def extract_pdf_text(file_path: str) -> str:
    text_chunks = []
    with fitz.open(file_path) as doc:
        for page in doc:
            text_chunks.append(page.get_text("text"))
    return "\n".join(text_chunks)

def extract_pdf_metadata(file_path: str) -> dict:
    props = {}
    try:
        stat = os.stat(file_path)
        props["file_size_bytes"] = stat.st_size
        props["created_time"] = datetime.fromtimestamp(stat.st_ctime).isoformat()
        props["modified_time"] = datetime.fromtimestamp(stat.st_mtime).isoformat()
    except Exception as e:
        props["fs_meta_error"] = str(e)

    try:
        with fitz.open(file_path) as doc:
            props["page_count"] = doc.page_count
            props["pdf_metadata"] = doc.metadata or {}
    except Exception as e:
        props["pdf_meta_error"] = str(e)

    return props

async def process_pdf(entry: dict, root_folder: str, preview_chars: int = 1500) -> dict:
    full_path = os.path.join(root_folder, entry["relative_path"])
    start = time.time()
    try:
        text = await asyncio.to_thread(extract_pdf_text, full_path)
        props = await asyncio.to_thread(extract_pdf_metadata, full_path)
        lang = detect_language(text)
        hash_val = file_hash(full_path)
        enrichment = await metadata_extractors.enrich_text(text, props.get("page_count", 0))
    except Exception as e:
        return {"error": str(e), "filename": entry.get("filename", "unknown")}

    elapsed = round(time.time() - start, 3)

    return {
        "id": hash_val[:12],
        "filename": entry["filename"],
        "relative_path": entry["relative_path"],
        "extension": entry["extension"],
        "tags": {
            "domain": entry["domain"],
            "region": entry["region"],
            "client": entry["client"]
        },
        "file_size_bytes": props.get("file_size_bytes"),
        "last_modified": props.get("modified_time"),
        "page_count": props.get("page_count"),
        "content_length": len(text),
        "pdf_metadata": props.get("pdf_metadata"),
        "hash": hash_val,
        "language": lang,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "content_preview": text[:preview_chars],
        "overview_summary": enrichment["content_summary"]["summary"],
        "content_summary": enrichment["content_summary"],
        "classification": enrichment["classification"],
        "industry_tags": enrichment["industry_tags"],
        "entities": enrichment["entities"],
        "extraction_time_sec": elapsed
    }

async def process_all_pdfs(sitemap: List[dict], root_folder: str):
    tasks = [process_pdf(entry, root_folder) for entry in sitemap]
    return await asyncio.gather(*tasks)

# -----------------------------
# Auth (basic placeholder)
# -----------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    # POST
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    # Very basic role routing (placeholder)
    if username.lower().startswith("admin"):
        session["role"] = "admin"
        return redirect(url_for("admin_panel"))
    else:
        session["role"] = "user"
        return redirect(url_for("user_panel"))


# -----------------------------
# Dashboard and panels
# -----------------------------
@app.route("/")
def home():
    # Use dashboard as the new home
    return render_template("dashboard.html")

@app.route("/admin", methods=["GET"])
def admin_panel():
    return render_template("admin.html")

@app.route("/user", methods=["GET"])
def user_panel():
    return render_template("user.html")

# -----------------------------
# Admin actions
# -----------------------------
@app.route("/ingest", methods=["GET"])
def ingest():
    # Build sitemap
    sitemap = build_sitemap(ROOT_FOLDER)
    sitemap_path = os.path.join(SITEMAP_DIR, "sitemap.json")
    with open(sitemap_path, "w", encoding="utf-8") as f:
        json.dump(sitemap, f, indent=2, ensure_ascii=False)

    # Async processing
    results = asyncio.run(process_all_pdfs(sitemap, ROOT_FOLDER))
    metadata_path = os.path.join(METADATA_DIR, "metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Push to Neo4j
    for doc in results:
        if "id" in doc and "filename" in doc and "error" not in doc:
            handler.create_document_graph(doc)

    preview = json.dumps(results[:1], indent=2, ensure_ascii=False)
    return render_template(
        "results.html",
        files_processed=len(results),
        sitemap_file=sitemap_path,
        metadata_file=metadata_path,
        metadata_preview=preview
    )

@app.route("/view_sitemap", methods=["GET"])
def view_sitemap():
    path = os.path.join(SITEMAP_DIR, "sitemap.json")
    if not os.path.exists(path):
        return jsonify({"error": "No sitemap found. Run ingestion first."}), 404
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)

@app.route("/view_metadata", methods=["GET"])
def view_metadata():
    path = os.path.join(METADATA_DIR, "metadata.json")
    if not os.path.exists(path):
        return jsonify({"error": "No metadata found. Run ingestion first."}), 404
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)

@app.route("/view_graph", methods=["GET"])
def view_graph():
    with driver.session() as session_db:
        result = session_db.run("""
            MATCH (a)-[r]->(b)
            RETURN a, r, b LIMIT 200
        """)
        nodes, edges = [], []
        seen = set()

        def node_color(label):
            colors = {
                "Document": "#1f77b4",   # blue
                "Client": "#2ca02c",     # green
                "Region": "#ff7f0e",     # orange
                "Domain": "#9467bd",     # purple
                "Industry": "#8c564b",   # brown
                "Technology": "#17becf", # teal
                "Partner": "#d62728",    # red
                "Product": "#bcbd22"     # yellow-green
            }
            return colors.get(label, "#7f7f7f")  # default grey

        for record in result:
            a, r, b = record["a"], record["r"], record["b"]

            if a.id not in seen:
                label_a = list(a.labels)[0] if a.labels else "Node"
                nodes.append({
                    "id": a.id,
                    "label": label_a,
                    "title": dict(a),
                    "color": node_color(label_a)
                })
                seen.add(a.id)

            if b.id not in seen:
                label_b = list(b.labels)[0] if b.labels else "Node"
                nodes.append({
                    "id": b.id,
                    "label": label_b,
                    "title": dict(b),
                    "color": node_color(label_b)
                })
                seen.add(b.id)

            edges.append({
                "from": a.id,
                "to": b.id,
                "label": r.type
            })

    return render_template(
        "graph.html",
        nodes=json.dumps(nodes),
        edges=json.dumps(edges)
    )

@app.route("/upload_folder", methods=["POST"])
def upload_folder():
    """
    Handles multiple file uploads from the admin panel.
    Note: webkitdirectory sends individual files; we save each into UPLOADS_DIR.
    """
    files = request.files.getlist("folder")
    if not files:
        return jsonify({"status": "no_files"}), 400

    saved = []
    for f in files:
        filename = secure_filename(f.filename)
        # Preserve relative subpaths if provided by browser (some include directories)
        dest_path = os.path.join(UPLOADS_DIR, filename)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        f.save(dest_path)
        saved.append(dest_path)

    return jsonify({"status": "success", "files_saved": saved})

# -----------------------------
# User actions
# -----------------------------
@app.route("/upload_rfp", methods=["POST"])
def upload_rfp():
    """
    Handles user RFP upload (single PDF).
    """
    file = request.files.get("rfp_file")
    if file is None or file.filename == "":
        return jsonify({"status": "no_file"}), 400
    filename = secure_filename(file.filename)
    if not filename.lower().endswith(".pdf"):
        return jsonify({"status": "invalid_type", "message": "Only PDF allowed"}), 400
    dest_path = os.path.join(USER_RFP_DIR, filename)
    file.save(dest_path)

    # Track current doc in session
    doc_meta = {
        "filename": filename,
        "path": dest_path,
        "id": file_hash(dest_path)[:12]
    }
    session["current_doc"] = doc_meta
    session["chat_history"] = []  # reset chat history for new upload

    return jsonify({"status": "success", "saved_to": dest_path})

@app.route("/chatbot", methods=["POST"])
def chatbot():
    data = request.get_json(force=True)
    user_msg = (data.get("message") or "").strip()
    if not user_msg or len(user_msg) > 1000:
        return jsonify({"status": "error", "message": "Invalid input"}), 400

    # Initialize history if missing
    history = session.setdefault("chat_history", [])
    history.append({"role": "user", "content": user_msg})

    # Build context
    context = ""
    current_doc = session.get("current_doc")
    if current_doc:
        context += f"User uploaded doc: {current_doc['filename']} (id {current_doc['id']})\n"

        # Pull related docs from Neo4j
        try:
            with driver.session() as sess:
                res = sess.run("""
                    MATCH (d:Document {id:$doc_id})-[]->(x)<-[]-(other:Document)
                    WHERE other.id <> $doc_id
                    RETURN other.filename AS filename, labels(x)[0] AS via
                    LIMIT 10
                """, doc_id=current_doc["id"])
                related = [f"{r['filename']} via {r['via']}" for r in res]
            if related:
                context += "Related docs:\n" + "\n".join(related) + "\n"
        except Exception as e:
            context += f"(Neo4j lookup failed: {e})\n"

    # Add metadata summaries
    meta_path = os.path.join(METADATA_DIR, "metadata.json")
    if os.path.exists(meta_path):
        try:
            docs = json.load(open(meta_path, encoding="utf-8"))
            # Take top 3 summaries for grounding
            snippets = []
            for d in docs[:3]:
                snippets.append(f"{d['filename']}: {d.get('overview_summary','')}")
            context += "Sample corpus summaries:\n" + "\n".join(snippets) + "\n"
        except Exception as e:
            context += f"(Metadata load failed: {e})\n"

    # Prompt with history
    hist_str = "\n".join([f"{t['role']}: {t['content']}" for t in history[-10:]])
    prompt = (
        f"SYSTEM: You are a helpful assistant. Ground answers in the provided context and cite filenames when relevant.\n"
        f"CONTEXT:\n{context}\n\n"
        f"HISTORY:\n{hist_str}\n\n"
        f"USER: {user_msg}\nASSISTANT:"
    )

    answer = ask_llama(prompt)
    history.append({"role": "assistant", "content": answer})
    session["chat_history"] = history

    return jsonify({"status": "ok", "answer": answer, "history": history})

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.teardown_appcontext
def close_driver(exception):
    try:
        driver.close()
    except:
        pass

# -----------------------------
# Static file serving convenience (optional)
# -----------------------------
@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)

# -----------------------------
# Run app
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)