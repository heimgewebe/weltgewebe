from pathlib import Path

root = Path.cwd()

state = root / "apps/api/src/state.rs"
text = state.read_text()
old = '''    pub fn get(&self, id: &str) -> Option<&T> {
        self.items.get(id)
    }

    pub fn len(&self) -> usize {
'''
new = '''    pub fn get(&self, id: &str) -> Option<&T> {
        self.items.get(id)
    }

    pub fn remove(&mut self, id: &str) -> Option<T> {
        let removed = self.items.remove(id)?;
        self.order.retain(|existing_id| existing_id != id);
        Some(removed)
    }

    pub fn len(&self) -> usize {
'''
assert text.count(old) == 1, "unexpected OrderedCache get/len block"
text = text.replace(old, new)
old = '''        assert_eq!(cache.len(), 2);
        // Order must match original insertion of the unique ID
        let order: Vec<_> = cache.iter_in_order().collect();
        assert_eq!(order, vec![&"second".to_string(), &"item2".to_string()]);
    }
}
'''
new = '''        assert_eq!(cache.len(), 2);
        // Order must match original insertion of the unique ID
        let order: Vec<_> = cache.iter_in_order().collect();
        assert_eq!(order, vec![&"second".to_string(), &"item2".to_string()]);
    }

    #[test]
    fn test_ordered_cache_remove_updates_lookup_length_and_order() {
        let mut cache = OrderedCache::<String>::new();
        cache.insert("id1".to_string(), "first".to_string());
        cache.insert("id2".to_string(), "second".to_string());

        assert_eq!(cache.remove("id1"), Some("first".to_string()));
        assert_eq!(cache.get("id1"), None);
        assert_eq!(cache.len(), 1);
        assert_eq!(
            cache.iter_in_order().collect::<Vec<_>>(),
            vec![&"second".to_string()]
        );
        assert_eq!(cache.remove("missing"), None);
    }
}
'''
assert text.count(old) == 1, "unexpected state test tail"
state.write_text(text.replace(old, new))

routes = root / "apps/api/src/routes/mod.rs"
text = routes.read_text()
old = '''    edges::{create_edge, get_edge, list_edges},
    nodes::{create_node, get_node, list_nodes, patch_node},
'''
new = '''    edges::{create_edge, delete_edge, get_edge, list_edges, patch_edge},
    nodes::{create_node, delete_node, get_node, list_nodes, patch_node, replace_node},
'''
assert text.count(old) == 1, "unexpected route imports"
text = text.replace(old, new)
old = '''            get(get_node)
                .patch(patch_node)
                .route_layer(from_fn(require_write)),
'''
new = '''            get(get_node)
                .patch(patch_node)
                .put(replace_node)
                .delete(delete_node)
                .route_layer(from_fn(require_write)),
'''
assert text.count(old) == 1, "unexpected node route"
text = text.replace(old, new)
old = '''        .route("/edges/{id}", get(get_edge))
'''
new = '''        .route(
            "/edges/{id}",
            get(get_edge)
                .patch(patch_edge)
                .delete(delete_edge)
                .route_layer(from_fn(require_write)),
        )
'''
assert text.count(old) == 1, "unexpected edge route"
routes.write_text(text.replace(old, new))
