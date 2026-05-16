from pathlib import Path

from app.config import LOGS_LOCAL_ROOT


def main() -> None:
    root = Path(LOGS_LOCAL_ROOT)
    expected = list(root.glob("*/*.log"))
    print(f"Sample logs available: {len(expected)} files under {root}")


if __name__ == "__main__":
    main()
