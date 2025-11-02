import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
  static targets = ["button", "status"];
  static values = {
    competitorId: Number,
  };

  async generate(event) {
    event.preventDefault();

    const button = event.currentTarget;
    const originalContent = button.innerHTML;

    button.disabled = true;
    button.innerHTML = `
      <svg class="w-4 h-4 mr-2 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      Generating...
    `;

    try {
      const response = await fetch("/api/generate-vs-competitor-title", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": this.getCSRFToken(),
        },
        body: JSON.stringify({
          competitor_id: this.competitorIdValue,
        }),
      });

      const data = await response.json();

      if (data.status === "success" && data.suggestion_html) {
        const container = document.getElementById("vs-competitor-suggestions");
        if (container) {
          const tempDiv = document.createElement("div");
          tempDiv.innerHTML = data.suggestion_html;
          container.insertBefore(tempDiv.firstChild, container.firstChild);
        }

        button.innerHTML = `
          <svg class="mr-2 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
          </svg>
          Generated
        `;

        setTimeout(() => {
          button.innerHTML = originalContent;
          button.disabled = false;
        }, 2000);
      } else {
        this.showError(button, originalContent, data.message || "Failed to generate title");
      }
    } catch (error) {
      console.error("Error generating vs competitor title:", error);
      this.showError(button, originalContent, "An error occurred. Please try again.");
    }
  }

  showError(button, originalContent, message) {
    button.innerHTML = `
      <svg class="mr-2 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
      </svg>
      Error
    `;

    const errorDiv = document.createElement("div");
    errorDiv.className = "mt-2 p-3 text-sm text-red-700 bg-red-50 rounded-md";
    errorDiv.innerHTML = message;
    button.parentElement.appendChild(errorDiv);

    setTimeout(() => {
      button.innerHTML = originalContent;
      button.disabled = false;
      errorDiv.remove();
    }, 3000);
  }

  getCSRFToken() {
    const token = document.querySelector("[name=csrfmiddlewaretoken]");
    return token ? token.value : "";
  }
}
