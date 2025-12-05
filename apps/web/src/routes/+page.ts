import { redirect } from "@sveltejs/kit";
import { dev } from "$app/environment";
import type { PageLoad } from "./$types";

export const load: PageLoad = () => {
  if (!dev) {
    throw redirect(307, "/map");
  }
};
