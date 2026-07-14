use super::{
    domain_write_guard::reject_account_create_unless_writable,
    query::{
        cursor_page, parse_cursor_params, parse_usize_param, validate_cursor_limit, ListResponse,
        MAX_PAGE_SIZE,
    },
};
use crate::auth::{accounts::AccountStore, role::Role};
use crate::config::DomainAccountWriteSource;
use crate::domain_db::{
    insert_account_from_jsonl_record, load_account_profile_from_postgres,
    update_account_profile_in_postgres, AccountProfileUpdate, AccountProfileUpdateError,
    AccountWriteError,
};
use crate::middleware::auth::AuthContext;
use crate::state::ApiState;
use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    Extension, Json,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{
    collections::{HashMap, HashSet},
    env,
    path::PathBuf,
};
use tokio::{
    fs::{File, OpenOptions},
    io::{AsyncBufReadExt, AsyncWriteExt, BufReader},
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

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct Location {
    pub lat: f64,
    pub lon: f64,
}

/// Public view of an Account.
/// STRICTLY does not contain the internal exact `location` (residence).
/// `map_state` and `public_pos` express visibility without creating a second
/// identity type. Legacy `ron`/`mode` fields are accepted only by the mapper.
#[derive(Serialize, Deserialize, Debug, PartialEq, Clone, Copy)]
#[serde(rename_all = "snake_case")]
pub enum GarnrolleMapState {
    NotOnMap,
    Exact,
    Radius,
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

    pub map_state: GarnrolleMapState,
    pub radius_m: u32,

    #[serde(default, skip_serializing)]
    pub disabled: bool,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub tags: Vec<String>,
}

#[derive(Serialize, Clone, Debug, PartialEq)]
pub struct AccountNodeRelation {
    pub node_id: String,
    pub node_title: String,
    pub node_kind: String,
    pub edge_kind: String,
}

#[derive(Serialize, Clone, Debug, PartialEq)]
pub struct AccountActivity {
    pub date: String,
    pub event: String,
}

#[derive(Serialize, Clone, Debug)]
pub struct AccountDetails {
    #[serde(flatten)]
    pub account: AccountPublic,
    pub nodes: Vec<AccountNodeRelation>,
    pub activity: Vec<AccountActivity>,
}

#[derive(Serialize, Clone, Debug, PartialEq)]
pub struct OwnGarnrolleProfile {
    pub id: String,
    pub title: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub summary: Option<String>,
    pub tags: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub address: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub location: Option<Location>,
    pub map_state: GarnrolleMapState,
    pub radius_m: u32,
}

#[derive(Deserialize, Debug)]
#[serde(deny_unknown_fields)]
pub struct UpdateOwnGarnrolleRequest {
    pub title: String,
    #[serde(default)]
    pub summary: Option<String>,
    #[serde(default)]
    pub tags: Vec<String>,
    #[serde(default)]
    pub address: Option<String>,
    pub map_state: GarnrolleMapState,
    #[serde(default)]
    pub radius_m: Option<u32>,
    #[serde(default)]
    pub location: Option<Location>,
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

pub(crate) fn map_json_to_public_account(v: &Value) -> Option<AccountPublic> {
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

    // Legacy compatibility is read-only. Old `type=ron`, `mode=ron` or
    // `ron_flag=true` records become an ordinary Garnrolle that is not on the
    // public map. No location is invented and no private position is exposed.
    let has_ron_flag = v.get("ron_flag").and_then(|v| v.as_bool()).unwrap_or(false);
    let legacy_mode = v.get("mode").and_then(|v| v.as_str());
    let explicit_map_state = v.get("map_state").and_then(|v| v.as_str());
    if let Some(state) = explicit_map_state {
        if !matches!(state, "not_on_map" | "exact" | "radius") {
            tracing::warn!(%id, %state, "rejecting account with invalid map_state");
            return None;
        }
    }
    let legacy_visibility = v.get("visibility").and_then(|v| v.as_str());
    if legacy_visibility == Some("approximate") && radius_m == 0 {
        radius_m = 250;
    }

    let legacy_not_on_map = kind == "ron"
        || has_ron_flag
        || legacy_mode == Some("ron")
        || legacy_visibility == Some("private")
        || v.get("suppress_public_pos")
            .and_then(|value| value.as_bool())
            .unwrap_or(false);

    let map_state = if legacy_not_on_map
        || explicit_map_state == Some("not_on_map")
        || lat.is_none()
        || lon.is_none()
    {
        GarnrolleMapState::NotOnMap
    } else if explicit_map_state == Some("radius")
        || radius_m > 0
        || legacy_visibility == Some("approximate")
    {
        GarnrolleMapState::Radius
    } else {
        GarnrolleMapState::Exact
    };

    if map_state == GarnrolleMapState::NotOnMap {
        radius_m = 0;
    }

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

    let public_pos = match (map_state, lat, lon) {
        (GarnrolleMapState::Exact | GarnrolleMapState::Radius, Some(lat), Some(lon)) => {
            Some(calculate_jittered_pos(lat, lon, radius_m, &id))
        }
        _ => None,
    };

    Some(AccountPublic {
        id,
        kind: "garnrolle".to_string(),
        title,
        summary,
        public_pos,
        map_state,
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
) -> Result<Json<ListResponse<AccountPublic>>, StatusCode> {
    let limit: usize = parse_usize_param(&params, "limit", 100)?.min(MAX_PAGE_SIZE);
    let (cursor_mode, after_id) = parse_cursor_params(&params)?;
    validate_cursor_limit(cursor_mode, limit)?;

    let accounts = state.accounts.read().await;

    if cursor_mode {
        // The AccountStore is a BTreeMap (already id-ascending); cursor_page
        // re-affirms the stable id-ascending contract shared by all cursor
        // endpoints and projects each account to its public view.
        let refs: Vec<&AccountInternal> = accounts.iter().map(|(_id, internal)| internal).collect();
        let page = cursor_page(
            refs,
            limit,
            after_id.as_deref(),
            |internal: &AccountInternal| internal.public.id.as_str(),
            |internal: &AccountInternal| internal.public.clone(),
        );
        Ok(Json(ListResponse::Cursor(page)))
    } else {
        let offset: usize = parse_usize_param(&params, "offset", 0)?;
        // BTreeMap iterates in ascending key order, so output is deterministic by account id.
        let accounts: Vec<AccountPublic> = accounts
            .iter()
            .skip(offset)
            .take(limit)
            .map(|(_id, internal)| internal.public.clone())
            .collect();

        Ok(Json(ListResponse::Legacy(accounts)))
    }
}

pub async fn get_account(
    State(state): State<ApiState>,
    Path(id): Path<String>,
) -> Result<Json<AccountDetails>, StatusCode> {
    // Clone the public profile before reading the relationship caches so this
    // endpoint never holds several state locks at once.
    let account = {
        let accounts = state.accounts.read().await;
        accounts
            .get(&id)
            .map(|internal| internal.public.clone())
            .ok_or(StatusCode::NOT_FOUND)?
    };

    // Fäden are the source of truth for which Knoten belong to a Garnrolle.
    // Both directions are accepted, but a raw id match is insufficient: an
    // explicitly node-typed endpoint must never be projected as an account.
    // Missing legacy type metadata remains readable; newly created edges always
    // carry explicit validated types.
    let related_edges = {
        let edges = state.edges.read().await;
        edges
            .iter_in_order()
            .filter(|edge| {
                (edge.source_id == id
                    && matches!(edge.source_type.as_deref(), Some("account") | None))
                    || (edge.target_id == id
                        && matches!(edge.target_type.as_deref(), Some("account") | None))
            })
            .cloned()
            .collect::<Vec<_>>()
    };

    let node_cache = state.nodes.read().await;
    let mut seen_nodes = HashSet::new();
    let mut nodes = Vec::new();
    let mut activity = Vec::new();

    for edge in related_edges {
        let account_is_source = edge.source_id == id;
        let (related_id, related_type) = if account_is_source {
            (edge.target_id.as_str(), edge.target_type.as_deref())
        } else {
            (edge.source_id.as_str(), edge.source_type.as_deref())
        };
        if !matches!(related_type, Some("node") | None) {
            continue;
        }
        let Some(node) = node_cache.get(related_id) else {
            continue;
        };

        if seen_nodes.insert(node.id.clone()) {
            nodes.push(AccountNodeRelation {
                node_id: node.id.clone(),
                node_title: node.title.clone(),
                node_kind: node.kind.clone(),
                edge_kind: edge.edge_kind.clone(),
            });
        }

        if let Some(date) = edge.created_at.clone() {
            let event = if account_is_source {
                format!("Hat den Knoten \"{}\" geknüpft.", node.title)
            } else {
                format!(
                    "Wurde über einen Faden mit dem Knoten \"{}\" verknüpft.",
                    node.title
                )
            };
            activity.push(AccountActivity { date, event });
        }
    }

    nodes.sort_by(|left, right| {
        left.node_title
            .cmp(&right.node_title)
            .then_with(|| left.node_id.cmp(&right.node_id))
    });
    activity.sort_by(|left, right| right.date.cmp(&left.date));

    Ok(Json(AccountDetails {
        account,
        nodes,
        activity,
    }))
}

/// Parse a JSON value as f64, accepting either a number or a numeric string.
fn json_f64(v: &Value) -> Option<f64> {
    v.as_f64()
        .or_else(|| v.as_str().and_then(|s| s.parse().ok()))
}

/// Append a single account record as a JSONL line. Durability via fsync.
/// Callers MUST hold `state.accounts_persist` to serialize writes.
///
/// `pub(crate)` so the auth auto-provisioning path (`routes::auth`) can persist
/// through the exact same durable append used by the operator-facing
/// `POST /accounts` create path — no second, divergent JSONL writer.
pub(crate) async fn append_account_line(record: &Value) -> std::io::Result<()> {
    let path = accounts_path();
    if let Some(parent) = path.parent() {
        tokio::fs::create_dir_all(parent).await?;
    }
    let line = serde_json::to_string(record)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;

    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&path)
        .await?;
    file.write_all(line.as_bytes()).await?;
    file.write_all(b"\n").await?;
    file.flush().await?;
    file.sync_all().await?;
    Ok(())
}

const MAX_PROFILE_TITLE_LEN: usize = 160;
const MAX_PROFILE_SUMMARY_LEN: usize = 2_000;
const MAX_PROFILE_ADDRESS_LEN: usize = 500;
const MAX_PROFILE_TAGS: usize = 64;
const MAX_PROFILE_TAG_LEN: usize = 80;

fn profile_response(
    account: &AccountInternal,
    address: Option<String>,
    location: Option<Location>,
) -> OwnGarnrolleProfile {
    OwnGarnrolleProfile {
        id: account.public.id.clone(),
        title: account.public.title.clone(),
        summary: account.public.summary.clone(),
        tags: account.public.tags.clone(),
        address,
        location,
        map_state: account.public.map_state,
        radius_m: account.public.radius_m,
    }
}

async fn latest_jsonl_account_record(account_id: &str) -> std::io::Result<Option<Value>> {
    let file = match File::open(accounts_path()).await {
        Ok(file) => file,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(error) => return Err(error),
    };
    let mut lines = BufReader::new(file).lines();
    let mut latest = None;
    while let Some(line) = lines.next_line().await? {
        let Ok(value) = serde_json::from_str::<Value>(&line) else {
            continue;
        };
        if value.get("id").and_then(Value::as_str) == Some(account_id) {
            latest = Some(value);
        }
    }
    Ok(latest)
}

fn private_profile_from_record(record: &Value) -> (Option<String>, Option<Location>) {
    let address = record
        .get("address")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(str::to_string);
    let location = record.get("location").and_then(|location| {
        let lat = location.get("lat").and_then(json_f64)?;
        let lon = location.get("lon").and_then(json_f64)?;
        Some(Location { lat, lon })
    });
    (address, location)
}

fn validate_profile_update(
    payload: UpdateOwnGarnrolleRequest,
) -> Result<AccountProfileUpdate, (StatusCode, String)> {
    let bad = |message: &str| (StatusCode::BAD_REQUEST, message.to_string());
    let title = payload.title.trim().to_string();
    if title.is_empty() || title.len() > MAX_PROFILE_TITLE_LEN {
        return Err(bad("title must be between 1 and 160 bytes"));
    }
    let summary = payload
        .summary
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty());
    if summary
        .as_ref()
        .is_some_and(|value| value.len() > MAX_PROFILE_SUMMARY_LEN)
    {
        return Err(bad("summary is too long"));
    }
    let address = payload
        .address
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty());
    if address
        .as_ref()
        .is_some_and(|value| value.len() > MAX_PROFILE_ADDRESS_LEN)
    {
        return Err(bad("address is too long"));
    }

    let mut tags = Vec::new();
    for raw in payload.tags {
        let tag = raw.trim();
        if tag.is_empty() {
            continue;
        }
        if tag.len() > MAX_PROFILE_TAG_LEN {
            return Err(bad("a tag is too long"));
        }
        if !tags.iter().any(|existing| existing == tag) {
            tags.push(tag.to_string());
        }
    }
    for required in ["account", "garnrolle"] {
        if !tags.iter().any(|tag| tag == required) {
            tags.push(required.to_string());
        }
    }
    if tags.len() > MAX_PROFILE_TAGS {
        return Err(bad("too many tags"));
    }

    if let Some(location) = &payload.location {
        if !location.lat.is_finite()
            || !location.lon.is_finite()
            || !(-90.0..=90.0).contains(&location.lat)
            || !(-180.0..=180.0).contains(&location.lon)
        {
            return Err(bad(
                "location is outside the valid latitude/longitude range",
            ));
        }
    }

    let (radius_m, map_state) = match payload.map_state {
        GarnrolleMapState::NotOnMap => (0_i64, "not_on_map".to_string()),
        GarnrolleMapState::Exact => {
            if address.is_none() {
                return Err(bad("address is required for a mapped Garnrolle"));
            }
            (0_i64, "exact".to_string())
        }
        GarnrolleMapState::Radius => {
            if address.is_none() {
                return Err(bad("address is required for a mapped Garnrolle"));
            }
            let radius = payload.radius_m.unwrap_or(250);
            if !(50..=5_000).contains(&radius) {
                return Err(bad("radius_m must be between 50 and 5000"));
            }
            (i64::from(radius), "radius".to_string())
        }
    };

    Ok(AccountProfileUpdate {
        title,
        summary,
        tags,
        address,
        map_state,
        radius_m,
        location: payload.location,
    })
}

fn update_jsonl_profile_record(
    mut record: Value,
    update: &AccountProfileUpdate,
) -> Result<(Value, Option<Location>), (StatusCode, String)> {
    let object = record.as_object_mut().ok_or_else(|| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            "stored account record is invalid".to_string(),
        )
    })?;
    let existing_location = object.get("location").and_then(|value| {
        let lat = value.get("lat").and_then(json_f64)?;
        let lon = value.get("lon").and_then(json_f64)?;
        Some(Location { lat, lon })
    });
    let effective_location = update.location.clone().or(existing_location);
    if update.map_state != "not_on_map" && effective_location.is_none() {
        return Err((
            StatusCode::BAD_REQUEST,
            "a map location is required for this visibility".to_string(),
        ));
    }

    object.insert("type".to_string(), json!("garnrolle"));
    object.insert("title".to_string(), json!(update.title));
    object.insert("map_state".to_string(), json!(update.map_state));
    object.insert("radius_m".to_string(), json!(update.radius_m));
    object.remove("mode");
    object.remove("ron_flag");
    object.remove("visibility");
    object.remove("suppress_public_pos");
    match &update.summary {
        Some(summary) => {
            object.insert("summary".to_string(), json!(summary));
        }
        None => {
            object.remove("summary");
        }
    }
    if update.tags.is_empty() {
        object.remove("tags");
    } else {
        object.insert("tags".to_string(), json!(update.tags));
    }
    match &update.address {
        Some(address) => {
            object.insert("address".to_string(), json!(address));
        }
        None => {
            object.remove("address");
        }
    }
    if let Some(location) = &update.location {
        object.insert(
            "location".to_string(),
            json!({ "lat": location.lat, "lon": location.lon }),
        );
    }
    Ok((record, effective_location))
}

pub async fn get_own_garnrolle_profile(
    State(state): State<ApiState>,
    Extension(ctx): Extension<AuthContext>,
) -> Result<Json<OwnGarnrolleProfile>, (StatusCode, String)> {
    let account_id = ctx
        .account_id
        .as_deref()
        .filter(|_| ctx.authenticated)
        .ok_or((
            StatusCode::UNAUTHORIZED,
            "authentication required".to_string(),
        ))?;
    let _persist_guard = state.accounts_persist.lock().await;
    let account = state
        .accounts
        .read()
        .await
        .get(account_id)
        .cloned()
        .ok_or((StatusCode::NOT_FOUND, "account not found".to_string()))?;

    let (address, location) = match state.config.domain_account_write_source {
        DomainAccountWriteSource::Jsonl => {
            let record = latest_jsonl_account_record(account_id)
                .await
                .map_err(|error| {
                    tracing::error!(%error, "failed to read own JSONL account profile");
                    (
                        StatusCode::INTERNAL_SERVER_ERROR,
                        "failed to load account profile".to_string(),
                    )
                })?
                .ok_or((
                    StatusCode::NOT_FOUND,
                    "account profile not found".to_string(),
                ))?;
            private_profile_from_record(&record)
        }
        DomainAccountWriteSource::Postgres => {
            let pool = state.db_pool.as_ref().ok_or((
                StatusCode::INTERNAL_SERVER_ERROR,
                "PostgreSQL pool unavailable for account profile".to_string(),
            ))?;
            load_account_profile_from_postgres(pool, account_id)
                .await
                .map_err(|error| {
                    tracing::error!(%error, "failed to read own PostgreSQL account profile");
                    (
                        StatusCode::INTERNAL_SERVER_ERROR,
                        "failed to load account profile".to_string(),
                    )
                })?
                .ok_or((
                    StatusCode::NOT_FOUND,
                    "account profile not found".to_string(),
                ))?
        }
    };

    Ok(Json(profile_response(&account, address, location)))
}

pub async fn update_own_garnrolle_profile(
    State(state): State<ApiState>,
    Extension(ctx): Extension<AuthContext>,
    Json(payload): Json<UpdateOwnGarnrolleRequest>,
) -> Result<Json<OwnGarnrolleProfile>, (StatusCode, String)> {
    let account_id = ctx
        .account_id
        .clone()
        .filter(|_| ctx.authenticated)
        .ok_or((
            StatusCode::UNAUTHORIZED,
            "authentication required".to_string(),
        ))?;
    let update = validate_profile_update(payload)?;
    let _persist_guard = state.accounts_persist.lock().await;
    let existing = state
        .accounts
        .read()
        .await
        .get(&account_id)
        .cloned()
        .ok_or((StatusCode::NOT_FOUND, "account not found".to_string()))?;

    let stored = match state.config.domain_account_write_source {
        DomainAccountWriteSource::Jsonl => {
            let record = latest_jsonl_account_record(&account_id)
                .await
                .map_err(|error| {
                    tracing::error!(%error, "failed to read JSONL account before profile update");
                    (
                        StatusCode::INTERNAL_SERVER_ERROR,
                        "failed to update account profile".to_string(),
                    )
                })?
                .ok_or((
                    StatusCode::NOT_FOUND,
                    "account profile not found".to_string(),
                ))?;
            let (record, location) = update_jsonl_profile_record(record, &update)?;
            let public = map_json_to_public_account(&record).ok_or((
                StatusCode::INTERNAL_SERVER_ERROR,
                "failed to project updated account".to_string(),
            ))?;
            append_account_line(&record).await.map_err(|error| {
                tracing::error!(%error, "failed to append JSONL account profile update");
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    "failed to persist account profile".to_string(),
                )
            })?;
            let mut account = existing;
            account.public = public;
            crate::domain_db::StoredAccountProfile {
                account,
                address: update.address.clone(),
                location,
            }
        }
        DomainAccountWriteSource::Postgres => {
            let pool = state.db_pool.as_ref().ok_or((
                StatusCode::INTERNAL_SERVER_ERROR,
                "PostgreSQL pool unavailable for account profile".to_string(),
            ))?;
            update_account_profile_in_postgres(pool, &account_id, &update)
                .await
                .map_err(|error| match error {
                    AccountProfileUpdateError::NotFound => {
                        (StatusCode::NOT_FOUND, "account not found".to_string())
                    }
                    AccountProfileUpdateError::MissingLocation => (
                        StatusCode::BAD_REQUEST,
                        "a map location is required for this visibility".to_string(),
                    ),
                    other => {
                        tracing::error!(error = %other, "failed to update PostgreSQL account profile");
                        (
                            StatusCode::INTERNAL_SERVER_ERROR,
                            "failed to persist account profile".to_string(),
                        )
                    }
                })?
        }
    };

    {
        let mut accounts = state.accounts.write().await;
        accounts.insert(stored.account.clone());
    }
    tracing::info!(
        event = "account.profile.updated",
        account_id = %account_id,
        map_state = %update.map_state,
        write_source = ?state.config.domain_account_write_source,
        "Account updated its own Garnrolle profile"
    );
    Ok(Json(profile_response(
        &stored.account,
        stored.address,
        stored.location,
    )))
}

/// Create the first/next account as an operator (Admin-only; gated by
/// `require_admin` middleware). v0 creates a verortete Garnrolle with a public
/// position derived from `location` (+ optional `radius_m`, default 0 => exact).
///
/// ## radius_m semantics
///
/// - `radius_m=0` (default): `public_pos` equals `location` exactly.
/// - `radius_m>0`: `public_pos` is a **deterministic, ID-based jitter** of
///   `location` within a square bounding box of ±`radius_m` meters. The jitter
///   is derived from a djb2 hash of the account ID and is guaranteed non-zero
///   (the hash bucket values can never produce exactly 0.0 offset for either
///   axis). This is not a fake field: the API actually obfuscates the position
///   when a non-zero radius is requested.
///
/// ## role=admin in v0
///
/// The `role` field accepts `"weber"` (default) or `"admin"`. Allowing an
/// Admin to create another Admin account is **intentional in v0** — it enables
/// controlled power delegation by the initial operator. Only the first Admin
/// must be bootstrapped via `scripts/dev/bootstrap-first-account.sh`; all
/// subsequent Admins can be created through this endpoint by an existing Admin.
///
/// Persists to the configured account-create write source and inserts into the
/// in-memory store (immediate visibility for GET /accounts).
pub async fn create_account(
    State(state): State<ApiState>,
    Extension(ctx): Extension<AuthContext>,
    Json(payload): Json<Value>,
) -> Result<(StatusCode, Json<AccountPublic>), (StatusCode, String)> {
    reject_account_create_unless_writable(&state)?;

    let bad = |msg: &str| (StatusCode::BAD_REQUEST, msg.to_string());

    // --- title (required, non-empty) ---
    let title = payload
        .get("title")
        .and_then(|v| v.as_str())
        .map(str::trim)
        .unwrap_or("");
    if title.is_empty() {
        return Err(bad("title is required"));
    }

    // --- type (v0: garnrolle only) ---
    let kind = payload
        .get("type")
        .and_then(|v| v.as_str())
        .unwrap_or("garnrolle");
    if kind != "garnrolle" {
        return Err(bad("type must be 'garnrolle'"));
    }

    // --- role (allowlist weber|admin, default weber) ---
    let role_str = payload
        .get("role")
        .and_then(|v| v.as_str())
        .unwrap_or("weber");
    let role = match role_str {
        "weber" => Role::Weber,
        "admin" => Role::Admin,
        _ => return Err(bad("role must be 'weber' or 'admin'")),
    };

    // --- location (required) + range validation ---
    let location = payload
        .get("location")
        .ok_or_else(|| bad("location is required"))?;
    let (lat, lon) = match (
        location.get("lat").and_then(json_f64),
        location.get("lon").and_then(json_f64),
    ) {
        (Some(la), Some(lo)) => (la, lo),
        _ => return Err(bad("location.lat and location.lon are required numbers")),
    };
    if !(-90.0..=90.0).contains(&lat) {
        return Err(bad("location.lat must be in [-90, 90]"));
    }
    if !(-180.0..=180.0).contains(&lon) {
        return Err(bad("location.lon must be in [-180, 180]"));
    }

    // --- radius_m (optional, default 0) ---
    let radius_m: u32 = match payload.get("radius_m") {
        None | Some(Value::Null) => 0,
        Some(v) => match v.as_u64() {
            Some(n) if n <= u32::MAX as u64 => n as u32,
            _ => return Err(bad("radius_m must be a non-negative integer")),
        },
    };

    // --- id (optional UUID, else generated) ---
    let id = match payload.get("id").and_then(|v| v.as_str()) {
        Some(s) => {
            if Uuid::parse_str(s).is_err() {
                return Err(bad("id must be a UUID"));
            }
            s.to_string()
        }
        None => Uuid::new_v4().to_string(),
    };

    // --- optional summary / tags / email ---
    let summary = payload
        .get("summary")
        .and_then(|v| v.as_str())
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(str::to_string);
    let tags: Vec<String> = payload
        .get("tags")
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|x| x.as_str().map(String::from))
                .collect()
        })
        .unwrap_or_default();
    let email = payload
        .get("email")
        .and_then(|v| v.as_str())
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(str::to_string);
    let webauthn_user_id = Uuid::new_v4();

    // --- Build canonical JSONL record (matches contract after key projection;
    // role/email are operational fields read by the API) ---
    let mut record = serde_json::Map::new();
    record.insert("id".into(), json!(id));
    record.insert("type".into(), json!("garnrolle"));
    record.insert("title".into(), json!(title));
    if let Some(s) = &summary {
        record.insert("summary".into(), json!(s));
    }
    if !tags.is_empty() {
        record.insert("tags".into(), json!(tags));
    }
    record.insert("role".into(), json!(role_str));
    record.insert("location".into(), json!({ "lat": lat, "lon": lon }));
    record.insert(
        "map_state".into(),
        json!(if radius_m > 0 { "radius" } else { "exact" }),
    );
    record.insert("radius_m".into(), json!(radius_m));
    if let Some(e) = &email {
        record.insert("email".into(), json!(e));
    }
    record.insert(
        "webauthn_user_id".into(),
        Value::String(webauthn_user_id.to_string()),
    );
    let record = Value::Object(record);

    let public = map_json_to_public_account(&record).ok_or_else(|| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            "failed to map account".to_string(),
        )
    })?;

    // --- Persist (serialize creates so check-then-write is atomic) ---
    let _persist_guard = state.accounts_persist.lock().await;

    {
        let accounts = state.accounts.read().await;
        if accounts.get(&id).is_some() {
            return Err((
                StatusCode::CONFLICT,
                "account id already exists".to_string(),
            ));
        }
        if let Some(e) = &email {
            if accounts.get_by_email(e).is_some() {
                return Err((StatusCode::CONFLICT, "email already exists".to_string()));
            }
        }
    }

    // Persist to the configured account-create write source. Only after a
    // successful durable write is the in-memory store mutated. A failed write
    // must never leave a phantom account in memory, and the two write sources
    // are mutually exclusive (no dual-write): JSONL mode never touches
    // PostgreSQL, PostgreSQL mode never appends JSONL.
    match state.config.domain_account_write_source {
        DomainAccountWriteSource::Jsonl => {
            if let Err(e) = append_account_line(&record).await {
                tracing::error!(error = %e, "failed to append account to JSONL");
                return Err((
                    StatusCode::INTERNAL_SERVER_ERROR,
                    "failed to persist account".to_string(),
                ));
            }
        }
        DomainAccountWriteSource::Postgres => {
            // Startup validation guarantees a pool exists in this mode; treat a
            // missing pool as an internal error rather than silently degrading.
            let pool = state.db_pool.as_ref().ok_or_else(|| {
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    "PostgreSQL pool unavailable for account write".to_string(),
                )
            })?;
            match insert_account_from_jsonl_record(pool, &record).await {
                Ok(()) => {}
                Err(AccountWriteError::DuplicateId) => {
                    return Err((
                        StatusCode::CONFLICT,
                        "account id already exists".to_string(),
                    ));
                }
                Err(AccountWriteError::DuplicateEmail) => {
                    // Same generic message as the in-memory precheck above, so the
                    // client sees a consistent 409 whether the conflict is caught
                    // in memory or by the PostgreSQL unique index. The offending
                    // email, account id and constraint name are never leaked.
                    return Err((StatusCode::CONFLICT, "email already exists".to_string()));
                }
                Err(e) => {
                    tracing::error!(error = %e, "failed to insert account into domain_accounts");
                    return Err((
                        StatusCode::INTERNAL_SERVER_ERROR,
                        "failed to persist account".to_string(),
                    ));
                }
            }
        }
    }

    {
        let mut accounts = state.accounts.write().await;
        accounts.insert(AccountInternal {
            public: public.clone(),
            role,
            email,
            webauthn_user_id,
        });
    }

    tracing::info!(
        event = "account.created",
        account_id = %id,
        created_by = ctx.account_id.as_deref().unwrap_or("?"),
        write_source = ?state.config.domain_account_write_source,
        "Account created by operator"
    );

    Ok((StatusCode::CREATED, Json(public)))
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
    fn invalid_explicit_map_state_is_rejected() {
        let input = serde_json::json!({
            "id": "test-invalid-map-state",
            "type": "garnrolle",
            "title": "Invalid state",
            "map_state": "public-ish",
            "location": { "lat": 53.5, "lon": 10.0 }
        });
        assert!(map_json_to_public_account(&input).is_none());
    }

    #[test]
    fn explicit_not_on_map_ignores_internal_and_supplied_public_positions() {
        let input = serde_json::json!({
            "id": "test-explicit-hidden",
            "type": "garnrolle",
            "title": "Hidden Test",
            "map_state": "not_on_map",
            "location": { "lat": 53.5, "lon": 10.0 },
            "public_pos": { "lat": 1.0, "lon": 2.0 },
            "radius_m": 500
        });

        let account = map_json_to_public_account(&input).expect("Mapping failed");
        assert_eq!(account.map_state, GarnrolleMapState::NotOnMap);
        assert_eq!(account.radius_m, 0);
        assert!(account.public_pos.is_none());
        let output = serde_json::to_value(&account).expect("serialize public account");
        assert!(output.get("location").is_none());
        assert!(output.get("public_pos").is_none());
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

        // GUARD: Private legacy visibility becomes an ordinary Garnrolle off the public map.
        assert_eq!(account.map_state, GarnrolleMapState::NotOnMap);
        assert!(account.public_pos.is_none());
    }

    #[test]
    fn test_guard_legacy_radius_maps_to_radius_state() {
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

        assert_eq!(account.map_state, GarnrolleMapState::Exact);
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
        // The longitude offset should be scaled by exactly 1 / cos(latitude) compared to the equator.

        let radius_m = 111_000;
        let lat = 60.0;

        // Find any ID that produces a non-zero longitude jitter to avoid divide-by-zero.
        let id = (0..100)
            .map(|i| i.to_string())
            .find(|id| calculate_jittered_pos(0.0, 0.0, radius_m, id).lon.abs() > 1e-6)
            .expect("expected deterministic id with non-zero longitude jitter");

        let equator = calculate_jittered_pos(0.0, 0.0, radius_m, &id);
        let high_lat = calculate_jittered_pos(lat, 0.0, radius_m, &id);

        let equator_lon = equator.lon.abs();
        let high_lat_lon = high_lat.lon.abs();

        assert!(
            equator_lon > 1e-6,
            "fixture id must produce non-zero longitude jitter"
        );

        let expected_scale = 1.0 / lat.to_radians().cos();
        let observed_scale = high_lat_lon / equator_lon;

        assert!(
            (observed_scale - expected_scale).abs() < 1e-6,
            "longitude jitter should scale by 1/cos(latitude); expected {}, got {}",
            expected_scale,
            observed_scale
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
    fn test_legacy_verortet_without_location_normalizes_to_not_on_map() {
        let input = json!({
            "id": "test-verortet-no-loc",
            "type": "garnrolle",
            "title": "No Loc",
            "mode": "verortet",
        });

        let account = map_json_to_public_account(&input)
            .expect("A Garnrolle without location remains a valid account");
        assert_eq!(account.kind, "garnrolle");
        assert_eq!(account.map_state, GarnrolleMapState::NotOnMap);
        assert!(account.public_pos.is_none());
    }

    #[test]
    fn test_ron_without_location_succeeds() {
        let input = serde_json::json!({
            "id": "test-ron-no-loc",
            "type": "ron",
            "title": "No Loc Ron",
            "mode": "ron",
        });

        let account = map_json_to_public_account(&input)
            .expect("legacy RoN without location should normalize");
        assert_eq!(account.map_state, GarnrolleMapState::NotOnMap);
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
        assert_eq!(account.map_state, GarnrolleMapState::NotOnMap);
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
        assert_eq!(account.map_state, GarnrolleMapState::NotOnMap);
        assert!(account.public_pos.is_none());
    }
}

#[cfg(test)]
mod profile_update_tests {
    use super::*;
    use serde_json::json;

    fn request(
        map_state: GarnrolleMapState,
        address: Option<&str>,
        location: Option<Location>,
    ) -> UpdateOwnGarnrolleRequest {
        UpdateOwnGarnrolleRequest {
            title: "  Meine Garnrolle  ".to_string(),
            summary: Some("  Gemeinsame Dinge  ".to_string()),
            tags: vec![
                "skill:Kochen".to_string(),
                "skill:Kochen".to_string(),
                "interest:Commons".to_string(),
            ],
            address: address.map(str::to_string),
            map_state,
            radius_m: Some(250),
            location,
        }
    }

    #[test]
    fn exact_profile_requires_address_and_valid_location() {
        let missing_address = validate_profile_update(request(
            GarnrolleMapState::Exact,
            None,
            Some(Location {
                lat: 53.5,
                lon: 10.0,
            }),
        ));
        assert_eq!(missing_address.unwrap_err().0, StatusCode::BAD_REQUEST);

        let invalid_location = validate_profile_update(request(
            GarnrolleMapState::Exact,
            Some("Poelsweg 2, Hamburg"),
            Some(Location {
                lat: 91.0,
                lon: 10.0,
            }),
        ));
        assert_eq!(invalid_location.unwrap_err().0, StatusCode::BAD_REQUEST);
    }

    #[test]
    fn profile_validation_normalises_fields_and_keeps_required_tags() {
        let update = validate_profile_update(request(
            GarnrolleMapState::Radius,
            Some("  Poelsweg 2, Hamburg  "),
            Some(Location {
                lat: 53.5,
                lon: 10.0,
            }),
        ))
        .expect("valid profile");

        assert_eq!(update.title, "Meine Garnrolle");
        assert_eq!(update.summary.as_deref(), Some("Gemeinsame Dinge"));
        assert_eq!(update.address.as_deref(), Some("Poelsweg 2, Hamburg"));
        assert_eq!(update.map_state, "radius");
        assert_eq!(update.radius_m, 250);
        assert_eq!(
            update.tags,
            vec!["skill:Kochen", "interest:Commons", "account", "garnrolle"]
        );
    }

    #[test]
    fn jsonl_update_preserves_operational_identity_and_existing_location() {
        let record = json!({
            "id": "own-account",
            "type": "garnrolle",
            "title": "Alt",
            "role": "weber",
            "email": "private@example.test",
            "webauthn_user_id": "79e8d447-c7b3-46ff-bcc9-55a0d843f780",
            "map_state": "exact",
            "radius_m": 0,
            "location": {"lat": 53.5, "lon": 10.0},
            "address": "Alte Adresse"
        });
        let update = validate_profile_update(UpdateOwnGarnrolleRequest {
            title: "Neu".to_string(),
            summary: None,
            tags: vec![],
            address: Some("Neue Adresse".to_string()),
            map_state: GarnrolleMapState::Exact,
            radius_m: None,
            location: None,
        })
        .expect("valid profile");

        let (updated, effective_location) =
            update_jsonl_profile_record(record, &update).expect("update record");
        assert_eq!(updated["id"], "own-account");
        assert_eq!(updated["role"], "weber");
        assert_eq!(updated["email"], "private@example.test");
        assert_eq!(
            updated["webauthn_user_id"],
            "79e8d447-c7b3-46ff-bcc9-55a0d843f780"
        );
        assert_eq!(updated["title"], "Neu");
        assert_eq!(updated["address"], "Neue Adresse");
        assert_eq!(effective_location.unwrap().lat, 53.5);
        assert_eq!(updated["location"]["lat"], 53.5);
    }

    #[test]
    fn not_on_map_keeps_internal_location_but_has_no_public_projection() {
        let record = json!({
            "id": "own-account",
            "type": "garnrolle",
            "title": "Alt",
            "role": "weber",
            "map_state": "exact",
            "radius_m": 0,
            "location": {"lat": 53.5, "lon": 10.0}
        });
        let update = validate_profile_update(request(GarnrolleMapState::NotOnMap, None, None))
            .expect("not-on-map profile");
        let (updated, _) = update_jsonl_profile_record(record, &update).expect("update record");
        let public = map_json_to_public_account(&updated).expect("public account");
        assert_eq!(public.map_state, GarnrolleMapState::NotOnMap);
        assert!(public.public_pos.is_none());
        assert_eq!(updated["location"]["lat"], 53.5);
    }
}
