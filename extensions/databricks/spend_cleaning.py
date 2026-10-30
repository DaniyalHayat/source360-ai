from pyspark.sql import functions as F


def clean_spend(po, supplier):
    aliases = supplier.select("supplier_id", F.lower(F.trim("canonical_name")).alias("supplier_key")).union(
        supplier.select("supplier_id", F.lower(F.trim("alias")).alias("supplier_key"))
    )
    fx = (
        F.when(F.col("currency") == "USD", 1.0)
        .when(F.col("currency") == "EUR", 1.08)
        .when(F.col("currency") == "GBP", 1.27)
    )
    return (
        po.withColumn("supplier_key", F.lower(F.trim("supplier_raw")))
        .join(aliases, "supplier_key", "left")
        .withColumn("fx_rate_usd", fx)
        .filter(
            (F.col("quantity") > 0)
            & (F.col("unit_price_local") > 0)
            & F.col("supplier_id").isNotNull()
            & F.col("fx_rate_usd").isNotNull()
        )
        .withColumn(
            "extended_spend_usd", F.col("quantity") * F.col("unit_price_local") * F.col("fx_rate_usd")
        )
    )
