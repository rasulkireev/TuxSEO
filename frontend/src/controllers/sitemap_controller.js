import { Controller } from "@hotwired/stimulus";
import { showMessage } from "../utils/messages";

export default class extends Controller {
  static targets = ["form", "input", "submitButton", "formElement"];

  showForm(event) {
    event.preventDefault();
    this.formTarget.classList.remove("hidden");
  }

  hideForm(event) {
    event.preventDefault();
    this.formTarget.classList.add("hidden");
  }

  async submit(event) {
    event.preventDefault();

    const formData = new FormData(this.formElementTarget);
    const projectId = formData.get("project_id");
    const sitemapUrl = formData.get("sitemap_url");

    if (!sitemapUrl) {
      showMessage("Please enter a valid sitemap URL", "error");
      return;
    }

    // Disable submit button
    this.submitButtonTarget.disabled = true;
    this.submitButtonTarget.innerHTML = `
      <svg class="mr-2 w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      Processing...
    `;

    try {
      const response = await fetch(`/api/project/${projectId}/sitemap/submit/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": formData.get("csrfmiddlewaretoken"),
        },
        body: JSON.stringify({
          sitemap_url: sitemapUrl,
        }),
      });

      const data = await response.json();

      if (response.ok) {
        showMessage(data.message || "Sitemap submitted successfully! Your pages will be analyzed shortly.", "success");

        // Reload page after a brief delay to show the updated state
        setTimeout(() => {
          window.location.reload();
        }, 1500);
      } else {
        showMessage(data.error || "Failed to submit sitemap. Please try again.", "error");

        // Re-enable submit button
        this.submitButtonTarget.disabled = false;
        this.submitButtonTarget.innerHTML = `
          <svg class="mr-2 w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
          </svg>
          Submit Sitemap
        `;
      }
    } catch (error) {
      console.error("Error submitting sitemap:", error);
      showMessage("An error occurred while submitting the sitemap. Please try again.", "error");

      // Re-enable submit button
      this.submitButtonTarget.disabled = false;
      this.submitButtonTarget.innerHTML = `
        <svg class="mr-2 w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
        </svg>
        Submit Sitemap
      `;
    }
  }
}
