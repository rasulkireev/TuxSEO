import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
  static targets = ["form", "urlInput", "submitButton", "message", "tableBody", "emptyState"];
  static values = { projectId: Number };

  toggleForm() {
    this.formTarget.classList.toggle("hidden");
    if (!this.formTarget.classList.contains("hidden")) {
      this.urlInputTarget.focus();
      this.clearMessage();
    } else {
      this.urlInputTarget.value = "";
      this.clearMessage();
    }
  }

  async addInspiration() {
    const url = this.urlInputTarget.value.trim();

    if (!url) {
      this.showMessage("Please enter a URL", "error");
      return;
    }

    if (!url.startsWith("http://") && !url.startsWith("https://")) {
      this.showMessage("URL must start with http:// or https://", "error");
      return;
    }

    this.submitButtonTarget.disabled = true;
    this.submitButtonTarget.innerHTML = `
      <svg class="animate-spin mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      Adding...
    `;

    try {
      const response = await fetch("/api/inspirations/add", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": this.getCsrfToken(),
        },
        body: JSON.stringify({
          project_id: this.projectIdValue,
          url: url,
        }),
      });

      const data = await response.json();

      if (data.status === "success") {
        this.showMessage(data.message, "success");
        this.urlInputTarget.value = "";
        
        setTimeout(() => {
          window.location.reload();
        }, 1000);
      } else {
        this.showMessage(data.message || "Failed to add inspiration", "error");
      }
    } catch (error) {
      console.error("Error adding inspiration:", error);
      this.showMessage("An error occurred. Please try again.", "error");
    } finally {
      this.submitButtonTarget.disabled = false;
      this.submitButtonTarget.innerHTML = `
        <svg class="mr-2 w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
        </svg>
        Add Inspiration
      `;
    }
  }

  async deleteInspiration(event) {
    const inspirationId = event.currentTarget.dataset.inspirationId;

    if (!confirm("Are you sure you want to delete this inspiration?")) {
      return;
    }

    try {
      const response = await fetch("/api/inspirations/delete", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": this.getCsrfToken(),
        },
        body: JSON.stringify({
          inspiration_id: parseInt(inspirationId),
        }),
      });

      const data = await response.json();

      if (data.status === "success") {
        window.location.reload();
      } else {
        alert(data.message || "Failed to delete inspiration");
      }
    } catch (error) {
      console.error("Error deleting inspiration:", error);
      alert("An error occurred. Please try again.");
    }
  }

  showMessage(text, type) {
    const messageEl = this.messageTarget;
    messageEl.classList.remove("hidden");
    
    if (type === "success") {
      messageEl.className = "mt-4 p-4 bg-green-50 border border-green-200 rounded-md text-sm text-green-800";
    } else {
      messageEl.className = "mt-4 p-4 bg-red-50 border border-red-200 rounded-md text-sm text-red-800";
    }
    
    messageEl.textContent = text;
  }

  clearMessage() {
    if (this.hasMessageTarget) {
      this.messageTarget.classList.add("hidden");
      this.messageTarget.textContent = "";
    }
  }

  getCsrfToken() {
    return document.querySelector("[name=csrfmiddlewaretoken]")?.value || 
           document.cookie.match(/csrftoken=([^;]+)/)?.[1] || "";
  }
}
