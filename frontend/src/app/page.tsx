import { redirect } from "next/navigation";

/**
 * The library is the only built surface, so the root sends people there rather
 * than showing a landing page that only repeats the sidebar.
 */
export default function Home() {
  redirect("/library");
}
