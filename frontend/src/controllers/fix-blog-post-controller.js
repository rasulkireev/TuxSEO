import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
  static values = { generatedPostId: Number };
  static targets = ["button", "buttonText", "buttonIcon"];

  connect() {
    this.originalButtonText = this.buttonTextTarget.textContent;
    this.originalButtonIcon = this.buttonIconTarget.innerHTML;
  }

  async fix() {
    // Disable button and show loading state
    this.buttonTarget.disabled = true;
    this.buttonTextTarget.textContent = "Fixing...";
    this.buttonIconTarget.innerHTML = `
      <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
    `;

    try {
      const response = await fetch("/api/fix-generated-blog-post", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": this.getCSRFToken(),
        },
        body: JSON.stringify({
          id: this.generatedPostIdValue
        })
      });

      const data = await response.json();

      if (data.status === "success") {
        // Reload the page on success
        window.location.reload();
      } else {
        // Show error message
        alert(data.message || "Failed to fix blog post");
        this.resetButton();
      }
    } catch (error) {
      console.error("Error fixing blog post:", error);
      alert("An error occurred while fixing the blog post");
      this.resetButton();
    }
  }

  resetButton() {
    this.buttonTarget.disabled = false;
    this.buttonTextTarget.textContent = this.originalButtonText;
    this.buttonIconTarget.innerHTML = this.originalButtonIcon;
  }

  getCSRFToken() {
    const token = document.querySelector("[name=\"csrfmiddlewaretoken\"]")?.value;
    if (token) return token;

    // Fallback: try to get from cookie
    const cookies = document.cookie.split(";");
    for (let cookie of cookies) {
      const [name, value] = cookie.trim().split("=");
      if (name === "csrftoken") {
        return value;
      }
    }
    return "";
  }
}
