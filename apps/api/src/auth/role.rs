use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Role {
    Gast,
    Weber,
    Admin,
}

impl Role {
    pub fn from_str_lossy(s: &str) -> Role {
        match s.trim().to_ascii_lowercase().as_str() {
            "admin" => Role::Admin,
            "weber" => Role::Weber,
            "gast" => Role::Gast,
            "guest" => Role::Gast,
            _ => Role::Gast,
        }
    }
}
