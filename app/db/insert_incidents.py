from scripts.seed_incidents import seed_incidents


if __name__ == "__main__":
    print("Seeded incidents:", ", ".join(str(item) for item in seed_incidents()))
