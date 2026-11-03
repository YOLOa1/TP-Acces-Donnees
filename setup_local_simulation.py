from tp_acces_donnees.remote import RemoteConfig, RemoteDatabaseClient


def main() -> None:
    counts = RemoteDatabaseClient(RemoteConfig.local_simulation()).initialize_local_simulation()
    print(
        "Simulation ODBC locale prete : "
        f"{counts['operateurs']} operateur(s), "
        f"{counts['machines']} machine(s), "
        f"{counts['pieces']} piece(s)."
    )


if __name__ == "__main__":
    main()
