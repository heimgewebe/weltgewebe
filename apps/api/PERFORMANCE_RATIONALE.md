# Performance Rationale: O(1) Lookups for Nodes and Edges

## Issue
The original implementation of the API stored `Node` and `Edge` objects in `Vec` collections within the `ApiState`.
This resulted in $O(N)$ linear scans when looking up a specific node or edge by its unique `id`.
As the dataset grows, these operations become increasingly slow, impacting the responsiveness of endpoints such as `GET /nodes/:id`, `GET /edges/:id`, and `PATCH /nodes/:id`.

## Optimization
We are transitioning the in-memory cache for nodes and edges to use `HashMap<String, Node>` and `HashMap<String, Edge>` respectively, keyed by their `id`.
This change provides several performance benefits:
- **$O(1)$ Lookups:** Finding a node or edge by its ID now takes constant time on average, regardless of the collection size.
- **Efficient Updates:** In `patch_node`, updating the cache no longer requires a linear search to find the index of the element to replace.
- **Improved Data Integrity:** Using a `HashMap` inherently prevents duplicate IDs in the cache, reinforcing the "last-write-wins" policy during initial load.

## Impact
- `get_node`, `get_edge`, and participant detail lookups within `get_edge` are now measurably faster for large datasets.
- Cache updates in `patch_node` are optimized from $O(N)$ search and replace to $O(1)$ insertion.
- The change is functionally transparent to API consumers while providing a significant performance boost for read-heavy and update-heavy workloads.
