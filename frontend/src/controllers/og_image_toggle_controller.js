import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
  static values = {
    projectId: Number,
    enabled: Boolean,
  };
  static targets = ["toggle", "switch"];

  connect() {
    this.updateToggleState();
  }

  toggle() {
    // Optimistically update UI
    this.enabledValue = !this.enabledValue;
    this.updateToggleState();

    fetch(`/api/projects/${this.projectIdValue}/toggle-og-image-generation`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    })
      .then((response) => {
        if (response.ok) {
          return response.json();
        }
        throw new Error("Server response wasn't OK");
      })
      .then((body) => {
        // Server state
        this.enabledValue = body.enabled;
        this.updateToggleState(); // Sync UI with server state
      })
      .catch((error) => {
        // Revert optimistic update on failure
        this.enabledValue = !this.enabledValue;
        this.updateToggleState();
        console.error("Error toggling OG image generation:", error);
      });
  }

  updateToggleState() {
    if (this.enabledValue) {
      this.toggleTarget.classList.add("bg-gray-600");
      this.toggleTarget.classList.remove("bg-gray-200");
      this.switchTarget.classList.add("translate-x-5");
      this.switchTarget.classList.remove("translate-x-0");
    } else {
      this.toggleTarget.classList.remove("bg-gray-600");
      this.toggleTarget.classList.add("bg-gray-200");
      this.switchTarget.classList.remove("translate-x-5");
      this.switchTarget.classList.add("translate-x-0");
    }
  }
}
