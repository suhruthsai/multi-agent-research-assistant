"""
Knowledge graph for tracking relationships between papers, authors, and topics.
Uses networkx for graph operations.
"""

import logging
from typing import Optional

import networkx as nx

logger = logging.getLogger(__name__)


class KnowledgeGraph:
    def __init__(self):
        self.graph = nx.DiGraph()

    # ── Add data ──────────────────────────────────────────────────────────
    def add_papers(self, papers: list[dict]) -> None:
        """Add paper and author nodes, plus authored_by edges."""
        for paper in papers:
            url   = paper.get("url", "")
            title = paper.get("title", "")
            if not url or not title:
                continue

            # Add paper node
            self.graph.add_node(url, **{
                "type":           "paper",
                "label":          title[:60],
                "title":          title,
                "year":           paper.get("year", 0),
                "source":         paper.get("source", "unknown"),
                "citation_count": paper.get("citation_count", 0),
                "abstract":       paper.get("abstract", "")[:200],
            })

            # Add author nodes and edges
            for author in paper.get("authors", [])[:5]:
                author_id = f"author:{author.lower().strip()}"
                if not self.graph.has_node(author_id):
                    self.graph.add_node(author_id, **{
                        "type":  "author",
                        "label": author,
                        "name":  author,
                    })
                self.graph.add_edge(url, author_id, type="authored_by")

    def add_topics(self, paper_url: str, topics: list[str]) -> None:
        """Link LLM-extracted topics to a paper."""
        for topic in topics:
            topic_id = f"topic:{topic.lower().strip()}"
            if not self.graph.has_node(topic_id):
                self.graph.add_node(topic_id, **{
                    "type":  "topic",
                    "label": topic.title(),
                    "name":  topic,
                })
            if self.graph.has_node(paper_url):
                self.graph.add_edge(paper_url, topic_id, type="covers_topic")

    def add_citation_link(self, from_url: str, to_url: str) -> None:
        """Add a citation edge between two papers."""
        if self.graph.has_node(from_url) and self.graph.has_node(to_url):
            self.graph.add_edge(from_url, to_url, type="cites")

    def add_related_link(self, url_a: str, url_b: str, reason: str = "") -> None:
        """Add a related_to edge between two papers."""
        if self.graph.has_node(url_a) and self.graph.has_node(url_b):
            self.graph.add_edge(url_a, url_b, type="related_to", reason=reason)

    # ── Query ─────────────────────────────────────────────────────────────
    def get_papers(self) -> list[dict]:
        """Get all paper nodes."""
        return [
            {"id": n, **data}
            for n, data in self.graph.nodes(data=True)
            if data.get("type") == "paper"
        ]

    def get_topics(self) -> list[str]:
        """Get all unique topics."""
        return [
            data.get("name", "")
            for _, data in self.graph.nodes(data=True)
            if data.get("type") == "topic"
        ]

    def get_paper_topics(self, paper_url: str) -> list[str]:
        """Get topics for a specific paper."""
        topics = []
        for _, target, edge_data in self.graph.edges(paper_url, data=True):
            if edge_data.get("type") == "covers_topic":
                node_data = self.graph.nodes[target]
                topics.append(node_data.get("name", ""))
        return topics

    def get_author_papers(self, author_name: str) -> list[dict]:
        """Get all papers by an author."""
        author_id = f"author:{author_name.lower().strip()}"
        papers = []
        for source, target, edge_data in self.graph.edges(data=True):
            if target == author_id and edge_data.get("type") == "authored_by":
                node_data = self.graph.nodes[source]
                if node_data.get("type") == "paper":
                    papers.append({"id": source, **node_data})
        return papers

    def get_field_evolution(self, topic: str) -> list[dict]:
        """Get papers covering a topic, sorted chronologically."""
        topic_id = f"topic:{topic.lower().strip()}"
        papers = []
        for source, target, edge_data in self.graph.edges(data=True):
            if target == topic_id and edge_data.get("type") == "covers_topic":
                node_data = self.graph.nodes[source]
                if node_data.get("type") == "paper":
                    papers.append({"id": source, **node_data})
        return sorted(papers, key=lambda x: x.get("year", 0))

    def get_co_authors(self, author_name: str) -> list[str]:
        """Find co-authors of a given author."""
        author_id = f"author:{author_name.lower().strip()}"
        co_authors = set()

        # Find all papers by this author
        paper_urls = []
        for source, target, edge_data in self.graph.edges(data=True):
            if target == author_id and edge_data.get("type") == "authored_by":
                paper_urls.append(source)

        # Find all other authors of those papers
        for paper_url in paper_urls:
            for _, target, edge_data in self.graph.edges(paper_url, data=True):
                if edge_data.get("type") == "authored_by" and target != author_id:
                    node_data = self.graph.nodes[target]
                    co_authors.add(node_data.get("name", ""))

        return list(co_authors)

    # ── Stats ─────────────────────────────────────────────────────────────
    def get_stats(self) -> dict:
        """Summary statistics of the knowledge graph."""
        type_counts = {}
        for _, data in self.graph.nodes(data=True):
            t = data.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1

        edge_counts = {}
        for _, _, data in self.graph.edges(data=True):
            t = data.get("type", "unknown")
            edge_counts[t] = edge_counts.get(t, 0) + 1

        # Most connected papers
        paper_nodes = [n for n, d in self.graph.nodes(data=True) if d.get("type") == "paper"]
        top_papers = sorted(
            paper_nodes,
            key=lambda n: self.graph.degree(n),
            reverse=True,
        )[:5]

        return {
            "total_nodes":  self.graph.number_of_nodes(),
            "total_edges":  self.graph.number_of_edges(),
            "node_types":   type_counts,
            "edge_types":   edge_counts,
            "top_connected": [
                {"id": n, "label": self.graph.nodes[n].get("label", ""), "degree": self.graph.degree(n)}
                for n in top_papers
            ],
        }

    # ── Serialization for frontend ────────────────────────────────────────
    def to_json(self) -> dict:
        """Serialize the graph for frontend visualization (nodes + links format)."""
        nodes = []
        for node_id, data in self.graph.nodes(data=True):
            nodes.append({
                "id":    node_id,
                "label": data.get("label", str(node_id)[:30]),
                "type":  data.get("type", "unknown"),
                "year":  data.get("year"),
                "citation_count": data.get("citation_count"),
            })

        links = []
        for source, target, data in self.graph.edges(data=True):
            links.append({
                "source": source,
                "target": target,
                "type":   data.get("type", "unknown"),
            })

        return {
            "nodes": nodes,
            "links": links,
            "stats": self.get_stats(),
        }
