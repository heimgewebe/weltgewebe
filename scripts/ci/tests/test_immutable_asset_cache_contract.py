"""Runtime contract for cache headers on immutable frontend assets."""

from __future__ import annotations

import http.client
import pathlib
import shutil
import socket
import subprocess
import tempfile
import time
import unittest


CACHE_VALUE = "public, max-age=31536000, immutable"
CADDYFILES = (
    "infra/caddy/Caddyfile.vps",
    "infra/caddy/Caddyfile.heim",
)


def _extract_block(source: str, marker: str) -> str:
    start = source.index(marker)
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"unterminated Caddy block: {marker}")


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _request(port: int, path: str) -> tuple[int, dict[str, str], bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        body = response.read()
        headers = {name.lower(): value for name, value in response.getheaders()}
        return response.status, headers, body
    finally:
        connection.close()


class ImmutableAssetCacheContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo = pathlib.Path(__file__).resolve().parents[3]

    def test_long_lived_cache_header_is_guarded_by_file_existence(self) -> None:
        for relative in CADDYFILES:
            with self.subTest(caddyfile=relative):
                source = (self.repo / relative).read_text(encoding="utf-8")
                block = _extract_block(source, "handle /_app/immutable/*")
                self.assertIn("@immutableAsset {", block)
                self.assertIn("file {", block)
                self.assertIn("root /srv/weltgewebe-web", block)
                self.assertIn("not path */", block)
                self.assertIn(
                    f'header @immutableAsset Cache-Control "{CACHE_VALUE}"',
                    block,
                )
                self.assertNotIn(
                    f'header Cache-Control "{CACHE_VALUE}"',
                    block,
                )

    @unittest.skipUnless(shutil.which("caddy"), "caddy binary required for runtime cache proof")
    def test_missing_immutable_asset_never_receives_positive_cache_header(self) -> None:
        for relative in CADDYFILES:
            with self.subTest(caddyfile=relative), tempfile.TemporaryDirectory() as tmp:
                root = pathlib.Path(tmp) / "web"
                asset = root / "_app" / "immutable" / "present.js"
                asset.parent.mkdir(parents=True)
                asset.write_text("export const present = true;\n", encoding="utf-8")
                (asset.parent / "directory").mkdir()

                source = (self.repo / relative).read_text(encoding="utf-8")
                block = _extract_block(source, "handle /_app/immutable/*")
                block = block.replace("/srv/weltgewebe-web", root.as_posix())
                port = _free_port()
                config = pathlib.Path(tmp) / "Caddyfile"
                config.write_text(
                    "{\n    admin off\n}\n\n"
                    f"http://127.0.0.1:{port} {{\n"
                    + "\n".join(f"    {line}" if line else "" for line in block.splitlines())
                    + "\n    respond 404\n}\n",
                    encoding="utf-8",
                )

                process = subprocess.Popen(
                    ["caddy", "run", "--config", str(config), "--adapter", "caddyfile"],
                    cwd=self.repo,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                try:
                    deadline = time.monotonic() + 5
                    while True:
                        try:
                            present = _request(port, "/_app/immutable/present.js")
                            break
                        except OSError:
                            if time.monotonic() >= deadline:
                                stderr = process.stderr.read() if process.stderr else ""
                                self.fail(f"caddy runtime did not become ready: {stderr}")
                            time.sleep(0.05)

                    self.assertEqual(present[0], 200)
                    self.assertEqual(present[1].get("cache-control"), CACHE_VALUE)
                    self.assertEqual(present[2], b"export const present = true;\n")

                    missing = _request(port, "/_app/immutable/missing.js")
                    self.assertEqual(missing[0], 404)
                    self.assertNotEqual(missing[1].get("cache-control"), CACHE_VALUE)

                    directory_root = _request(port, "/_app/immutable/")
                    self.assertNotEqual(directory_root[0], 200)
                    self.assertNotEqual(
                        directory_root[1].get("cache-control"), CACHE_VALUE
                    )

                    directory = _request(port, "/_app/immutable/directory")
                    self.assertNotEqual(directory[1].get("cache-control"), CACHE_VALUE)
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                    if process.stderr is not None:
                        process.stderr.close()


if __name__ == "__main__":
    unittest.main()
