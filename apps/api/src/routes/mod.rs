pub mod accounts;
pub mod auth;
mod domain_write_guard;
pub mod edges;
pub mod governance;
pub mod health;
pub mod meta;
pub mod nodes;
mod query;

use axum::{
    middleware::from_fn,
    routing::{get, post},
    Router,
};

use crate::middleware::authz::{require_admin, require_write};
use crate::state::ApiState;

use self::{
    accounts::{
        create_account, get_account, get_own_garnrolle_profile, list_accounts,
        update_own_garnrolle_profile,
    },
    auth::{
        consume_login_get, consume_login_post, consume_step_up, dev_login, list_dev_accounts,
        list_devices, logout, logout_all, me, passkey_auth_options, passkey_auth_verify,
        passkey_register_options, passkey_register_verify, remove_device, request_login,
        request_step_up, session, session_refresh, update_email,
    },
    edges::{get_edge, list_edges},
    governance::{
        create_proposal, exit_own_account, get_proposal, list_proposal_messages, list_proposals,
        post_proposal_message, veto_proposal, vote_proposal,
    },
    nodes::{create_node, get_node, list_nodes, patch_node},
};

pub fn api_router() -> Router<ApiState> {
    let router = Router::new()
        .route(
            "/nodes",
            get(list_nodes).merge(post(create_node).route_layer(from_fn(require_write))),
        )
        .route(
            "/nodes/{id}",
            get(get_node)
                .patch(patch_node)
                .route_layer(from_fn(require_write)),
        )
        .route("/edges", get(list_edges))
        .route("/edges/{id}", get(get_edge))
        .route(
            "/accounts",
            get(list_accounts)
                .post(create_account)
                .route_layer(from_fn(require_admin)),
        )
        .route(
            "/accounts/me/profile",
            get(get_own_garnrolle_profile)
                .patch(update_own_garnrolle_profile)
                .route_layer(from_fn(require_write)),
        )
        .route("/accounts/{id}", get(get_account))
        // Antragssystem (docs/specs/governance-antraege.md). `POST /proposals`
        // und `POST /accounts/me/exit` sind bewusst NICHT hinter
        // `require_write`: der eigene Weberantrag und der eigene Austritt sind
        // die einzigen zustandsändernden Gastvorgänge; die Handler prüfen die
        // Authentifizierung selbst. Veto, Stimme und Gesprächsraum-Beiträge
        // sind Webungsaktionen und bleiben Gästen verwehrt.
        .route("/proposals", get(list_proposals).post(create_proposal))
        .route("/proposals/{id}", get(get_proposal))
        .route(
            "/proposals/{id}/veto",
            post(veto_proposal).route_layer(from_fn(require_write)),
        )
        .route(
            "/proposals/{id}/vote",
            axum::routing::put(vote_proposal).route_layer(from_fn(require_write)),
        )
        .route(
            "/proposals/{id}/messages",
            get(list_proposal_messages)
                .merge(post(post_proposal_message).route_layer(from_fn(require_write))),
        )
        .route("/accounts/me/exit", post(exit_own_account))
        .route("/auth/dev/accounts", get(list_dev_accounts))
        .route("/auth/dev/login", post(dev_login))
        .route("/auth/magic-link/request", post(request_login))
        .route(
            "/auth/magic-link/consume",
            get(consume_login_get).post(consume_login_post),
        )
        .route("/auth/logout", post(logout))
        .route("/auth/logout-all", post(logout_all))
        .route("/auth/devices", get(list_devices))
        .route("/auth/devices/{id}", axum::routing::delete(remove_device))
        .route("/auth/me", get(me))
        .route("/auth/me/email", axum::routing::put(update_email))
        .route("/auth/session", get(session))
        .route("/auth/session/refresh", post(session_refresh))
        .route("/auth/step-up/magic-link/request", post(request_step_up))
        .route("/auth/step-up/magic-link/consume", post(consume_step_up))
        .route(
            "/auth/passkeys/register/options",
            post(passkey_register_options),
        )
        .route(
            "/auth/passkeys/register/verify",
            post(passkey_register_verify),
        )
        .route("/auth/passkeys/auth/options", post(passkey_auth_options))
        .route("/auth/passkeys/auth/verify", post(passkey_auth_verify));

    #[cfg(feature = "integration-testing")]
    let router = router.route(
        "/auth/testing/passkeys/bootstrap-session",
        post(auth::passkey_testing_bootstrap_session),
    );

    #[cfg(feature = "integration-testing")]
    let router = router.route(
        "/auth/testing/passkeys/register/grant",
        post(auth::passkey_testing_issue_grant),
    );

    #[cfg(feature = "integration-testing")]
    let router = router.route(
        "/auth/testing/passkeys",
        get(auth::passkey_testing_list_credentials),
    );

    router
}
