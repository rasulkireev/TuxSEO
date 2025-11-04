import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
  static targets = ["list", "content", "sidebar"];

  connect() {
    this.generateTableOfContents();
    this.highlightCurrentSection();
    this.boundHandleScroll = this.handleScroll.bind(this);
    window.addEventListener("scroll", this.boundHandleScroll, { passive: true });
  }

  disconnect() {
    window.removeEventListener("scroll", this.boundHandleScroll);
  }

  generateTableOfContents() {
    if (!this.hasContentTarget || !this.hasListTarget) {
      return;
    }

    const headings = this.contentTarget.querySelectorAll("h2");

    if (headings.length === 0) {
      if (this.hasSidebarTarget) {
        this.sidebarTarget.style.display = "none";
      }
      return;
    }

    const tocItems = [];

    headings.forEach((heading) => {
      const headingText = heading.textContent.trim();

      let headingId = heading.id;
      if (!headingId) {
        headingId = this.generateSlug(headingText);
        heading.id = headingId;
      }

      const listItem = document.createElement("li");

      const link = document.createElement("a");
      link.href = `#${headingId}`;
      link.textContent = headingText;
      link.dataset.tocTarget = "link";
      link.dataset.section = headingId;
      link.className = `block py-1.5 pl-3 text-sm text-gray-600 border-l-2 border-gray-200 transition-colors hover:text-gray-900 hover:border-gray-400`;

      link.addEventListener("click", (event) => {
        event.preventDefault();
        this.scrollToSection(headingId);
      });

      listItem.appendChild(link);
      tocItems.push(listItem);
    });

    this.listTarget.innerHTML = "";
    tocItems.forEach(item => this.listTarget.appendChild(item));
  }

  generateSlug(text) {
    return text
      .toLowerCase()
      .replace(/[^\w\s-]/g, "")
      .replace(/\s+/g, "-")
      .replace(/-+/g, "-")
      .trim();
  }

  scrollToSection(sectionId) {
    const section = document.getElementById(sectionId);
    if (section) {
      const yOffset = -80;
      const elementPosition = section.getBoundingClientRect().top;
      const offsetPosition = elementPosition + window.pageYOffset + yOffset;

      window.scrollTo({
        top: offsetPosition,
        behavior: "smooth"
      });

      this.updateActiveLink(sectionId);
    }
  }

  handleScroll() {
    this.highlightCurrentSection();
  }

  highlightCurrentSection() {
    if (!this.hasContentTarget) {
      return;
    }

    const headings = this.contentTarget.querySelectorAll("h2");
    const scrollPosition = window.scrollY + 100;

    let currentSectionId = "";

    headings.forEach((heading) => {
      const headingPosition = heading.offsetTop;
      if (scrollPosition >= headingPosition) {
        currentSectionId = heading.id;
      }
    });

    if (currentSectionId) {
      this.updateActiveLink(currentSectionId);
    }
  }

  updateActiveLink(activeSectionId) {
    const links = this.element.querySelectorAll("[data-toc-target='link']");

    links.forEach((link) => {
      const isActive = link.dataset.section === activeSectionId;

      if (isActive) {
        link.classList.remove("border-gray-200", "text-gray-600");
        link.classList.add("border-red-600", "text-red-600", "font-medium");
      } else {
        link.classList.remove("border-red-600", "text-red-600", "font-medium");
        link.classList.add("border-gray-200", "text-gray-600");
      }
    });
  }
}
