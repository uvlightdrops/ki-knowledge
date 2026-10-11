(function () {
  "use strict";
  function start() {
    const indicator = document.getElementById("node-connectivity");
    if (!indicator) return;
    let busy = false;
    let timer;
    const explanation = "HTTP node descriptor RTT; not ICMP ping or sync success.";
    function showError(message) {
      indicator.textContent = "Nodes !";
      indicator.title = explanation + " " + message;
      indicator.setAttribute("aria-label", indicator.title);
    }
    function render(data) {
      if (!Array.isArray(data.peers)) throw new Error("Invalid connectivity response");
      indicator.replaceChildren();
      indicator.href = data.status === "not_configured" ? indicator.dataset.settingsUrl : indicator.dataset.syncUrl;
      if (!data.peers.length) {
        indicator.textContent = data.status === "checking" ? "Nodes …" : "Nodes –";
        indicator.title = explanation + (data.status === "checking" ? " Check in progress." : " No other nodes configured.");
      } else {
        const details = [explanation];
        data.peers.slice(0, 3).forEach(function (peer) {
          const item = document.createElement("span");
          const dot = document.createElement("span");
          dot.className = "node-connectivity-dot";
          dot.dataset.status = peer.status === "reachable" ? "reachable" : peer.status === "not_configured" ? "not-configured" : "error";
          dot.setAttribute("aria-hidden", "true");
          const label = document.createElement("span");
          label.className = "node-connectivity-label";
          label.textContent = peer.label;
          const text = document.createElement("span");
          const reachable = peer.status === "reachable" && Number.isFinite(peer.rtt_ms);
          const status = reachable ? peer.rtt_ms + " ms" : peer.status === "not_configured" ? "–" : "!";
          text.textContent = status;
          const age = Math.max(0, Math.round(Date.now() / 1000 - peer.checked_at));
          item.title = peer.label + ": " + (reachable ? "reachable, " + status : peer.error || "Check failed")
            + "; checked " + age + " s ago; cache " + data.cache_seconds + " s; timeout " + data.timeout_ms + " ms.";
          item.setAttribute("aria-label", item.title);
          item.className = "node-connectivity-peer";
          item.append(dot, label, text);
          indicator.append(item);
          details.push(item.title);
        });
        if (data.overflow > 0) {
          const overflow = document.createElement("span");
          overflow.textContent = "+" + data.overflow;
          overflow.title = data.overflow + " more configured nodes; " + (data.unprobed || 0) + " not probed (cap 4).";
          indicator.append(overflow);
          details.push(overflow.title);
        }
        indicator.title = details.join(" ");
      }
      indicator.setAttribute("aria-label", indicator.title);
    }
    async function poll() {
      if (document.hidden || busy) return;
      busy = true;
      const controller = new AbortController();
      const timeout = setTimeout(function () { controller.abort(); }, 4000);
      try {
        const response = await fetch(indicator.dataset.endpoint, {
          credentials: "same-origin", mode: "same-origin", redirect: "error",
          cache: "no-store", signal: controller.signal, headers: {Accept: "application/json"}
        });
        if (!response.ok) throw new Error("Connectivity HTTP " + response.status);
        render(await response.json());
      } catch (error) {
        showError(error.name === "AbortError" ? "Connectivity request timed out; status unavailable."
          : "Connectivity check unavailable; previous status is no longer current.");
      } finally {
        clearTimeout(timeout);
        busy = false;
      }
    }
    function visible() {
      clearInterval(timer);
      if (!document.hidden) {
        poll();
        timer = setInterval(poll, 30000);
      }
    }
    document.addEventListener("visibilitychange", visible);
    visible();
  }
  if (document.readyState === "complete") start();
  else window.addEventListener("load", start, {once: true});
}());
