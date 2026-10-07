(() => {
  const form = document.getElementById("jira-support-chat-form");
  const question = document.getElementById("chat-question");
  const limit = document.getElementById("chat-limit");
  const status = document.getElementById("chat-status");
  const liveQuestion = document.getElementById("chat-live-question");
  const submit = document.getElementById("chat-submit");

  const updatePreview = () => {
    const text = (question?.value || "").trim();
    liveQuestion.textContent = text || "—";
    status.textContent = text ? `Bereit · Kontext-Limit ${limit?.value || 8}` : "Bereit";
  };

  question?.addEventListener("input", updatePreview);
  limit?.addEventListener("input", updatePreview);
  form?.addEventListener("submit", () => {
    const text = (question?.value || "").trim();
    status.textContent = text ? `Sende an KI: "${text}"` : "Sende an KI...";
    if (submit) {
      submit.disabled = true;
      submit.textContent = "Sende...";
    }
  });

  updatePreview();
})();
