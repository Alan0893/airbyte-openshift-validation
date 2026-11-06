#!/usr/bin/env python3
"""Stage SEC quarterly ZIP members as raw TSV objects for Airbyte's S3 source."""

import argparse
import hashlib
import json
import os
import zipfile
from pathlib import Path


TABLES = ("sub", "num", "pre", "tag")


def sha256_member(archive: zipfile.ZipFile, member: str) -> str:
    digest = hashlib.sha256()
    with archive.open(member) as stream:
        while block := stream.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archives", type=Path, default=Path("data/seed/s3/financial-statements")
    )
    parser.add_argument("--bucket", default=os.environ.get("S3_BUCKET"))
    parser.add_argument("--prefix", default="financial-statements")
    parser.add_argument("--endpoint-url", default=os.environ.get("S3_ENDPOINT") or None)
    parser.add_argument("--region", default=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
    parser.add_argument(
        "--manifest-out",
        type=Path,
        default=Path("docs/evidence/financial-tsv-sha256.json"),
    )
    parser.add_argument("--manifest-only", action="store_true")
    args = parser.parse_args()

    prefix = args.prefix.strip("/")
    if not prefix:
        parser.error("--prefix must not be empty")
    if not args.manifest_only and not args.bucket:
        parser.error("--bucket or S3_BUCKET is required unless --manifest-only is set")
    archives = sorted(args.archives.glob("*.zip"))
    if not archives:
        parser.error(f"no quarterly ZIP archives found in {args.archives}")

    client = None
    if not args.manifest_only:
        import boto3
        from botocore.exceptions import ClientError

        client = boto3.client("s3", region_name=args.region, endpoint_url=args.endpoint_url)

    objects = []
    for archive_path in archives:
        quarter = archive_path.stem
        with zipfile.ZipFile(archive_path) as archive:
            for table in TABLES:
                member = f"{table}.txt"
                try:
                    size = archive.getinfo(member).file_size
                except KeyError as exc:
                    raise ValueError(f"{archive_path} is missing {member}") from exc
                key = f"{prefix}/{quarter}/{table}.tsv"
                digest = sha256_member(archive, member)
                objects.append({"key": key, "size_bytes": size, "sha256": digest})

                if client is None:
                    print(f"hashed {key} ({size} bytes)")
                    continue

                try:
                    current = client.head_object(Bucket=args.bucket, Key=key)
                except ClientError as exc:
                    if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") != 404:
                        raise
                    current = None
                if current and current["ContentLength"] == size and current.get("Metadata", {}).get("sha256") == digest:
                    print(f"already staged {key} ({size} bytes)")
                    continue

                with archive.open(member) as stream:
                    client.upload_fileobj(
                        stream,
                        args.bucket,
                        key,
                        ExtraArgs={"Metadata": {"sha256": digest}},
                    )
                uploaded = client.head_object(Bucket=args.bucket, Key=key)
                if uploaded["ContentLength"] != size or uploaded.get("Metadata", {}).get("sha256") != digest:
                    raise RuntimeError(f"uploaded object verification failed: {key}")
                print(f"staged {key} ({size} bytes)")

    manifest = {
        "source_prefix": f"{prefix}/",
        "file_count": len(objects),
        "total_bytes": sum(item["size_bytes"] for item in objects),
        "objects": objects,
    }
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {args.manifest_out}: {manifest['file_count']} files, {manifest['total_bytes']} bytes")


if __name__ == "__main__":
    main()
