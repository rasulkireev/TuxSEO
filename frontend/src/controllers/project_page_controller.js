import { Controller } from "@hotwired/stimulus";
import { showMessage } from "../utils/messages";

export default class extends Controller {
  static targets = ["toggleButton", "toggleIcon", "toggleText"];
  static values = {
    pageId: Number,
    alwaysUse: Boolean
  };

  async toggleAlwaysUse(event) {
    event.preventDefault();

    const button = this.toggleButtonTarget;
    const originalContent = button.innerHTML;

    // Disable button and show loading state
    button.disabled = true;
    button.innerHTML = `
      <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
    `;

    try {
      const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]").value;

      const response = await fetch("/api/project-pages/toggle-always-use", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({
          page_id: this.pageIdValue,
        }),
      });

      const data = await response.json();

      if (response.ok && data.status === "success") {
        this.alwaysUseValue = data.always_use;
        this.updateButtonState();

        const message = data.always_use
          ? "Page marked to always be included in blog posts"
          : "Page will be included intelligently in blog posts";
        showMessage(message, "success");
      } else {
        showMessage(data.message || "Failed to update page setting", "error");
        button.innerHTML = originalContent;
        button.disabled = false;
      }
    } catch (error) {
      console.error("Error toggling always use:", error);
      showMessage("An error occurred. Please try again.", "error");
      button.innerHTML = originalContent;
      button.disabled = false;
    }
  }

  updateButtonState() {
    const button = this.toggleButtonTarget;
    button.disabled = false;

    if (this.alwaysUseValue) {
      button.innerHTML = `
        <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
        </svg>
        <span class="ml-1">Always Use</span>
      `;
      button.classList.remove("bg-white", "text-gray-700", "border-gray-300", "hover:bg-gray-50");
      button.classList.add("bg-green-600", "text-white", "border-green-600", "hover:bg-green-700");
    } else {
      button.innerHTML = `
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
        </svg>
        <span class="ml-1">Mark Always Use</span>
      `;
      button.classList.remove("bg-green-600", "text-white", "border-green-600", "hover:bg-green-700");
      button.classList.add("bg-white", "text-gray-700", "border-gray-300", "hover:bg-gray-50");
    }
  }

  connect() {
    this.updateButtonState();
  }
}
