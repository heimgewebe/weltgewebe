use std::{collections::BTreeSet, fs, path::PathBuf};

fn routes_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("src/routes")
}

const CSRF_COVERED_MUTATING_ROUTES: &[(&str, &str)] = &[
    ("POST", "/auth/session/refresh"),
    ("POST", "/auth/logout-all"),
    ("DELETE", "/auth/devices/:id"),
    ("PUT", "/auth/me/email"),
    ("POST", "/auth/step-up/magic-link/request"),
    ("POST", "/auth/step-up/magic-link/consume"),
    ("POST", "/auth/passkeys/register/options"),
    ("PATCH", "/nodes/:id"),
];

const CSRF_EXEMPT_MUTATING_ROUTES: &[(&str, &str)] = &[
    // Dev login is explicitly feature-gated and intentionally kept outside the CSRF policy.
    ("POST", "/auth/dev/login"),
    // Magic-link request/consume are pre-session or redirect-driven entry points with their own flow handling.
    ("POST", "/auth/magic-link/request"),
    ("POST", "/auth/magic-link/consume"),
    // Logout intentionally remains exempt so a sign-out action can be executed without the CSRF middleware path.
    ("POST", "/auth/logout"),
];

fn collect_declared_mutating_routes() -> BTreeSet<(String, String)> {
    let mut routes = BTreeSet::new();

    collect_route_sources(&routes_dir(), &mut routes);

    routes
}

fn collect_route_sources(dir: &PathBuf, routes: &mut BTreeSet<(String, String)>) {
    for entry in fs::read_dir(dir).expect("failed to read apps/api/src/routes") {
        let path = entry.expect("failed to read route entry").path();
        if path.is_dir() {
            collect_route_sources(&path, routes);
            continue;
        }

        if path.extension().and_then(|value| value.to_str()) != Some("rs") {
            continue;
        }

        let source = fs::read_to_string(&path).unwrap_or_else(|error| {
            panic!("failed to read route source {}: {}", path.display(), error)
        });
        routes.extend(collect_mutating_routes_from_source(&source));
    }
}

fn collect_mutating_routes_from_source(source: &str) -> BTreeSet<(String, String)> {
    let mut routes = BTreeSet::new();
    let mut cursor = 0;

    while let Some(route_start_rel) = source[cursor..].find(".route(") {
        let route_start = cursor + route_start_rel;
        let open_paren = route_start + ".route".len();
        let Some(route_end) = find_matching_paren(source, open_paren) else {
            break;
        };

        for route in extract_mutating_routes(&source[route_start..route_end]) {
            routes.insert(route);
        }

        cursor = route_end;
    }

    routes
}

fn find_matching_paren(source: &str, open_paren: usize) -> Option<usize> {
    let bytes = source.as_bytes();
    let mut depth = 0usize;

    for (index, byte) in bytes.get(open_paren..)?.iter().enumerate() {
        match byte {
            b'(' => depth += 1,
            b')' => {
                depth = depth.checked_sub(1)?;
                if depth == 0 {
                    return Some(open_paren + index + 1);
                }
            }
            _ => {}
        }
    }

    None
}

fn extract_mutating_routes(route_call: &str) -> Vec<(String, String)> {
    // This is a source-level guard, not a Rust parser.
    let Some(path_start) = route_call.find('"').map(|index| index + 1) else {
        return Vec::new();
    };
    let Some(path_end) = route_call[path_start..]
        .find('"')
        .map(|index| index + path_start)
    else {
        return Vec::new();
    };
    let path = route_call[path_start..path_end].to_string();

    let mut routes = Vec::new();
    for method in ["DELETE", "PUT", "PATCH", "POST"] {
        if route_call.contains(&format!("{}(", method.to_lowercase()))
            || route_call.contains(&format!("axum::routing::{}(", method.to_lowercase()))
        {
            routes.push((method.to_string(), path.clone()));
        }
    }

    routes
}

fn route_set(routes: &[(&str, &str)]) -> BTreeSet<(String, String)> {
    routes
        .iter()
        .map(|(method, path)| ((*method).to_string(), (*path).to_string()))
        .collect()
}

fn format_route_set(routes: &BTreeSet<(String, String)>) -> String {
    routes
        .iter()
        .map(|(method, path)| format!("{} {}", method, path))
        .collect::<Vec<_>>()
        .join(", ")
}

#[test]
fn csrf_mutating_route_drift_guard_matches_router_declarations() {
    let discovered_routes = collect_declared_mutating_routes();
    let covered_routes = route_set(CSRF_COVERED_MUTATING_ROUTES);
    let exempt_routes = route_set(CSRF_EXEMPT_MUTATING_ROUTES);
    let policy_routes = covered_routes
        .union(&exempt_routes)
        .cloned()
        .collect::<BTreeSet<_>>();

    let uncovered_routes = discovered_routes
        .difference(&policy_routes)
        .cloned()
        .collect::<BTreeSet<_>>();
    let stale_routes = policy_routes
        .difference(&discovered_routes)
        .cloned()
        .collect::<BTreeSet<_>>();

    assert!(
        uncovered_routes.is_empty(),
        "mutating route drift detected; add each new route to CSRF_COVERED_MUTATING_ROUTES or CSRF_EXEMPT_MUTATING_ROUTES: {}",
        format_route_set(&uncovered_routes)
    );

    assert!(
        stale_routes.is_empty(),
        "CSRF policy lists contain routes that are no longer declared: {}",
        format_route_set(&stale_routes)
    );
}
