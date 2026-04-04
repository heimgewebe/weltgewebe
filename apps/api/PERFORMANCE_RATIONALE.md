# Performance Rationale: O(1) Lookups for Nodes and Edges

## Issue
The original implementation of the API stored `Node` and `Edge` objects in `Vec` collections within the `ApiState`.
This resulted in $O(N)$ linear scans when looking up a specific node or edge by its unique `id` (e.g., in `get_node`, `get_edge`, and `patch_node`).
As the dataset grows, these operations increase in cost relative to the number of elements in the collection.

## Optimization: Ordered Cache (Fast Lookup + Stable Order)
To optimize these hotpaths without compromising the stability of API list responses, we have transitioned the in-memory cache to use a hybrid `OrderedCache` structure:
- **$O(1)$ Lookups:** A `HashMap<String, T>` enables constant-time average retrieval for individual nodes and edges by their `id`.
- **Stable Order:** A `Vec<String>` maintains the original load/insertion order of IDs, ensuring that `list_nodes` and `list_edges` remain deterministic and consistent with previous versions.
- **Efficient Updates:** In `patch_node`, updating the cache now targets the map entry directly, avoiding a linear search for the element's index.

## Impact & Evidence
- **Asymptotic Improvement:** Theoretical lookup and update complexity is reduced from $O(N)$ to average $O(1)$.
- **Semantic Stability:** Unlike a standard `HashMap`, this approach preserves the implicit API contract of stable list ordering by separating retrieval from iteration.
- **Measurability:** While full end-to-end performance benchmarks were not conducted in this development iteration due to environment constraints, the asymptotic complexity reduction makes improved lookup performance expected as graph size grows, while real-world gains remain workload-dependent.
- **Data Integrity:** The "last-write-wins" policy for duplicate IDs is now enforced explicitly and verified via unit tests to ensure cache consistency.
