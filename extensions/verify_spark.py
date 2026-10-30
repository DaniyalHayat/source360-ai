import json
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from extensions.databricks.spend_cleaning import clean_spend
from source360.database import read


def main():
    spark = (
        SparkSession.builder.master("local[2]")
        .appName("source360-parity")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    raw = Path("data/raw").resolve()
    po = (
        spark.read.option("header", True)
        .option("inferSchema", True)
        .csv(str(raw / "erp_purchase_orders.csv"))
    )
    suppliers = (
        spark.read.option("header", True).option("inferSchema", True).csv(str(raw / "supplier_portal.csv"))
    )
    clean = clean_spend(po, suppliers).cache()
    count = clean.count()
    total = clean.agg(F.sum("extended_spend_usd")).first()[0]
    reference = read("fct_spend")
    assert count == len(reference)
    assert abs(total - float(reference.extended_spend_usd.sum())) < 0.01
    result = {
        "spark_version": spark.version,
        "master": "local[2]",
        "raw_rows": po.count(),
        "published_rows": count,
        "spend_usd": total,
        "python_parity": True,
        "distributed_cloud_execution": False,
    }
    Path("docs/spark-verification.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
    spark.stop()


if __name__ == "__main__":
    main()
