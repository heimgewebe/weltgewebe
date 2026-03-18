import re

with open('apps/web/src/lib/map/types.ts', 'r') as f:
    code = f.read()

# Make location and public_pos strictly undefined for RoN
old_ron = r'''export interface AccountRon extends AccountBase {
  mode: 'ron';
  location\?: Location; // internal shouldn't really exist, but optional to be safe
  public_pos\?: Location; // public might not exist
  radius_m: number;
}'''

new_ron = '''export interface AccountRon extends AccountBase {
  mode: 'ron';
  location?: never; // internal location does not exist for RoN
  public_pos?: never; // public position does not exist for RoN
  radius_m: number;
}'''

code = re.sub(old_ron, new_ron, code)

with open('apps/web/src/lib/map/types.ts', 'w') as f:
    f.write(code)
