/**
 * Linear flow screens. On phones they hide the tab bar and pin their main
 * action to the bottom of the screen, so there is one obvious way forward.
 */
const FLOW = ["/consent", "/intake", "/results", "/next", "/booking"];

export const isFlowRoute = (path: string) => FLOW.some((p) => path.startsWith(p));
