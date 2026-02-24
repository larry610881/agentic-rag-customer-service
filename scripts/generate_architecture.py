"""
產生系統架構圖 — 使用 Python diagrams 套件

安裝：
  Windows:  winget install Graphviz.Graphviz && pip install diagrams
  macOS:    brew install graphviz && pip install diagrams
  Linux:    sudo apt install graphviz && pip install diagrams

執行：
  python scripts/generate_architecture.py

產出：
  docs/images/architecture_diagrams.png
"""

from diagrams import Cluster, Diagram, Edge
from diagrams.onprem.database import MySQL
from diagrams.onprem.inmemory import Redis
from diagrams.onprem.client import User
from diagrams.programming.framework import FastAPI, React
from diagrams.programming.language import Python, TypeScript
from diagrams.generic.database import SQL
from diagrams.generic.compute import Rack
from diagrams.generic.storage import Storage
from diagrams.saas.chat import Line

graph_attr = {
    "bgcolor": "white",
    "pad": "0.5",
    "fontsize": "16",
    "fontname": "Helvetica",
    "splines": "spline",
    "nodesep": "0.8",
    "ranksep": "1.0",
}

node_attr = {
    "fontsize": "12",
    "fontname": "Helvetica",
}

edge_attr = {
    "color": "#64748b",
    "fontsize": "10",
    "fontname": "Helvetica",
}

with Diagram(
    "Agentic RAG Customer Service",
    filename="docs/images/architecture_diagrams",
    show=False,
    direction="TB",
    graph_attr=graph_attr,
    node_attr=node_attr,
    edge_attr=edge_attr,
    outformat="png",
):
    # --- Clients ---
    with Cluster("Clients", graph_attr={"bgcolor": "#dbeafe", "style": "rounded"}):
        browser = User("Browser")
        line_user = Line("LINE App")

    # --- Frontend ---
    with Cluster(
        "Frontend — Next.js 15 App Router",
        graph_attr={"bgcolor": "#dcfce7", "style": "rounded"},
    ):
        nextjs = React("App Router\nChat · KB · Bots")
        state = TypeScript("Zustand\nTanStack Query")
        ui = React("shadcn/ui\nTailwind CSS")

    # --- Backend ---
    with Cluster(
        "Backend — FastAPI + DDD 4-Layer",
        graph_attr={"bgcolor": "#fef9c3", "style": "rounded"},
    ):
        api = FastAPI("API Routers\nREST + SSE")

        with Cluster(
            "Domain Layer — 5 Bounded Contexts",
            graph_attr={"bgcolor": "#fff7ed", "style": "rounded"},
        ):
            tenant = Python("Tenant")
            knowledge = Python("Knowledge")
            rag = Python("RAG")
            conversation = Python("Conversation")
            agent = Python("Agent")

    # --- AI Pipeline ---
    with Cluster(
        "AI Pipeline",
        graph_attr={"bgcolor": "#f3e8ff", "style": "rounded"},
    ):
        langgraph = Rack("LangGraph\nOrchestrator")

        with Cluster("Multi-Agent Workers"):
            main_worker = Rack("Main Worker")
            refund_worker = Rack("Refund Worker")
            rag_tool = Rack("RAG Tool")

    # --- Data Layer ---
    with Cluster(
        "Data Layer",
        graph_attr={"bgcolor": "#e0e7ff", "style": "rounded"},
    ):
        mysql = MySQL("MySQL 8")
        qdrant = Storage("Qdrant\nVector DB")
        redis = Redis("Redis")

    # --- External Services ---
    with Cluster(
        "External Services",
        graph_attr={"bgcolor": "#fce7f3", "style": "rounded"},
    ):
        openai = Rack("OpenAI / Azure\nLLM + Embedding")
        line_api = Line("LINE API")

    # === Connections ===

    # Client → Frontend
    browser >> Edge(label="HTTP/SSE") >> nextjs
    nextjs - state - ui

    # Frontend → Backend
    nextjs >> Edge(label="REST + SSE") >> api

    # LINE → Backend
    line_user >> Edge(label="Webhook") >> api

    # Backend → Domain
    api >> [tenant, knowledge, rag, conversation, agent]

    # Domain → AI
    agent >> langgraph
    rag >> langgraph

    # AI Pipeline internal
    langgraph >> [main_worker, refund_worker, rag_tool]

    # AI → External
    langgraph >> Edge(label="Generate\nEmbed") >> openai
    api >> Edge(label="Reply") >> line_api

    # Domain → Data
    api >> Edge(label="Read/Write") >> mysql
    api >> Edge(label="Vector Search") >> qdrant
    api >> Edge(label="Cache") >> redis

    print("Generated: docs/images/architecture_diagrams.png")
