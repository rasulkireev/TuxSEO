import { Controller } from "@hotwired/stimulus";
import { showMessage } from "../utils/messages";

export default class extends Controller {
  static targets = ["modal", "form", "urlInput", "submitButton"];
  static values = {
    projectId: Number,
  };

  showModal(event) {
    event.preventDefault();
    this.modalTarget.classList.remove("hidden");
    document.body.style.overflow = "hidden";
  }

  hideModal(event) {
    if (event) {
      event.preventDefault();
    }
    this.modalTarget.classList.add("hidden");
    document.body.style.overflow = "";
    this.formTarget.reset();
  }

  async submit(event) {
    event.preventDefault();

    const url = this.urlInputTarget.value.trim();

    if (!url) {
      showMessage("Please enter a competitor URL.", "error");
      return;
    }

    if (!url.startsWith("http://") && !url.startsWith("https://")) {
      showMessage("URL must start with http:// or https://", "error");
      return;
    }

    this.submitButtonTarget.disabled = true;
    this.submitButtonTarget.innerHTML = `
      <svg class="inline mr-2 w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      Adding Competitor...
    `;

    try {
      const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]").value;

      const response = await fetch("/api/add-competitor", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({
          project_id: this.projectIdValue,
          url: url,
        }),
      });

      const data = await response.json();

      if (data.status === "success") {
        showMessage("Competitor added! Analysis will continue in the background. The page will reload.", "success");
        setTimeout(() => {
          window.location.reload();
        }, 1500);
      } else {
        showMessage(data.message || "Failed to add competitor. Please try again.", "error");
        this.submitButtonTarget.disabled = false;
        this.submitButtonTarget.innerHTML = "Add Competitor";
      }
    } catch (error) {
      showMessage("An error occurred. Please try again.", "error");
      this.submitButtonTarget.disabled = false;
      this.submitButtonTarget.innerHTML = "Add Competitor";
    }
  }
}
