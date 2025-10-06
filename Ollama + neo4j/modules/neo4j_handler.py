from neo4j import GraphDatabase
from typing import Dict

class Neo4jHandler:
    def __init__(self, driver):
        self.driver = driver

    def create_document_graph(self, doc: Dict):
        with self.driver.session() as session:
            session.write_transaction(self._create_nodes_and_relationships, doc)

    @staticmethod
    def _create_nodes_and_relationships(tx, doc: Dict):
        # Create Document node
        tx.run("""
            MERGE (d:Document {id: $id})
            SET d.filename = $filename,
                d.path = $path,
                d.language = $language,
                d.page_count = $page_count,
                d.content_length = $content_length,
                d.summary = $summary,
                d.ingested_at = $ingested_at
        """, {
            "id": doc["id"],
            "filename": doc["filename"],
            "path": doc["relative_path"],
            "language": doc["language"],
            "page_count": doc["page_count"],
            "content_length": doc["content_length"],
            "summary": doc["overview_summary"],
            "ingested_at": doc["ingested_at"]
        })

        # Create Client node
        tx.run("""
            MERGE (c:Client {name: $client})
            MERGE (d:Document {id: $id})
            MERGE (d)-[:BELONGS_TO]->(c)
        """, {
            "client": doc["tags"]["client"],
            "id": doc["id"]
        })

        # Create Region node
        tx.run("""
            MERGE (r:Region {name: $region})
            MERGE (d:Document {id: $id})
            MERGE (d)-[:LOCATED_IN]->(r)
        """, {
            "region": doc["tags"]["region"],
            "id": doc["id"]
        })

        # Create Domain node
        tx.run("""
            MERGE (dm:Domain {name: $domain})
            MERGE (d:Document {id: $id})
            MERGE (d)-[:PART_OF]->(dm)
        """, {
            "domain": doc["tags"]["domain"],
            "id": doc["id"]
        })

        # Create Industry nodes
        for industry in doc.get("industry_tags", {}).get("industries", []):
            tx.run("""
                MERGE (i:Industry {name: $industry})
                MERGE (d:Document {id: $id})
                MERGE (d)-[:TAGGED_AS]->(i)
            """, {
                "industry": industry,
                "id": doc["id"]
            })

        # Create Technology nodes
        for tech in doc.get("entities", {}).get("technologies", []):
            tx.run("""
                MERGE (t:Technology {name: $tech})
                MERGE (d:Document {id: $id})
                MERGE (d)-[:MENTIONS]->(t)
            """, {
                "tech": tech,
                "id": doc["id"]
            })

        # Create Partner nodes
        for partner in doc.get("entities", {}).get("partners", []):
            tx.run("""
                MERGE (p:Partner {name: $partner})
                MERGE (d:Document {id: $id})
                MERGE (d)-[:PARTNERED_WITH]->(p)
            """, {
                "partner": partner,
                "id": doc["id"]
            })

        # Create Product nodes
        for product in doc.get("entities", {}).get("products", []):
            tx.run("""
                MERGE (pr:Product {name: $product})
                MERGE (d:Document {id: $id})
                MERGE (d)-[:DESCRIBES]->(pr)
            """, {
                "product": product,
                "id": doc["id"]
            })