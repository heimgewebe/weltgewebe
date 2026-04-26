use crate::auth::{accounts::AccountStore, role::Role};
use crate::state::ApiState;
use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    Json,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::{collections::HashMap, env, path::PathBuf};
use tokio::{
    fs::File,
    io::{AsyncBufReadExt, BufReader},
};
use uuid::Uuid;

const METERS_PER_DEGREE: f64 = 111_000.0;
const COS_LAT_FLOOR: f64 = 1e-3;

fn in_dir() -> PathBuf {
    env::var("GEWEBE_IN_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from(".gewebe/in"))
}

fn accounts_path() -> PathBuf {
    in_dir().join("demo.accounts.jsonl")
}

#[derive(Serialize, Clone, Debug)]
pub struct Location {
    pub lat: f64,
    pub lon: f64,
}

/// Public view of an Account.
/// STRICTLY does not contain the internal 'location' (residence).
/// Only exposes 'public_pos' which is calculated based on the account mode (verortet vs ron).
#[derive(Serialize, Deserialize, Debug, PartialEq, Clone)]
#[serde(rename_all = "lowercase")]
pub enum AccountMode {
    Verortet,
    Ron,
}
#[derive(Serialize, Clone, Debug)]
pub struct AccountPublic {
    pub id: String,
    #[serde(rename = "type")]
    pub kind: String,
    pub title: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub summary: Option<String>,

    // Privacy: 'location' field is intentionally omitted.
    // 'public_pos' is the only projected location for public consumption.
    #[serde(skip_serializing_if = "Option::is_none", rename = "public_pos")]
    pub public_pos: Option<Location>,

    pub mode: AccountMode,
    pub radius_m: u32,

    #[serde(default, skip_serializing)]
    pub disabled: bool,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub tags: Vec<String>,
}

#[derive(Clone, Debug)]
pub struct AccountInternal {
    pub public: AccountPublic,
    pub role: Role,
    pub email: Option<String>,
    /// Dedicated WebAuthn user identity for this account.
    /// This is NOT derived from `account_id` — it is an independent, opaque handle
    /// used exclusively by the WebAuthn protocol to identify the user.
    ///
    /// **Persistence:** read from the account data source when present. When absent
    /// (e.g. existing accounts loaded before this field was introduced), a fresh
    /// UUID v4 is generated at load time as a lazy backfill. This generated value
    /// is stable for the lifetime of the running process only. It becomes durable
    /// once written back to the data source — a prerequisite for `register/verify`
    /// that is not yet implemented.
    pub webauthn_user_id: Uuid,
}

/// Simple deterministic pseudo-random number generator based on ID
fn stable_hash(s: &str) -> u64 {
    let mut hash: u64 = 5381;
    for c in s.bytes() {
        hash = ((hash << 5).wrapping_add(hash)) + c as u64;
    }
    hash
}

/// Calculates the public position based on the real location and radius.
/// Uses a deterministic "jitter" based on the ID so the position doesn't jump around on every request.
fn calculate_jittered_pos(lat: f64, lon: f64, radius_m: u32, id: &str) -> Location {
    if radius_m == 0 {
        return Location { lat, lon };
    }

    // Seed the RNG with the ID
    let seed = stable_hash(id);

    // Generate two offsets in range [-1.0, 1.0] derived from seed
    // We mix bits to get different values for x and y
    let r1 = ((seed & 0xFFFF) as f64 / 65535.0) * 2.0 - 1.0;
    let r2 = (((seed >> 16) & 0xFFFF) as f64 / 65535.0) * 2.0 - 1.0;

    // Scale by radius (converted to degrees)
    // We simply use a square box jitter for simplicity in this minimal core.
    // A circle would be better but requires sin/cos and proper distance calc.
    // For visual obfuscation, this is sufficient "phantom world".
    let lat_offset = (r1 * radius_m as f64) / METERS_PER_DEGREE;

    // Near the poles cos(latitude) approaches 0 which would explode the offset or
    // even lead to division by zero. Clamp the denominator to a reasonable floor
    // so that the longitude offset remains bounded and plausible instead of
    // merely finite.
    let cos_lat = lat.to_radians().cos().max(COS_LAT_FLOOR);
    let lon_offset = (r2 * radius_m as f64) / (METERS_PER_DEGREE * cos_lat);

    let mut lon_jittered = (lon + lon_offset).rem_euclid(360.0);
    if lon_jittered > 180.0 {
        lon_jittered -= 360.0;
    }

    Location {
        lat: (lat + lat_offset).clamp(-90.0, 90.0),
        lon: lon_jittered,
    }
}

fn map_json_to_public_account(v: &Value) -> Option<AccountPublic> {
    let id = match v.get("id").and_then(|v| v.as_str()) {
        Some(s) => s.to_string(),
        None => {
            tracing::debug!("Skipping account with missing or invalid id");
            return None;
        }
    };

    let kind = v
        .get("type")
        .and_then(|v| v.as_str())
        .unwrap_or("garnrolle")
        .to_string();

    let title = v
        .get("title")
        .and_then(|v| v.as_str())
        .unwrap_or("Untitled")
        .to_string();

    let summary = v
        .get("summary")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string());

    let mut lat = None;
    let mut lon = None;

    if let Some(location_obj) = v.get("location") {
        lon = location_obj.get("lon").and_then(|val| {
            val.as_f64()
                .or_else(|| val.as_str().and_then(|s| s.parse().ok()))
        });
        lat = location_obj.get("lat").and_then(|val| {
            val.as_f64()
                .or_else(|| val.as_str().and_then(|s| s.parse().ok()))
        });
    }

    let mut radius_m = v.get("radius_m").and_then(|v| v.as_u64()).unwrap_or(0) as u32;

    // Legacy fallback mapping
    let has_ron_flag = v.get("ron_flag").and_then(|v| v.as_bool()).unwrap_or(false);
    let legacy_visibility = v.get("visibility").and_then(|v| v.as_str());

    let mode = v
        .get("mode")
        .and_then(|v| serde_json::from_value::<AccountMode>(v.clone()).ok())
        .or_else(|| {
            if kind == "ron" || has_ron_flag {
                Some(AccountMode::Ron)
            } else if let Some(vis) = legacy_visibility {
                match vis {
                    "private" => {
                        // Legacy private records had an individual residence but were not projected publicly.
                        // We map them to Verortet to preserve their ontological identity (they are not a collective RoN),
                        // but we will suppress their public_pos calculation below.
                        Some(AccountMode::Verortet)
                    }
                    "approximate" => {
                        if radius_m == 0 {
                            radius_m = 250;
                        }
                        Some(AccountMode::Verortet)
                    }
                    _ => Some(AccountMode::Verortet),
                }
            } else {
                // If neither mode, ron_flag, nor visibility exists, default safely
                if lat.is_some() && lon.is_some() {
                    Some(AccountMode::Verortet)
                } else {
                    Some(AccountMode::Ron)
                }
            }
        })
        .unwrap_or(AccountMode::Ron);

    // Validate requirements
    let (lat, lon) = match mode {
        AccountMode::Verortet => {
            if let (Some(la), Some(lo)) = (lat, lon) {
                (la, lo)
            } else {
                tracing::debug!(%id, "Skipping 'verortet' account missing exact location");
                return None;
            }
        }
        AccountMode::Ron => (0.0, 0.0), // RoN has no individual location
    };

    let disabled = v.get("disabled").and_then(|v| v.as_bool()).unwrap_or(false);

    let tags = v
        .get("tags")
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|x| x.as_str().map(String::from))
                .collect()
        })
        .unwrap_or_default();

    let public_pos = match mode {
        AccountMode::Ron => None, // RoN accounts have no individual public position.
        AccountMode::Verortet => {
            // Legacy compatibility: If this was explicitly a "private" account,
            // it retains its individual Verortet identity but its public position is suppressed.
            if legacy_visibility == Some("private") {
                None
            } else {
                Some(calculate_jittered_pos(lat, lon, radius_m, &id))
            }
        }
    };

    Some(AccountPublic {
        id,
        kind,
        title,
        summary,
        public_pos,
        mode,
        radius_m,
        disabled,
        tags,
    })
}

pub async fn load_all_accounts() -> AccountStore {
    let mut store = AccountStore::new();
    let path = accounts_path();

    let file = match File::open(&path).await {
        Ok(f) => f,
        Err(e) => {
            tracing::warn!(
                ?path,
                ?e,
                "Failed to open accounts file, returning empty map"
            );
            return store;
        }
    };

    let mut lines = BufReader::new(file).lines();
    while let Ok(Some(line)) = lines.next_line().await {
        let v: Value = match serde_json::from_str(&line) {
            Ok(v) => v,
            Err(_) => continue,
        };

        let role = v
            .get("role")
            .and_then(|v| v.as_str())
            .map(Role::from_str_lossy)
            .unwrap_or(Role::Gast);

        let email = v
            .get("email")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());

        // Read persisted webauthn_user_id if present; otherwise generate a new one.
        // NOTE: This generated ID is stable only for the lifetime of this process.
        // Once passkey registration is implemented (register-verify), the generated
        // webauthn_user_id MUST be persisted back to the account data source so that
        // registered passkeys remain bound to the correct identity across restarts.
        let webauthn_user_id = v
            .get("webauthn_user_id")
            .and_then(|v| v.as_str())
            .and_then(|s| Uuid::parse_str(s).ok())
            .unwrap_or_else(Uuid::new_v4);

        if let Some(public) = map_json_to_public_account(&v) {
            let account = AccountInternal {
                public,
                role,
                email,
                webauthn_user_id,
            };
            store.insert_unindexed(account);
        }
    }
    store.rebuild_email_index();
    store
}

pub async fn list_accounts(
    State(state): State<ApiState>,
    Query(params): Query<HashMap<String, String>>,
) -> Result<Json<Vec<AccountPublic>>, StatusCode> {
    let limit: usize = params
        .get("limit")
        .and_then(|s| s.parse().ok())
        .unwrap_or(100);
    let offset: usize = params
        .get("offset")
        .and_then(|s| s.parse().ok())
        .unwrap_or(0);

    let accounts = state.accounts.read().await;

    // BTreeMap iterates in ascending key order, so output is deterministic by account id.
    let accounts: Vec<AccountPublic> = accounts
        .iter()
        .skip(offset)
        .take(limit)
        .map(|(_id, internal)| internal.public.clone())
        .collect();

    Ok(Json(accounts))
}

pub async fn get_account(
    State(state): State<ApiState>,
    Path(id): Path<String>,
) -> Result<Json<AccountPublic>, StatusCode> {
    let accounts = state.accounts.read().await;
    if let Some(internal) = accounts.get(&id) {
        Ok(Json(internal.public.clone()))
    } else {
        Err(StatusCode::NOT_FOUND)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    /// Calculate circular distance between two longitude values
    fn lon_delta(a: f64, b: f64) -> f64 {
        let mut d = (a - b).abs();
        if d > 180.0 {
            d = 360.0 - d;
        }
        d
    }

    #[test]
    fn test_guard_public_view_never_leaks_location() {
        let input = json!({
            "id": "test-leak-guard",
            "type": "garnrolle",
            "title": "Leak Test",
            "location": { "lat": 53.5, "lon": 10.0 },
            "visibility": "public"
        });

        let account = map_json_to_public_account(&input).expect("Mapping failed");
        let output_value = serde_json::to_value(&account).expect("Serialization failed");

        // GUARD: The "location" field must NOT be present in the public JSON output.
        assert!(
            output_value.get("location").is_none(),
            "Public view MUST NOT contain 'location' field!"
        );

        // But public_pos MUST be present (as it is public)
        assert!(output_value.get("public_pos").is_some());
    }

    #[test]
    fn test_guard_private_hides_public_pos() {
        let input = serde_json::json!({
            "id": "test-private",
            "type": "garnrolle",
            "title": "Private Test",
            "location": { "lat": 53.5, "lon": 10.0 },
            "visibility": "private" // Legacy field
        });

        let account = map_json_to_public_account(&input).expect("Mapping failed");

        // GUARD: Legacy private accounts retain Verortet but suppress public_pos
        assert_eq!(account.mode, AccountMode::Verortet);
        assert!(account.public_pos.is_none());
    }

    #[test]
    fn test_guard_verortet_preserves_radius() {
        let input = serde_json::json!({
            "id": "test-verortet-zero",
            "type": "garnrolle",
            "title": "Verortet Zero",
            "location": { "lat": 53.5, "lon": 10.0 },
            "mode": "verortet",
            "radius_m": 0
        });

        let account = map_json_to_public_account(&input).expect("Mapping failed");

        assert_eq!(account.radius_m, 0);
        assert!(account.public_pos.is_some());
    }

    #[test]
    fn test_guard_unknown_visibility_defaults_to_public() {
        let input = json!({
            "id": "test-unknown-vis",
            "type": "garnrolle",
            "title": "Unknown Vis",
            "location": { "lat": 53.5, "lon": 10.0 },
            "visibility": "garbage_value"
        });

        let account = map_json_to_public_account(&input).expect("Mapping failed");

        assert_eq!(account.mode, AccountMode::Verortet);
        assert!(account.public_pos.is_some());
    }

    #[test]
    fn test_public_pos_remains_finite_near_poles() {
        let lat: f64 = 89.9999;
        let input = json!({
            "id": "polar-test",
            "type": "garnrolle",
            "title": "Polar Account",
            "location": { "lat": lat, "lon": 10.0 },
            "visibility": "approximate",
            "radius_m": 500,
        });

        let account = map_json_to_public_account(&input).expect("Mapping failed");
        let public_pos = account.public_pos.expect("public position present");

        let max_deg_lat = 500.0 / METERS_PER_DEGREE;
        // Correctly scale expected longitude jitter by 1/cos(lat)
        let cos_lat = lat.to_radians().cos().max(COS_LAT_FLOOR);
        let max_deg_lon = max_deg_lat / cos_lat;

        assert!(public_pos.lat.is_finite());
        assert!(public_pos.lon.is_finite());
        assert!(public_pos.lat <= 90.0 && public_pos.lat >= -90.0);
        assert!(public_pos.lon <= 180.0 && public_pos.lon >= -180.0);
        assert!(
            (public_pos.lat - lat).abs() <= max_deg_lat + 1e-6,
            "lat jitter exceeded expected bound"
        );
        assert!(
            lon_delta(public_pos.lon, 10.0) <= max_deg_lon + 1e-6,
            "lon jitter exceeded expected bound"
        );
    }

    #[test]
    fn test_public_pos_remains_finite_near_south_pole() {
        let lat: f64 = -89.9999;
        let input = json!({
            "id": "south-polar-test",
            "type": "garnrolle",
            "title": "South Polar Account",
            "location": { "lat": lat, "lon": 10.0 },
            "visibility": "approximate",
            "radius_m": 500,
        });

        let account = map_json_to_public_account(&input).expect("Mapping failed");
        let public_pos = account.public_pos.expect("public position present");

        let max_deg_lat = 500.0 / METERS_PER_DEGREE;
        // Correctly scale expected longitude jitter by 1/cos(lat)
        let cos_lat = lat.to_radians().cos().max(COS_LAT_FLOOR);
        let max_deg_lon = max_deg_lat / cos_lat;

        assert!(public_pos.lat.is_finite());
        assert!(public_pos.lon.is_finite());
        assert!(public_pos.lat <= 90.0 && public_pos.lat >= -90.0);
        assert!(public_pos.lon <= 180.0 && public_pos.lon >= -180.0);
        assert!(
            (public_pos.lat - lat).abs() <= max_deg_lat + 1e-6,
            "lat jitter exceeded expected bound"
        );
        assert!(
            lon_delta(public_pos.lon, 10.0) <= max_deg_lon + 1e-6,
            "lon jitter exceeded expected bound"
        );
    }

    #[test]
    fn test_jitter_scaling_at_high_latitudes() {
        // At 60 degrees latitude, cos(60) = 0.5.
        // A radius of 111km (1 deg lat) should result in approx 2 deg longitude jitter max.
        // Since we scale by 1/cos(lat), the longitude jitter range should be [-2.0, 2.0] degrees.
        // If the code incorrectly clamps to 1 deg (max_deg), the max observed will be ~1.0.

        let radius_m = 111_000;
        let lat = 60.0;
        let max_deg = radius_m as f64 / METERS_PER_DEGREE; // ~1.0 degree

        // We iterate through many IDs to find the maximum extent of the jitter
        let mut max_observed = 0.0;

        for i in 0..10000 {
            // Use simple varying string for hash distribution
            let id = i.to_string();
            let pos = calculate_jittered_pos(lat, 0.0, radius_m, &id);
            let d_lon = pos.lon.abs();

            if d_lon > max_observed {
                max_observed = d_lon;
            }
        }

        // Assert that we observed a jitter significantly larger than max_deg.
        // Theoretical max is 2.0 * max_deg. We check for > 1.2 to be robust against hash distribution variance
        // while still proving that the value is not clamped to 1.0.
        assert!(
            max_observed > max_deg * 1.2,
            "Longitude jitter should scale with latitude. Expected > {}, got max {}",
            max_deg * 1.2,
            max_observed
        );
    }

    #[test]
    fn test_jitter_wraparound() {
        // Test that longitude wraps correctly across the dateline (180/-180)
        let radius_m = 500_000; // ~5 degrees at equator
        let lat = 0.0;
        let lon = 179.0;

        // We need a specific ID that pushes longitude POSITIVE (East)
        // lon (179) + offset (> 1) should wrap to negative (e.g. -179)

        let mut wrapped = false;

        for i in 0..1000 {
            let id = format!("test-wrap-{}", i);
            let pos = calculate_jittered_pos(lat, lon, radius_m, &id);

            // If we wrapped, pos.lon should be negative (e.g. -178, -179)
            // Original is 179.
            if pos.lon < 0.0 {
                wrapped = true;
                // Verify it's valid longitude
                assert!(pos.lon >= -180.0);
                assert!(pos.lon <= 180.0);
                break;
            }
        }

        assert!(wrapped, "Jitter should be able to wrap around the dateline");
    }
}

#[cfg(test)]
mod additional_tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_verortet_without_location_fails() {
        let input = json!({
            "id": "test-verortet-no-loc",
            "type": "garnrolle",
            "title": "No Loc",
            "mode": "verortet",
        });

        let account = map_json_to_public_account(&input);
        assert!(
            account.is_none(),
            "Verortet account without location must fail mapping"
        );
    }

    #[test]
    fn test_ron_without_location_succeeds() {
        let input = serde_json::json!({
            "id": "test-ron-no-loc",
            "type": "ron",
            "title": "No Loc Ron",
            "mode": "ron",
        });

        let account =
            map_json_to_public_account(&input).expect("Ron without location should succeed");
        assert_eq!(account.mode, AccountMode::Ron);
        assert!(account.public_pos.is_none());
    }

    #[test]
    fn test_legacy_type_ron_maps_correctly() {
        let input = json!({
            "id": "test-legacy-type-ron",
            "type": "ron",
            "title": "Legacy Type Ron",
            // Notice: no "mode" field here
        });

        let account = map_json_to_public_account(&input).expect("Mapping failed");
        assert_eq!(account.mode, AccountMode::Ron);
        assert!(account.public_pos.is_none());
    }

    #[test]
    fn test_legacy_ron_flag_maps_correctly() {
        let input = json!({
            "id": "test-legacy-ron-flag",
            "type": "garnrolle",
            "title": "Legacy Ron Flag",
            "ron_flag": true
            // Notice: no "mode" field here
        });

        let account = map_json_to_public_account(&input).expect("Mapping failed");
        assert_eq!(account.mode, AccountMode::Ron);
        assert!(account.public_pos.is_none());
    }
}
