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

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn from_str_lossy_exact_matches() {
        assert_eq!(Role::from_str_lossy("admin"), Role::Admin);
        assert_eq!(Role::from_str_lossy("weber"), Role::Weber);
        assert_eq!(Role::from_str_lossy("gast"), Role::Gast);
        assert_eq!(Role::from_str_lossy("guest"), Role::Gast);
    }

    #[test]
    fn from_str_lossy_case_insensitive() {
        assert_eq!(Role::from_str_lossy("Admin"), Role::Admin);
        assert_eq!(Role::from_str_lossy("ADMIN"), Role::Admin);
        assert_eq!(Role::from_str_lossy("Weber"), Role::Weber);
        assert_eq!(Role::from_str_lossy("WEBER"), Role::Weber);
    }

    #[test]
    fn from_str_lossy_trims_whitespace() {
        assert_eq!(Role::from_str_lossy(" admin "), Role::Admin);
        assert_eq!(Role::from_str_lossy("\tadmin\n"), Role::Admin);
    }

    #[test]
    fn from_str_lossy_unknown_falls_back_to_gast() {
        assert_eq!(Role::from_str_lossy("unknown"), Role::Gast);
        assert_eq!(Role::from_str_lossy("superadmin"), Role::Gast);
        assert_eq!(Role::from_str_lossy(""), Role::Gast);
    }

    #[test]
    fn serde_serialization() {
        assert_eq!(serde_json::to_value(&Role::Admin).unwrap(), json!("admin"));
        assert_eq!(serde_json::to_value(&Role::Weber).unwrap(), json!("weber"));
        assert_eq!(serde_json::to_value(&Role::Gast).unwrap(), json!("gast"));
    }

    #[test]
    fn serde_deserialization() {
        let admin: Role = serde_json::from_value(json!("admin")).unwrap();
        assert_eq!(admin, Role::Admin);

        let weber: Role = serde_json::from_value(json!("weber")).unwrap();
        assert_eq!(weber, Role::Weber);

        let gast: Role = serde_json::from_value(json!("gast")).unwrap();
        assert_eq!(gast, Role::Gast);
    }
}
