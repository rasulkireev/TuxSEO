import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
  static targets = ["button", "imageContainer", "imageUrl", "imageDisplay"];
  static values = {
    blogPostId: Number,
  };

  async generate(event) {
    event.preventDefault();

    const button = this.buttonTarget;
    const originalText = button.innerHTML;

    button.disabled = true;
    button.innerHTML = `
      <svg class="inline mr-2 w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      Generating Image...
    `;

    try {
      const response = await fetch(`/api/generate-blog-image/${this.blogPostIdValue}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": this.getCSRFToken(),
        },
      });

      const data = await response.json();

      if (data.status === "success") {
        this.showImage(data.image_url);

        button.innerHTML = `
          <svg class="mr-2 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
          </svg>
          Image Generated
        `;
        button.classList.remove("bg-gray-900", "hover:bg-gray-800");
        button.classList.add("bg-green-600", "hover:bg-green-700");
      } else {
        throw new Error(data.message || "Failed to generate image");
      }
    } catch (error) {
      console.error("Error generating image:", error);
      button.innerHTML = originalText;
      button.disabled = false;
      alert(error.message || "Failed to generate image. Please try again.");
    }
  }

  showImage(imageUrl) {
    this.imageUrlTarget.value = imageUrl;
    this.imageDisplayTarget.src = imageUrl;
    this.imageContainerTarget.classList.remove("hidden");
    this.buttonTarget.classList.add("hidden");
  }

  getCSRFToken() {
    const name = "csrftoken";
    const cookies = document.cookie.split(";");
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.startsWith(name + "=")) {
        return cookie.substring(name.length + 1);
      }
    }
    return null;
  }
}
