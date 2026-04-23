import { error } from "@sveltejs/kit";

export const load = async () => {
  // In production builds (adapter-static), this will throw 404
  // which effectively marks the page as non-existent.
  if (import.meta.env.PROD) {
    error(404, "Not found");
  }
};
