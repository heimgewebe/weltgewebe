pub mod accounts;
pub mod auth;
pub mod edges;
pub mod health;
pub mod meta;
pub mod nodes;

use axum::{
    middleware::from_fn,
    routing::{get, post},
    Router,
};

use crate::middleware::authz::require_write;
use crate::state::ApiState;

use self::{
    accounts::{get_account, list_accounts},
    auth::{consume_login, dev_login, list_dev_accounts, logout, me, request_login},
    edges::list_edges,
    nodes::{get_node, list_nodes, patch_node},
};

pub fn api_router() -> Router<ApiState> {
    Router::new()
        .route("/nodes", get(list_nodes))
        .route(
            "/nodes/:id",
            get(get_node)
                .patch(patch_node)
                .route_layer(from_fn(require_write)),
        )
        .route("/edges", get(list_edges))
        .route("/accounts", get(list_accounts))
        .route("/accounts/:id", get(get_account))
        .route("/auth/dev/accounts", get(list_dev_accounts))
        .route("/auth/dev/login", post(dev_login))
        .route("/auth/login/request", post(request_login))
        .route("/auth/login/consume", get(consume_login))
        .route("/auth/logout", post(logout))
        .route("/auth/me", get(me))
}
