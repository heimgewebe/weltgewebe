pub mod edges;
pub mod health;
pub mod meta;
pub mod nodes;

use axum::{routing::get, Router};

use crate::state::ApiState;

use self::{edges::list_edges, nodes::list_nodes};

pub fn api_router() -> Router<ApiState> {
    Router::new()
        .route("/nodes", get(list_nodes))
        .route("/edges", get(list_edges))
}
