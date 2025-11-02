import { Controller } from "@hotwired/stimulus";
import { showMessage } from "../utils/messages";

export default class extends Controller {
  static values = {
    projectId: Number,
    currentTab: String
  };

  static targets = ["suggestionsList", "suggestionsContainer", "activeSuggestionsList", "vsCompetitorSection"];

  connect() {
    // Get the last selected tab from localStorage, default to "SHARING" if none exists
    this.currentTabValue = localStorage.getItem("selectedTab") || "SHARING";

    // Update initial tab UI
    const tabs = this.element.querySelectorAll("[data-action='title-suggestions#switchTab']");
    tabs.forEach(t => {
      if (t.dataset.tab === this.currentTabValue) {
        t.classList.add("text-gray-900", "border-b-2", "border-gray-900");
        t.classList.remove("text-gray-500", "hover:text-gray-700", "border-transparent", "hover:border-gray-300");
      } else {
        t.classList.remove("text-gray-900", "border-b-2", "border-gray-900");
        t.classList.add("text-gray-500", "hover:text-gray-700", "border-b-2", "border-transparent", "hover:border-gray-300");
      }
    });

    // Filter suggestions based on initial tab
    this.filterSuggestions();
  }

  switchTab(event) {
    const selectedTab = event.currentTarget.dataset.tab;
    this.currentTabValue = selectedTab;
    localStorage.setItem("selectedTab", selectedTab);

    // Update tab UI
    const tabs = this.element.querySelectorAll("[data-action='title-suggestions#switchTab']");
    tabs.forEach(t => {
      if (t.dataset.tab === selectedTab) {
        t.classList.add("text-gray-900", "border-b-2", "border-gray-900");
        t.classList.remove("text-gray-500", "hover:text-gray-700", "border-transparent", "hover:border-gray-300");
      } else {
        t.classList.remove("text-gray-900", "border-b-2", "border-gray-900");
        t.classList.add("text-gray-500", "hover:text-gray-700", "border-b-2", "border-transparent", "hover:border-gray-300");
      }
    });

    this.filterSuggestions();
  }

  filterSuggestions() {
    if (this.currentTabValue === "VS_COMPETITOR") {
      if (this.hasVsCompetitorSectionTarget) {
        this.vsCompetitorSectionTarget.classList.remove("hidden");
      }
      const archivedLists = this.element.querySelectorAll(".archived-list");
      archivedLists.forEach(list => list.classList.add("hidden"));
    } else {
      if (this.hasVsCompetitorSectionTarget) {
        this.vsCompetitorSectionTarget.classList.add("hidden");
      }
      const archivedLists = this.element.querySelectorAll(".archived-list");
      archivedLists.forEach(list => list.classList.remove("hidden"));
      
      const suggestions = this.suggestionsListTarget.querySelectorAll("[data-suggestion-type]");
      suggestions.forEach(suggestion => {
        if (suggestion.dataset.suggestionType === this.currentTabValue) {
          suggestion.classList.remove("hidden");
        } else {
          suggestion.classList.add("hidden");
        }
      });
    }
  }



  async generate(event) {
    event.preventDefault();
    const button = event.currentTarget;

    try {
      // Show loading state
      button.disabled = true;
      button.innerHTML = `
        <div class="flex gap-x-2 items-center">
          <div class="w-4 h-4 rounded-full border-2 border-gray-300 animate-spin border-t-gray-700"></div>
          <span>Generating...</span>
        </div>
      `;

      // Make API call
      const response = await fetch('/api/generate-title-suggestions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector("[name=csrfmiddlewaretoken]").value
        },
        body: JSON.stringify({
          project_id: this.projectIdValue,
          content_type: this.currentTabValue
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.message || "Failed to generate suggestions");
      }

      const { suggestions_html, status, message } = await response.json();

      if (status === "error") {
        console.log(message);
        throw new Error(message || "Failed to generate suggestions");
      }

      this.suggestionsContainerTarget.classList.remove('hidden');
      suggestions_html.forEach(html => {
        this.activeSuggestionsListTarget.insertAdjacentHTML('beforeend', html);
      });

      // Restore button state
      button.disabled = false;
      button.innerHTML = `
        <svg class="mr-2 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
        </svg>
        Generate More Ideas
      `;

    } catch (error) {
      button.disabled = false;
      button.innerHTML = `
        <svg class="mr-2 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
        </svg>
        Generate More Ideas
      `;

      showMessage(error.message, 'error');
    }
  }
}
