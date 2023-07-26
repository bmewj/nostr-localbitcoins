async def m001_initial(db):
    """
    Initial localbitcoinss table.
    """
    await db.execute(
        """
        CREATE TABLE localbitcoins.localbitcoinss (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            name TEXT NOT NULL
        );
    """
    )
