#!/usr/bin/env python3
"""Восстановить ровно QASPER v0.3 из официального архива с SHA-256."""

import hashlib
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "sources"
URL = "https://qasper-dataset.s3.us-west-2.amazonaws.com/qasper-train-dev-v0.3.tgz"
ARCHIVE_SHA256 = "a28fdf966db827bcee3d873107d6b6669864fb7ca8fbf73a192f5e39191bdb5a"
FILES = {
    "qasper-train-v0.3.json": "9458bfe76074a8fa8d1685af02bcc73537aa6d338ad20591dfaff1946bc88bf4",
    "qasper-dev-v0.3.json": "2ae7ee62a65b1c4225791c70de80c2aad4e8998cf1fd4f09a53103db4f21af93",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    SOURCE.mkdir(parents=True, exist_ok=True)
    if all((SOURCE / name).is_file() and sha256(SOURCE / name) == checksum for name, checksum in FILES.items()):
        print("QASPER v0.3 уже загружен и проверен")
        return
    with tempfile.TemporaryDirectory() as folder:
        archive = Path(folder) / "qasper.tgz"
        with urllib.request.urlopen(URL, timeout=60) as response, archive.open("wb") as output:
            shutil.copyfileobj(response, output)
        if sha256(archive) != ARCHIVE_SHA256:
            raise ValueError("SHA-256 архива QASPER не совпадает")
        with tarfile.open(archive, "r:gz") as package:
            for name, checksum in FILES.items():
                member = package.extractfile(name)
                if member is None:
                    raise ValueError(f"в архиве нет {name}")
                target = SOURCE / name
                with target.open("wb") as output:
                    shutil.copyfileobj(member, output)
                if sha256(target) != checksum:
                    raise ValueError(f"SHA-256 файла {name} не совпадает")
    print("QASPER v0.3 загружен и проверен; выполните `make repro`")


if __name__ == "__main__":
    main()
