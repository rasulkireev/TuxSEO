import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
  static targets = ["button"];
  static values = {
    content: String,
  };

  async copy() {
    await navigator.clipboard.writeText(this.contentValue);

    const button = this.buttonTarget;
    const originalText = button.innerHTML;

    button.innerHTML = `
      <svg class="mr-2 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
      </svg>
      Copied!
    `;
    button.classList.remove("hover:bg-gray-50");
    button.classList.add("bg-green-50", "text-green-700", "border-green-300");

    setTimeout(() => {
      button.innerHTML = originalText;
      button.classList.remove("bg-green-50", "text-green-700", "border-green-300");
      button.classList.add("hover:bg-gray-50");
    }, 2000);
  }
}
