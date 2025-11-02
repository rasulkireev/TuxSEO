import { Controller } from "@hotwired/stimulus";
import { marked } from "marked";
import DOMPurify from "dompurify";

export default class extends Controller {
  static targets = ["source", "button"];

  async copyAsHtml() {
    const markdownText = this.sourceTarget.value;
    
    const rawHtml = marked.parse(markdownText);
    const cleanHtml = DOMPurify.sanitize(rawHtml);
    
    await navigator.clipboard.writeText(cleanHtml);

    const button = this.buttonTarget;
    const originalText = button.textContent;

    button.textContent = "Copied!";
    button.classList.remove(
      "bg-gray-900",
      "hover:bg-gray-800",
    );
    button.classList.add(
      "bg-green-600",
      "hover:bg-green-700",
    );

    setTimeout(() => {
      button.textContent = originalText;
      button.classList.remove(
        "bg-green-600",
        "hover:bg-green-700",
      );
      button.classList.add(
        "bg-gray-900",
        "hover:bg-gray-800",
      );
    }, 2000);
  }
}
