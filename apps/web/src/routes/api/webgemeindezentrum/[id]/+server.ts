import { error, json, type RequestEvent } from "@sveltejs/kit";
import { demoWebgemeindezentrumDetails } from "$lib/demo/demoData";

export const prerender = true;
export const entries = () =>
  demoWebgemeindezentrumDetails.map((center) => ({ id: center.id }));

export function GET({ params }: RequestEvent) {
  const id = params.id?.trim();
  if (!id) throw error(400, "ID is required");

  const center = demoWebgemeindezentrumDetails.find((item) => item.id === id);
  if (!center) throw error(404, "Webgemeindezentrum not found");

  return json({
    ...center,
    governance: {
      proposal_count: 0,
      open_proposal_count: 0,
      voting_proposal_count: 0,
      conversation_message_count: 0,
    },
  });
}
