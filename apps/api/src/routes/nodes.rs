use axum::{extract::Query, http::StatusCode, Json};
use serde_json::Value;
use std::{collections::HashMap, env, path::PathBuf};
use tokio::{
    fs::File,
    io::{AsyncBufReadExt, BufReader},
};

fn in_dir() -> PathBuf {
    // Überschreibbar in Tests via GEWEBE_IN_DIR
    env::var("GEWEBE_IN_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from(".gewebe/in"))
}

fn nodes_path() -> PathBuf {
    in_dir().join("demo.nodes.jsonl")
}

#[derive(Clone, Copy, Debug)]
struct BBox {
    min_lng: f64,
    min_lat: f64,
    max_lng: f64,
    max_lat: f64,
}

fn parse_bbox(s: &str) -> Option<BBox> {
    let parts: Vec<_> = s.split(',').collect();
    let (lng1, lat1, lng2, lat2) = match parts.as_slice() {
        [lng1, lat1, lng2, lat2] => (
            lng1.trim().parse::<f64>().ok()?,
            lat1.trim().parse::<f64>().ok()?,
            lng2.trim().parse::<f64>().ok()?,
            lat2.trim().parse::<f64>().ok()?,
        ),
        _ => return None,
    };

    Some(BBox {
        min_lng: lng1.min(lng2),
        min_lat: lat1.min(lat2),
        max_lng: lng1.max(lng2),
        max_lat: lat1.max(lat2),
    })
}

fn point_in_bbox(lng: f64, lat: f64, bb: &BBox) -> bool {
    lng >= bb.min_lng && lng <= bb.max_lng && lat >= bb.min_lat && lat <= bb.max_lat
}

fn feature_point_coords(v: &Value) -> Option<(f64, f64)> {
    // Erwartet GeoJSON Feature Point: geometry.coordinates [lng,lat]
    let coords = v.pointer("/geometry/coordinates")?;
    let arr = coords.as_array()?;
    if arr.len() < 2 {
        return None;
    }
    let lng = arr[0].as_f64()?;
    let lat = arr[1].as_f64()?;
    Some((lng, lat))
}

pub async fn list_nodes(
    Query(params): Query<HashMap<String, String>>,
) -> Result<Json<Vec<Value>>, StatusCode> {
    let bbox = match params.get("bbox") {
        Some(raw_bbox) => Some(parse_bbox(raw_bbox).ok_or(StatusCode::BAD_REQUEST)?),
        None => None,
    };
    let limit: usize = params
        .get("limit")
        .and_then(|s| s.parse().ok())
        .unwrap_or(100);

    let path = nodes_path();
    let file = match File::open(&path).await {
        Ok(f) => f,
        Err(_) => return Ok(Json(Vec::new())), // robust: leer zurückgeben
    };
    let mut lines = BufReader::new(file).lines();

    let mut out = Vec::with_capacity(limit.min(1024));
    while let Ok(Some(line)) = lines.next_line().await {
        if out.len() >= limit {
            break;
        }
        let v: Value = match serde_json::from_str(&line) {
            Ok(v) => v,
            Err(_) => continue, // fehlerhafte Zeilen überschringen
        };

        if let Some(bb) = bbox {
            if let Some((lng, lat)) = feature_point_coords(&v) {
                if !point_in_bbox(lng, lat, &bb) {
                    continue;
                }
            } else {
                continue; // ohne Koordinate nicht in BBox
            }
        }
        out.push(v);
    }

    Ok(Json(out))
}
