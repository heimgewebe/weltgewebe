use super::query::{
    cursor_page, parse_cursor_params, parse_usize_param, validate_cursor_limit, ListResponse,
    MAX_PAGE_SIZE,
};
use crate::{routes::nodes::Location, state::ApiState};
use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    Json,
};
use chrono::{DateTime, SecondsFormat, Utc};
use serde::Serialize;
use sqlx::{PgPool, Row};
use std::collections::HashMap;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum WebgemeindezentrumLocationState {
    Desired,
    Provisional,
    Confirmed,
    Unavailable,
    RelocationProposed,
}

impl WebgemeindezentrumLocationState {
    fn parse(value: &str) -> Result<Self, sqlx::Error> {
        match value {
            "desired" => Ok(Self::Desired),
            "provisional" => Ok(Self::Provisional),
            "confirmed" => Ok(Self::Confirmed),
            "unavailable" => Ok(Self::Unavailable),
            "relocation_proposed" => Ok(Self::RelocationProposed),
            other => Err(sqlx::Error::Decode(
                format!("unsupported Webgemeindezentrum location_state {other:?}").into(),
            )),
        }
    }

    pub fn label(self) -> &'static str {
        match self {
            Self::Desired => "Gewünschter Treffort",
            Self::Provisional => "Vorläufiger Treffort",
            Self::Confirmed => "Bestätigter Treffort",
            Self::Unavailable => "Derzeit nicht verfügbar",
            Self::RelocationProposed => "Neuer Treffort vorgeschlagen",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct OrtswebereiReference {
    pub id: String,
    pub slug: String,
    pub name: String,
    pub gewebezelle_id: String,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
pub struct Webgemeindezentrum {
    #[serde(rename = "type")]
    pub entity_type: &'static str,
    pub id: String,
    pub title: String,
    pub ortsweberei: OrtswebereiReference,
    pub location_state: WebgemeindezentrumLocationState,
    pub location_state_label: &'static str,
    pub location: Location,
    pub location_label: String,
    pub meeting_note: String,
    pub access_note: String,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
pub struct Ortsweberei {
    pub id: String,
    pub slug: String,
    pub name: String,
    pub description: String,
    pub gewebezelle_id: String,
    pub lifecycle_state: String,
    pub created_at: String,
    pub updated_at: String,
    pub webgemeindezentrum: Webgemeindezentrum,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
pub struct WebgemeindezentrumLocationHistoryEvent {
    pub event_id: i64,
    pub event_type: String,
    pub location_state: WebgemeindezentrumLocationState,
    pub location_state_label: &'static str,
    pub location: Location,
    pub location_label: String,
    pub reason: String,
    pub decided_at: String,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
pub struct WebgemeindezentrumDetails {
    #[serde(flatten)]
    pub center: Webgemeindezentrum,
    pub location_history: Vec<WebgemeindezentrumLocationHistoryEvent>,
}

fn timestamp(value: DateTime<Utc>) -> String {
    value.to_rfc3339_opts(SecondsFormat::Millis, true)
}

fn database_pool(state: &ApiState) -> Result<&PgPool, StatusCode> {
    state
        .db_pool
        .as_ref()
        .ok_or(StatusCode::SERVICE_UNAVAILABLE)
}

async fn load_active_ortswebereien(pool: &PgPool) -> Result<Vec<Ortsweberei>, sqlx::Error> {
    let rows = sqlx::query(
        "SELECT \
             o.id AS ortsweberei_id, o.slug, o.name AS ortsweberei_name, \
             o.description, o.gewebezelle_id, o.lifecycle_state, \
             o.created_at AS ortsweberei_created_at, \
             o.updated_at AS ortsweberei_updated_at, \
             c.id AS center_id, c.name AS center_name, c.location_state, \
             c.lat, c.lon, c.location_label, c.meeting_note, c.access_note, \
             c.created_at AS center_created_at, c.updated_at AS center_updated_at \
         FROM ortswebereien o \
         JOIN gewebezellen g ON g.id = o.gewebezelle_id \
         JOIN webgemeindezentren c \
           ON c.id = o.active_webgemeindezentrum_id \
          AND c.ortsweberei_id = o.id \
         WHERE o.lifecycle_state = 'active' \
           AND g.lifecycle_state = 'active' \
         ORDER BY o.id",
    )
    .fetch_all(pool)
    .await?;

    rows.into_iter()
        .map(|row| {
            let location_state_raw: String = row.try_get("location_state")?;
            let location_state = WebgemeindezentrumLocationState::parse(&location_state_raw)?;
            let reference = OrtswebereiReference {
                id: row.try_get("ortsweberei_id")?,
                slug: row.try_get("slug")?,
                name: row.try_get("ortsweberei_name")?,
                gewebezelle_id: row.try_get("gewebezelle_id")?,
            };
            let center = Webgemeindezentrum {
                entity_type: "webgemeindezentrum",
                id: row.try_get("center_id")?,
                title: row.try_get("center_name")?,
                ortsweberei: reference.clone(),
                location_state,
                location_state_label: location_state.label(),
                location: Location {
                    lat: row.try_get("lat")?,
                    lon: row.try_get("lon")?,
                },
                location_label: row.try_get("location_label")?,
                meeting_note: row.try_get("meeting_note")?,
                access_note: row.try_get("access_note")?,
                created_at: timestamp(row.try_get("center_created_at")?),
                updated_at: timestamp(row.try_get("center_updated_at")?),
            };

            Ok(Ortsweberei {
                id: reference.id,
                slug: reference.slug,
                name: reference.name,
                description: row.try_get("description")?,
                gewebezelle_id: reference.gewebezelle_id,
                lifecycle_state: row.try_get("lifecycle_state")?,
                created_at: timestamp(row.try_get("ortsweberei_created_at")?),
                updated_at: timestamp(row.try_get("ortsweberei_updated_at")?),
                webgemeindezentrum: center,
            })
        })
        .collect()
}

fn internal_error(error: sqlx::Error, operation: &'static str) -> StatusCode {
    tracing::error!(%error, operation, "failed to read Ortsweberei structure");
    StatusCode::INTERNAL_SERVER_ERROR
}

fn paginate<T: Clone>(
    items: Vec<T>,
    params: &HashMap<String, String>,
    id_of: impl Fn(&T) -> &str + Copy,
) -> Result<ListResponse<T>, StatusCode> {
    let limit = parse_usize_param(params, "limit", 100)?.min(MAX_PAGE_SIZE);
    let (cursor_mode, after_id) = parse_cursor_params(params)?;
    validate_cursor_limit(cursor_mode, limit)?;

    if cursor_mode {
        let refs: Vec<&T> = items.iter().collect();
        Ok(ListResponse::Cursor(cursor_page(
            refs,
            limit,
            after_id.as_deref(),
            |item| id_of(item),
            |item| item.clone(),
        )))
    } else {
        let offset = parse_usize_param(params, "offset", 0)?;
        Ok(ListResponse::Legacy(
            items.into_iter().skip(offset).take(limit).collect(),
        ))
    }
}

pub async fn list_webgemeindezentren(
    State(state): State<ApiState>,
    Query(params): Query<HashMap<String, String>>,
) -> Result<Json<ListResponse<Webgemeindezentrum>>, StatusCode> {
    let pool = database_pool(&state)?;
    let mut centers: Vec<Webgemeindezentrum> = load_active_ortswebereien(pool)
        .await
        .map_err(|error| internal_error(error, "list_webgemeindezentren"))?
        .into_iter()
        .map(|ortsweberei| ortsweberei.webgemeindezentrum)
        .collect();
    centers.sort_by(|left, right| left.id.cmp(&right.id));
    paginate(centers, &params, |center| center.id.as_str()).map(Json)
}

pub async fn get_webgemeindezentrum(
    State(state): State<ApiState>,
    Path(id): Path<String>,
) -> Result<Json<WebgemeindezentrumDetails>, StatusCode> {
    let pool = database_pool(&state)?;
    let center = load_active_ortswebereien(pool)
        .await
        .map_err(|error| internal_error(error, "get_webgemeindezentrum"))?
        .into_iter()
        .map(|ortsweberei| ortsweberei.webgemeindezentrum)
        .find(|center| center.id == id)
        .ok_or(StatusCode::NOT_FOUND)?;

    let rows = sqlx::query(
        "SELECT event_id, event_type, location_state, lat, lon, \
                location_label, reason, decided_at \
         FROM webgemeindezentrum_location_history \
         WHERE webgemeindezentrum_id = $1 \
         ORDER BY decided_at DESC, event_id DESC",
    )
    .bind(&id)
    .fetch_all(pool)
    .await
    .map_err(|error| internal_error(error, "get_webgemeindezentrum_history"))?;

    let location_history = rows
        .into_iter()
        .map(|row| {
            let raw_state: String = row.try_get("location_state")?;
            let state = WebgemeindezentrumLocationState::parse(&raw_state)?;
            Ok(WebgemeindezentrumLocationHistoryEvent {
                event_id: row.try_get("event_id")?,
                event_type: row.try_get("event_type")?,
                location_state: state,
                location_state_label: state.label(),
                location: Location {
                    lat: row.try_get("lat")?,
                    lon: row.try_get("lon")?,
                },
                location_label: row.try_get("location_label")?,
                reason: row.try_get("reason")?,
                decided_at: timestamp(row.try_get("decided_at")?),
            })
        })
        .collect::<Result<Vec<_>, sqlx::Error>>()
        .map_err(|error| internal_error(error, "decode_webgemeindezentrum_history"))?;

    Ok(Json(WebgemeindezentrumDetails {
        center,
        location_history,
    }))
}

pub async fn list_ortswebereien(
    State(state): State<ApiState>,
    Query(params): Query<HashMap<String, String>>,
) -> Result<Json<ListResponse<Ortsweberei>>, StatusCode> {
    let pool = database_pool(&state)?;
    let ortswebereien = load_active_ortswebereien(pool)
        .await
        .map_err(|error| internal_error(error, "list_ortswebereien"))?;
    paginate(ortswebereien, &params, |ortsweberei| {
        ortsweberei.id.as_str()
    })
    .map(Json)
}

pub async fn get_ortsweberei(
    State(state): State<ApiState>,
    Path(id): Path<String>,
) -> Result<Json<Ortsweberei>, StatusCode> {
    let pool = database_pool(&state)?;
    load_active_ortswebereien(pool)
        .await
        .map_err(|error| internal_error(error, "get_ortsweberei"))?
        .into_iter()
        .find(|ortsweberei| ortsweberei.id == id)
        .map(Json)
        .ok_or(StatusCode::NOT_FOUND)
}

#[cfg(test)]
mod tests {
    use super::WebgemeindezentrumLocationState;

    #[test]
    fn location_state_labels_do_not_claim_confirmation_for_intentions() {
        assert_eq!(
            WebgemeindezentrumLocationState::Desired.label(),
            "Gewünschter Treffort"
        );
        assert_eq!(
            WebgemeindezentrumLocationState::Provisional.label(),
            "Vorläufiger Treffort"
        );
        assert_eq!(
            WebgemeindezentrumLocationState::Confirmed.label(),
            "Bestätigter Treffort"
        );
    }

    #[test]
    fn rejects_unknown_location_states_from_the_database() {
        assert!(WebgemeindezentrumLocationState::parse("reserved").is_err());
    }
}
