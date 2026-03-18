import re

with open('apps/api/src/routes/accounts.rs', 'r') as f:
    code = f.read()

# Update the legacy fallback logic for visibility="private"
legacy_fallback_match = r'''                    "private" => \{
                        // Legacy private records without a mode are treated safely
                        // by forcing a high fuzziness if they must be rendered,
                        // or mapping them to Ron if we consider them name-less\.
                        // The safest approach is to not blindly map them to "verortet" at 0m\.
                        // But since they have a location, we shouldn't drop it\.
                        // Let's map to Verortet but enforce a safe default radius if 0\.
                        if radius_m == 0 \{
                            radius_m = 1000;
                        \}
                        Some\(AccountMode::Verortet\)
                    \}'''

new_fallback = r'''                    "private" => {
                        // Legacy private records MUST NOT be projected publicly as exact or fuzzied locations
                        // unless explicitly opted in. Their semantic intent was "hidden".
                        // The safest migration path is to strip their individual location
                        // from the public sphere by treating them as RoN.
                        Some(AccountMode::Ron)
                    }'''

code = re.sub(legacy_fallback_match, new_fallback, code)

with open('apps/api/src/routes/accounts.rs', 'w') as f:
    f.write(code)
