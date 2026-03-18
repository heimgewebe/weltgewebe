import re

with open('apps/api/src/routes/accounts.rs', 'r') as f:
    code = f.read()

# I see `cargo fmt` likely changed the whitespace formatting of the block,
# making my previous regex replacement miss it. Let's do a more robust regex.

old_block = r'''"private" => \{
.*?
                        Some\(AccountMode::Verortet\)
                    \}'''

new_block = '''"private" => {
                        // Legacy private records MUST NOT be projected publicly as exact or fuzzied locations
                        // unless explicitly opted in. Their semantic intent was "hidden".
                        // The safest migration path is to strip their individual location
                        // from the public sphere by treating them as RoN.
                        Some(AccountMode::Ron)
                    }'''

code = re.sub(old_block, new_block, code, flags=re.DOTALL)

with open('apps/api/src/routes/accounts.rs', 'w') as f:
    f.write(code)
