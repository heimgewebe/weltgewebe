import type {
  Webgemeindezentrum,
  WebgemeindezentrumLocationState,
} from "$lib/map/types";

export interface WebgemeindezentrumGovernanceSummary {
  proposal_count: number;
  open_proposal_count: number;
  voting_proposal_count: number;
  conversation_message_count: number;
}

export interface WebgemeindezentrumLocationHistoryEvent {
  event_id: number;
  event_type: string;
  location_state: WebgemeindezentrumLocationState;
  location_state_label: string;
  location: { lat: number; lon: number };
  location_label: string;
  reason: string;
  decided_at: string;
}

export type WebgemeindezentrumDetails = Webgemeindezentrum & {
  governance: WebgemeindezentrumGovernanceSummary;
  location_history?: WebgemeindezentrumLocationHistoryEvent[];
};

export function emptyWebgemeindezentrumGovernance(): WebgemeindezentrumGovernanceSummary {
  return {
    proposal_count: 0,
    open_proposal_count: 0,
    voting_proposal_count: 0,
    conversation_message_count: 0,
  };
}

export function webgemeindezentrumTruthHeading(
  state: WebgemeindezentrumLocationState | undefined,
): string {
  if (state === "confirmed") return "Bestätigter Treffort";
  if (state === "unavailable") return "Derzeit nicht verfügbar";
  if (state === "relocation_proposed") return "Verlegung vorgeschlagen";
  if (state === "provisional") return "Vorläufiger Treffort";
  return "Noch keine Bestätigung";
}
