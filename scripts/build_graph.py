"""Manual graph rebuild. Run: python -m scripts.build_graph"""
from src.workers.graph_builder import build_graph_relationships_impl


def main() -> None:
    summary = build_graph_relationships_impl()
    print(summary)


if __name__ == "__main__":
    main()
