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
use crate::routes::auth::passkey_register_options;

use self::{
    accounts::{get_account, list_accounts},
    auth::{
        consume_login_get, consume_login_post, consume_step_up, dev_login, list_dev_accounts,
        list_devices, logout, logout_all, me, remove_device, request_login, request_step_up,
        session, session_refresh, update_email,
    },
    edges::{get_edge, list_edges},
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
        .route("/edges/:id", get(get_edge))
        .route("/accounts", get(list_accounts))
        .route("/accounts/:id", get(get_account))
        .route("/auth/dev/accounts", get(list_dev_accounts))
        .route("/auth/dev/login", post(dev_login))
        .route("/auth/magic-link/request", post(request_login))
        .route(
            "/auth/magic-link/consume",
            get(consume_login_get).post(consume_login_post),
        )
        // TODO: Temporary legacy alias for already dispatched magic links.
        // Remove once in-flight tokens from before the /magic-link/ migration have expired.
        .route(
            "/auth/login/consume",
            get(consume_login_get).post(consume_login_post),
        )
        .route("/auth/logout", post(logout))
        .route("/auth/logout-all", post(logout_all))
        .route("/auth/devices", get(list_devices))
        .route("/auth/devices/:id", axum::routing::delete(remove_device))
        .route("/auth/me", get(me))
        .route("/auth/me/email", axum::routing::put(update_email))
        .route("/auth/session", get(session))
        .route("/auth/session/refresh", post(session_refresh))
        .route("/auth/step-up/magic-link/request", post(request_step_up))
        .route("/auth/step-up/magic-link/consume", post(consume_step_up))
        .route("/auth/passkeys/register-options", post(passkey_register_options))
}
