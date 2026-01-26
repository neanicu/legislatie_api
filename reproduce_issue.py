from legislatie_client import LegislatieClient
import sys


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    client = LegislatieClient()

    print("--- Strategy 1: Numar=664, An=2019 ---")
    results1 = client.search(numar="664", an="2019", rezultate_pagina=100)
    print(f"Found {len(results1)} results.")
    for r in results1:
        print(f"  [{r['DataVigoare']}] {r['Titlu']} ({r['Numar']})")

    print("\n--- Strategy 2: Titlu='Decizia nr. 664' ---")
    results2 = client.search(titlu="Decizia nr. 664", an="2019", rezultate_pagina=100)
    print(f"Found {len(results2)} results.")

    print("\n--- Strategy 3: Text includes '29 octombrie 2019' ---")
    results3 = client.search(text="29 octombrie 2019", rezultate_pagina=10)
    print(f"Found {len(results3)} results.")


if __name__ == "__main__":
    main()
