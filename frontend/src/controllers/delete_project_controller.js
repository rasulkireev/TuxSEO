import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
  static targets = ["modal", "form"];

  connect() {
    this.boundHandleEscape = this.handleEscape.bind(this);
  }

  showModal() {
    if (this.hasModalTarget) {
      this.modalTarget.classList.remove("hidden");
      this.modalTarget.classList.remove("opacity-0", "pointer-events-none");

      document.addEventListener("keydown", this.boundHandleEscape);

      const firstFocusable = this.modalTarget.querySelector("button:not([disabled])");
      if (firstFocusable) {
        setTimeout(() => {
          firstFocusable.focus();
        }, 100);
      }
    }
  }

  hideModal() {
    if (this.hasModalTarget) {
      this.modalTarget.classList.add("opacity-0", "pointer-events-none");

      setTimeout(() => {
        this.modalTarget.classList.add("hidden");
      }, 300);

      document.removeEventListener("keydown", this.boundHandleEscape);
    }
  }

  handleEscape(event) {
    if (event.key === "Escape") {
      this.hideModal();
    }
  }

  submitDelete(event) {
    event.preventDefault();

    if (this.hasFormTarget) {
      this.formTarget.submit();
    }
  }

  disconnect() {
    document.removeEventListener("keydown", this.boundHandleEscape);
  }
}
