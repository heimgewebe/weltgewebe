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
  },
];

export const demoAccounts = [
  {
    id: "7d97a42e-3704-4a33-a61f-0e0a6b4d65d8",
    type: "garnrolle",
    title: "gewebespinnerAYE",
    summary: "Lokale Garnrolle / Account",
    // In strict public view, this is the public_pos.
    // We add radius_m and ron_flag to simulate the expanded model.
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
  },
  {
    id: "00000000-0000-0000-0000-000000000002",
    type: "garnrolle",
    title: "PrivateSpinner (Fuzzed)",
    summary: "Account with fuzziness enabled",
    // Simulating that public_pos is slightly different from a hypothetical 'real' location
    location: {
       lat: 53.5610000,
       lon: 10.0630000,
    },
    public_pos: {
       lat: 53.5610000,
       lon: 10.0630000,
    },
    visibility: "approximate",
    radius_m: 250,
    ron_flag: false,
    created_at: "2025-01-01T12:00:00Z",
    tags: ["account", "garnrolle", "demo", "fuzzed"],
  }
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
