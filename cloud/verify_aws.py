import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path


def aws(*args):
    result = subprocess.run(["aws", *args, "--output", "json"], capture_output=True, text=True, check=True)
    return json.loads(result.stdout) if result.stdout.strip() else {}


def main(region):
    root = Path(__file__).resolve().parents[1]
    template = root / "cloud/raw-zone.json"
    identity = aws("sts", "get-caller-identity")
    name = "source360-synthetic-verification"
    aws(
        "cloudformation",
        "validate-template",
        "--template-body",
        "file://" + str(template),
        "--region",
        region,
    )
    aws(
        "cloudformation",
        "create-stack",
        "--stack-name",
        name,
        "--template-body",
        "file://" + str(template),
        "--region",
        region,
    )
    buckets = []
    receipt = {
        "region": region,
        "stack": name,
        "synthetic_only": True,
        "maximum_budget_usd": 5,
        "budget_is_not_a_hard_billing_cap": True,
    }
    try:
        aws("cloudformation", "wait", "stack-create-complete", "--stack-name", name, "--region", region)
        stack = aws("cloudformation", "describe-stacks", "--stack-name", name, "--region", region)["Stacks"][
            0
        ]
        outputs = {o["OutputKey"]: o["OutputValue"] for o in stack["Outputs"]}
        buckets = [outputs["RawBucket"], outputs["LogBucket"]]
        for bucket in buckets:
            assert bucket.startswith(name + "-")
        source = root / "data/raw/manifest.json"
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        aws(
            "s3api",
            "put-object",
            "--bucket",
            buckets[0],
            "--key",
            "synthetic/manifest.json",
            "--body",
            str(source),
            "--server-side-encryption",
            "AES256",
            "--region",
            region,
        )
        head = aws(
            "s3api",
            "head-object",
            "--bucket",
            buckets[0],
            "--key",
            "synthetic/manifest.json",
            "--region",
            region,
        )
        assert head["ServerSideEncryption"] == "AES256"
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "manifest.json"
            aws(
                "s3api",
                "get-object",
                "--bucket",
                buckets[0],
                "--key",
                "synthetic/manifest.json",
                str(target),
                "--region",
                region,
            )
            assert hashlib.sha256(target.read_bytes()).hexdigest() == digest
        block = aws("s3api", "get-public-access-block", "--bucket", buckets[0], "--region", region)
        assert all(block["PublicAccessBlockConfiguration"].values())
        receipt.update(
            upload_download_sha256_verified=True,
            encryption_verified=True,
            public_access_block_verified=True,
            versioning=aws("s3api", "get-bucket-versioning", "--bucket", buckets[0], "--region", region)[
                "Status"
            ],
            uploaded_bytes=source.stat().st_size,
            account_identity_verified=bool(identity["Account"]),
        )
    finally:
        for bucket in buckets:
            objects = aws("s3api", "list-object-versions", "--bucket", bucket, "--region", region)
            versions = [
                {"Key": v["Key"], "VersionId": v["VersionId"]}
                for k in ["Versions", "DeleteMarkers"]
                for v in objects.get(k, [])
            ]
            if versions:
                aws(
                    "s3api",
                    "delete-objects",
                    "--bucket",
                    bucket,
                    "--delete",
                    json.dumps({"Objects": versions}),
                    "--region",
                    region,
                )
        aws("cloudformation", "delete-stack", "--stack-name", name, "--region", region)
        aws("cloudformation", "wait", "stack-delete-complete", "--stack-name", name, "--region", region)
        receipt["stack_cleanup_verified"] = True
        (root / "docs/aws-verification.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="us-east-2")
    main(parser.parse_args().region)
