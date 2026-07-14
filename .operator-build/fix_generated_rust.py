from pathlib import Path

root = Path.cwd()
for relative in ["apps/api/src/routes/nodes.rs", "apps/api/src/routes/edges.rs"]:
    path = root / relative
    text = path.read_text()
    text = text.replace('b"\n"', 'b"\\n"')
    path.write_text(text)

path = root / "apps/api/src/routes/edges.rs"
text = path.read_text()
old = "    io::{AsyncBufReadExt, AsyncReadExt, AsyncSeekExt, AsyncWriteExt, BufReader, SeekFrom},\n"
new = "    io::{\n        AsyncBufReadExt, AsyncReadExt, AsyncSeekExt, AsyncWriteExt, BufReader, BufWriter, SeekFrom,\n    },\n"
assert text.count(old) == 1
path.write_text(text.replace(old, new))
