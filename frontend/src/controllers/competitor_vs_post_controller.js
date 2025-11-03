import { Controller } from "@hotwired/stimulus";
import { showMessage } from "../utils/messages";

export default class extends Controller {
  static values = {
    competitorId: Number,
    projectId: Number
  };

  static targets = ["buttonContainer"];

  async generatePost(event) {
    event.preventDefault();
    const button = event.currentTarget;

    try {
      button.disabled = true;
      button.innerHTML = `
        <div class="flex gap-x-2 items-center">
          <div class="w-4 h-4 rounded-full border-2 border-gray-300 animate-spin border-t-gray-700"></div>
          <span>Generating...</span>
        </div>
      `;

      const response = await fetch("/api/generate-competitor-vs-title", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value
        },
        body: JSON.stringify({
          competitor_id: this.competitorIdValue
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.message || "Failed to generate vs. blog post");
      }

      const data = await response.json();

      if (data.status === "error") {
        throw new Error(data.message || "Failed to generate vs. blog post");
      }

      showMessage("VS blog post generated successfully!", "success");

      const viewPostUrl = `/project/${this.projectIdValue}/competitor/${this.competitorIdValue}/post/`;

      button.outerHTML = `
        <a href="${viewPostUrl}"
           class="inline-flex items-center px-3 py-1.5 text-xs font-medium text-white bg-gray-900 rounded-md border border-gray-900 hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-500">
          <svg class="mr-1.5 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
          </svg>
          View Post
        </a>
      `;

    } catch (error) {
      button.disabled = false;
      button.innerHTML = `
        <svg class="mr-1.5 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path>
        </svg>
        Generate Post
      `;

      showMessage(error.message, "error");
    }
  }
}
