from app.rag.service import RagService


def main() -> None:
    result = RagService().reindex()
    print(f"Indexed {result['documents']} knowledge chunks using {result['backend']}.")


if __name__ == "__main__":
    main()
