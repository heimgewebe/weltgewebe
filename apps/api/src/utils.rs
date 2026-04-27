use std::env;
use std::path::PathBuf;

pub fn in_dir() -> PathBuf {
    env::var("GEWEBE_IN_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from(".gewebe/in"))
}

pub fn nodes_path() -> PathBuf {
    in_dir().join("demo.nodes.jsonl")
}

pub fn edges_path() -> PathBuf {
    in_dir().join("demo.edges.jsonl")
}
