// apps/web/src/lib/demo/demoData.ts

// Using real UUIDs to match domain schema contracts
// IDs generated via `uuidgen` (or /proc/sys/kernel/random/uuid)

export const demoNodes = [
  {
    id: "b52be17c-4ab7-4434-98ce-520f86290cf0",
    kind: "Knoten", // Schema: 'kind' is free-text string (no enum in node.schema.json). 'Knoten' is valid.
    title: "fairschenkbox",
    summary: "Öffentliche Fair-Schenk-Box",
    // Schema requirement: location must have lat/lon
    location: {
      lat: 53.558894813662505,
      lon: 10.060228407382967,
    },
    // Schema requirement: timestamps are usually expected by consumers
    created_at: "2025-01-01T12:00:00Z",
    updated_at: "2025-01-01T12:00:00Z",
    modules: [
      { id: "infos", label: "Steckbrief", locked: true, type: "standard" },
      {
        id: "besprechungen",
        label: "Forum",
        locked: true,
        type: "standard",
      },
      {
        id: "verantwortungen",
        label: "Verantwortungen",
        locked: true,
        type: "standard",
      },
    ],
  },
];

export const demoAccounts = [
  {
    id: "7d97a42e-3704-4a33-a61f-0e0a6b4d65d8",
    type: "garnrolle",
    title: "gewebespinnerAYE",
    summary: "Lokale Garnrolle / Account",
    // Public view: Internal location is hidden. Only public_pos is exposed.
    location: {
      lat: 53.5604148,
      lon: 10.0629844,
    },
    public_pos: {
      lat: 53.5604148,
      lon: 10.0629844,
    },
    visibility: "public",
    radius_m: 0,
    ron_flag: false,
    created_at: "2025-01-01T12:00:00Z",
    tags: ["account", "garnrolle", "demo"],
    modules: [
      { id: "infos", label: "Steckbrief", locked: true, type: "standard" },
      {
        id: "besprechungen",
        label: "Forum",
        locked: true,
        type: "standard",
      },
      {
        id: "verantwortungen",
        label: "Verantwortungen",
        locked: true,
        type: "standard",
      },
    ],
  },
  {
    id: "00000000-0000-0000-0000-000000000002",
    type: "garnrolle",
    title: "PrivateSpinner (Fuzzed)",
    summary: "Account with fuzziness enabled",
    // Public view: internal location would be different, but here we only show the projected public_pos
    location: {
      lat: 53.561,
      lon: 10.063,
    },
    public_pos: {
      lat: 53.561,
      lon: 10.063,
    },
    visibility: "approximate",
    radius_m: 250,
    ron_flag: false,
    created_at: "2025-01-01T12:00:00Z",
    tags: ["account", "garnrolle", "demo", "fuzzed"],
    modules: [],
  },
  {
    id: "00000000-0000-0000-0000-000000000003",
    type: "garnrolle",
    title: "InvisibleSpinner",
    summary: "Private account",
    // Public view: public_pos is undefined/null for private accounts
    location: {
      lat: 53.561,
      lon: 10.063,
    },
    visibility: "private",
    radius_m: 0,
    ron_flag: false,
    created_at: "2025-01-01T12:00:00Z",
    tags: ["account", "garnrolle", "demo", "private"],
    modules: [],
  },
];

export const demoEdges = [
  {
    id: "eb5f41ff-3e64-417e-ae7e-eecd9c886ecc",
    source_type: "account",
    // Must match the UUID of gewebespinnerAYE
    source_id: "7d97a42e-3704-4a33-a61f-0e0a6b4d65d8",
    target_type: "node",
    // Must match the UUID of fairschenkbox
    target_id: "b52be17c-4ab7-4434-98ce-520f86290cf0",
    // Schema requirement: 'edge_kind' must be a valid enum value from the domain contract.
    // Verified against contracts/domain/edge.schema.json: ["delegation", "membership", "ownership", "reference"]
    edge_kind: "reference",
    note: "faden", // Storing the metaphor here
    created_at: "2025-01-01T12:00:00Z",
  },
];
