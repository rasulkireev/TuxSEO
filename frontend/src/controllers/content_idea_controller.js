import { Controller } from "@hotwired/stimulus";
import { showMessage } from "../utils/messages";

export default class extends Controller {
  static targets = ["form", "input"];
  static values = {
    projectId: Number
  };

  toggleForm() {
    this.formTarget.classList.toggle("hidden");
  }

  getCurrentTab() {
    // Find the active tab button
    const activeTab = document.querySelector('[data-action="title-suggestions#switchTab"].text-gray-900');
    return activeTab ? activeTab.dataset.tab : "SHARING"; // Default to SHARING if no tab is active
  }

  async generate() {
    const idea = this.inputTarget.value.trim();
    if (!idea) return;

    const button = this.element.querySelector('[data-action="content-idea#generate"]');
    const contentType = this.getCurrentTab();

    try {
      // Show loading state
      button.disabled = true;
      button.innerHTML = `
        <div class="flex gap-x-2 items-center">
          <div class="w-4 h-4 rounded-full border-2 animate-spin border-white/20 border-t-white"></div>
          <span>Generating...</span>
        </div>
      `;

      const response = await fetch("/api/generate-title-from-idea", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value
        },
        body: JSON.stringify({
          project_id: this.projectIdValue,
          user_prompt: idea,
          content_type: contentType
        })
      });

      if (!response.ok) {
        throw new Error("Failed to generate title suggestion");
      }

      const data = await response.json();

      if (data.status === "error") {
        throw new Error(data.message);
      }

      // Add the new suggestion to the active suggestions list
      const activeSuggestionsList = document.querySelector("[data-title-suggestions-target='activeSuggestionsList']");
      activeSuggestionsList.insertAdjacentHTML("beforeend", data.suggestion_html);

      // Clear the input and hide the form
      this.inputTarget.value = "";
      this.formTarget.classList.add("hidden");

      // Show the suggestions container if it was hidden
      document.querySelector("[data-title-suggestions-target='suggestionsContainer']")
        .classList.remove("hidden");

    } catch (error) {
      showMessage(error.message || "Failed to generate suggestion. Please try again later.", 'error');
    } finally {
      // Restore button state
      button.disabled = false;
      button.innerHTML = "Generate";
    }
  }

}
