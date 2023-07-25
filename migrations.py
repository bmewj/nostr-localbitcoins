async def m001_initial(db):
    """
    Initial localbitcoinss table.
    """
    await db.execute(
        """
        CREATE TABLE localbitcoins.localbitcoinss (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        );
    """
    )
