// apps/web/src/lib/demo/demoData.ts

export const demoNodes = [
  {
    id: "node-fairschenkbox",
    title: "fairschenkbox",
    summary: "Öffentliche Fair-Schenk-Box",
    location: {
      lat: 53.558894813662505,
      lon: 10.060228407382967,
    },
  },
];

export const demoAccounts = [
  {
    id: "account-gewebespinnerAYE",
    type: "garnrolle",
    title: "gewebespinnerAYE",
    summary: "Lokale Garnrolle / Account",
    location: {
      lat: 53.5604148,
      lon: 10.0629844,
    },
  },
];

export const demoEdges = [
  {
    id: "edge-faden-1",
    source_type: "account",
    source_id: "account-gewebespinnerAYE",
    target_type: "node",
    target_id: "node-fairschenkbox",
    edge_kind: "faden",
  },
];
