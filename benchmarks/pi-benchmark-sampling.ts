// Keep sampling comparable without changing the installed Pi profile.
export default function (pi: {
  on(event: "before_provider_request", handler: (event: { payload: unknown }) => unknown): void;
}) {
  pi.on("before_provider_request", ({ payload }) => {
    if (!payload || typeof payload !== "object" || !("model" in payload)) return;
    if (payload.model !== "coding-cyber-tiel-35b") return;
    return { ...payload, seed: 42 };
  });
}
