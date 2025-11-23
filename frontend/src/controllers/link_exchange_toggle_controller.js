import { Controller } from "@hotwired/stimulus";
import { showMessage } from "../utils/messages";

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
    // Check if button is disabled (for free users)
    if (this.toggleTarget.hasAttribute("disabled")) {
      return;
    }

    // Optimistically update UI
    this.enabledValue = !this.enabledValue;
    this.updateToggleState();

    fetch(`/api/projects/${this.projectIdValue}/toggle-link-exchange`, {
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
        if (body.status === "error") {
          // Revert optimistic update
          this.enabledValue = !this.enabledValue;
          this.updateToggleState();
          showMessage(body.message, "error");
        } else {
          // Server state
          this.enabledValue = body.enabled;
          this.updateToggleState(); // Sync UI with server state
          const message = this.enabledValue
            ? "Link Exchange enabled successfully"
            : "Link Exchange disabled successfully";
          showMessage(message, "success");
        }
      })
      .catch((error) => {
        // Revert optimistic update on failure
        this.enabledValue = !this.enabledValue;
        this.updateToggleState();
        console.error("Error toggling link exchange:", error);
        showMessage("Failed to toggle Link Exchange. Please try again.", "error");
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
