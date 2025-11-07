import { Controller } from "@hotwired/stimulus";
import { showMessage } from "../utils/messages";

export default class extends Controller {
  static targets = ["button", "emptyState", "imageContainer", "imageUrl", "imageDisplay"];
  static values = {
    blogPostId: Number,
  };

  async generate() {
    const original_button_content = this.buttonTarget.innerHTML;

    try {
      this.buttonTarget.disabled = true;
      this.buttonTarget.innerHTML = `
        <svg class="mr-2 w-4 h-4 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        Generating...
      `;

      const csrf_token = document.querySelector("[name=csrfmiddlewaretoken]").value;

      const response = await fetch("/api/generate-og-image", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrf_token,
        },
        body: JSON.stringify({
          blog_post_id: this.blogPostIdValue,
        }),
      });

      const data = await response.json();

      if (!response.ok || data.status === "error") {
        throw new Error(data.message || "Failed to generate image");
      }

      showMessage("OG image generated successfully!", "success");

      if (this.hasEmptyStateTarget) {
        this.emptyStateTarget.classList.add("hidden");
      }

      if (this.hasImageContainerTarget) {
        this.imageContainerTarget.classList.remove("hidden");

        if (this.hasImageUrlTarget) {
          this.imageUrlTarget.value = data.image_url;
        }

        if (this.hasImageDisplayTarget) {
          this.imageDisplayTarget.src = data.image_url;
        }
      } else {
        setTimeout(() => {
          window.location.reload();
        }, 1000);
      }
    } catch (error) {
      console.error("Error generating OG image:", error);
      showMessage(error.message || "Failed to generate OG image. Please try again.", "error");

      this.buttonTarget.disabled = false;
      this.buttonTarget.innerHTML = original_button_content;
    }
  }
}
