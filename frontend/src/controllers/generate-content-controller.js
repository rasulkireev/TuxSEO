import { Controller } from "@hotwired/stimulus";
import { showMessage } from "../utils/messages";
export default class extends Controller {
  static values = {
    url: String,
    suggestionId: Number,
    projectId: Number,
    blogPostId: Number,
    hasProSubscription: Boolean,
    hasAutoSubmissionSetting: Boolean,
    pricingUrl: String,
    projectSettingsUrl: String
  };

  static targets = [
    "status",
    "content",
    "buttonContainer",
    "dropdown",
    "chevron",
    "postButtonContainer"
  ];

  connect() {
    this.expandedValue = false;
  }

  toggle() {
    this.expandedValue = !this.expandedValue;

    if (this.hasDropdownTarget) {
      this.dropdownTarget.classList.toggle("hidden");
    }

    if (this.hasChevronTarget) {
      this.chevronTarget.classList.toggle("rotate-180");
    }
  }

  async generate(event) {
    event.preventDefault();

    try {
      // Update button to show loading state
      this.buttonContainerTarget.innerHTML = `
        <button
          disabled
          class="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-gray-900 rounded-md border border-gray-900 opacity-75 cursor-not-allowed">
          <svg class="mr-2 w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          Generating...
        </button>
      `;

      // Show progress dialog
      this._showProgressDialog();

      // Start the pipeline
      const startResponse = await fetch(`/api/generate-blog-content-pipeline/${this.suggestionIdValue}/start`, {
        method: "POST",
        headers: {
          "X-CSRFToken": this._getCsrfToken()
        }
      });

      if (!startResponse.ok) {
        const error = await startResponse.json();
        throw new Error(error.message || "Failed to start generation");
      }

      const startData = await startResponse.json();
      this.blogPostId = startData.blog_post_id;
      this.pipelineSteps = ["structure", "content", "preliminary_validation", "internal_links", "final_validation"];

      // Execute each step of the pipeline
      for (const step of this.pipelineSteps) {
        await this._executeStep(step);
      }

      // Hide progress dialog
      this._hideProgressDialog();

      // Update button to "View Post"
      this.buttonContainerTarget.innerHTML = `
        <a
          href="/project/${this.projectIdValue}/post/${this.blogPostId}/"
          class="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-gray-900 rounded-md border border-gray-900 hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-500">
          <svg class="mr-2 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
          </svg>
          View Post
        </a>
      `;

      // Update status to show completed state
      if (this.hasStatusTarget) {
        this.statusTarget.innerHTML = `
          <div class="flex gap-1.5 items-center">
            <div class="w-3 h-3 bg-green-500 rounded-full"></div>
            <span class="text-sm font-medium text-green-700">Generated</span>
          </div>
        `;
      }

      // Handle the post button
      this._appendPostButton(this.postButtonContainerTarget, this.blogPostId);

      showMessage("Blog post generated successfully!", 'success');

    } catch (error) {
      this._hideProgressDialog();
      showMessage(error.message || "Failed to generate content. Please try again later.", 'error');

      // Reset the button to original state
      this.buttonContainerTarget.innerHTML = `
        <button
          data-action="generate-content#generate"
          class="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-gray-900 rounded-md border border-gray-900 hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-500">
          <svg class="mr-2 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
          </svg>
          Generate
        </button>
      `;

      // Reset status if available
      if (this.hasStatusTarget) {
        this.statusTarget.innerHTML = `
          <div class="flex gap-1.5 items-center">
            <div class="w-3 h-3 bg-gray-400 rounded-full"></div>
            <span class="text-sm text-gray-600">Ready to generate</span>
          </div>
        `;
      }
    }
  }

  async continue(event) {
    event.preventDefault();

    // Get the blog post ID from the button's data attribute
    const blog_post_id = event.currentTarget.dataset.generateContentBlogPostIdValue;
    this.blogPostId = parseInt(blog_post_id);

    try {
      // Update button to show loading state
      this.buttonContainerTarget.innerHTML = `
        <button
          disabled
          class="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md border border-blue-600 opacity-75 cursor-not-allowed">
          <svg class="mr-2 w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          Continuing...
        </button>
      `;

      // Show progress dialog
      this._showProgressDialog();

      // Get current pipeline status
      const statusResponse = await fetch(`/api/generate-blog-content-pipeline/${this.blogPostId}/status`, {
        method: "GET",
        headers: {
          "X-CSRFToken": this._getCsrfToken()
        }
      });

      if (!statusResponse.ok) {
        throw new Error("Failed to get pipeline status");
      }

      const statusData = await statusResponse.json();

      // Map backend step names to frontend step names
      const step_name_map = {
        "generate_structure": "structure",
        "generate_content": "content",
        "preliminary_validation": "preliminary_validation",
        "insert_internal_links": "internal_links",
        "final_validation": "final_validation"
      };

      // Update progress dialog with current state
      if (statusData.steps) {
        for (const [backend_step_name, step_info] of Object.entries(statusData.steps)) {
          const frontend_step_name = step_name_map[backend_step_name];
          if (frontend_step_name && step_info.status === "completed") {
            this._updateProgressStep(frontend_step_name, "completed", this._getStepDisplayName(frontend_step_name));
          }
        }
      }

      // Determine which steps need to be executed
      this.pipelineSteps = ["structure", "content", "preliminary_validation", "internal_links", "final_validation"];
      const steps_to_execute = [];

      for (const frontend_step of this.pipelineSteps) {
        const backend_step = this._getBackendStepName(frontend_step);
        const step_status = statusData.steps?.[backend_step];

        if (!step_status || step_status.status !== "completed") {
          steps_to_execute.push(frontend_step);
        }
      }

      // Execute remaining steps
      for (const step of steps_to_execute) {
        await this._executeStep(step);
      }

      // Hide progress dialog
      this._hideProgressDialog();

      // Update button to "View Post"
      this.buttonContainerTarget.innerHTML = `
        <a
          href="/project/${this.projectIdValue}/post/${this.blogPostId}/"
          class="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-gray-900 rounded-md border border-gray-900 hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-500">
          <svg class="mr-2 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
          </svg>
          View Post
        </a>
      `;

      // Update status to show completed state
      if (this.hasStatusTarget) {
        this.statusTarget.innerHTML = `
          <div class="flex gap-1.5 items-center">
            <div class="w-3 h-3 bg-green-500 rounded-full"></div>
            <span class="text-sm font-medium text-green-700">Generated</span>
          </div>
        `;
      }

      // Handle the post button
      this._appendPostButton(this.postButtonContainerTarget, this.blogPostId);

      showMessage("Blog post generation completed!", 'success');

    } catch (error) {
      this._hideProgressDialog();
      showMessage(error.message || "Failed to continue generation. Please try again later.", 'error');

      // Reset the button to Continue state
      this.buttonContainerTarget.innerHTML = `
        <button
          data-action="generate-content#continue"
          data-generate-content-blog-post-id-value="${this.blogPostId}"
          class="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md border border-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500">
          <svg class="mr-2 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path>
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
          </svg>
          Continue
        </button>
      `;
    }
  }

  async _executeStep(step_name) {
    const step_display_names = {
      "structure": "Generating Structure",
      "content": "Generating Content",
      "preliminary_validation": "Validating Content",
      "internal_links": "Adding Internal Links",
      "final_validation": "Final Validation"
    };

    // Map frontend step names to backend internal step names
    const backend_step_names = {
      "structure": "generate_structure",
      "content": "generate_content",
      "preliminary_validation": "preliminary_validation",
      "internal_links": "insert_internal_links",
      "final_validation": "final_validation"
    };

    // Update progress dialog to show current step
    this._updateProgressStep(step_name, "in_progress", step_display_names[step_name]);

    try {
      const response = await fetch(`/api/generate-blog-content-pipeline/${this.blogPostId}/step/${step_name}`, {
        method: "POST",
        headers: {
          "X-CSRFToken": this._getCsrfToken()
        }
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.message || `Failed to execute ${step_name}`);
      }

      const data = await response.json();

      // Get the backend step name to check status
      const backend_step_name = backend_step_names[step_name];
      const step_status = data.pipeline_state?.steps?.[backend_step_name];

      // Check if step failed and needs retry
      if (step_status && step_status.status === "failed") {
        this._updateProgressStep(step_name, "failed", `${step_display_names[step_name]} Failed`);
        throw new Error(step_status.error || `Step ${step_name} failed`);
      }

      // Update progress dialog to show step completed
      this._updateProgressStep(step_name, "completed", step_display_names[step_name]);

    } catch (error) {
      this._updateProgressStep(step_name, "failed", step_display_names[step_name]);
      throw error;
    }
  }

  _showProgressDialog() {
    const dialog = document.createElement("div");
    dialog.id = "generation-progress-dialog";
    dialog.className = "fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50";
    dialog.innerHTML = `
      <div class="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
        <h3 class="text-lg font-semibold mb-4">Generating Blog Post</h3>
        <div id="progress-steps" class="space-y-3">
          <div data-step="structure" class="flex items-center gap-3">
            <div class="step-icon w-6 h-6"></div>
            <span class="step-text text-sm">Generating Structure</span>
          </div>
          <div data-step="content" class="flex items-center gap-3">
            <div class="step-icon w-6 h-6"></div>
            <span class="step-text text-sm">Generating Content</span>
          </div>
          <div data-step="preliminary_validation" class="flex items-center gap-3">
            <div class="step-icon w-6 h-6"></div>
            <span class="step-text text-sm">Validating Content</span>
          </div>
          <div data-step="internal_links" class="flex items-center gap-3">
            <div class="step-icon w-6 h-6"></div>
            <span class="step-text text-sm">Adding Internal Links</span>
          </div>
          <div data-step="final_validation" class="flex items-center gap-3">
            <div class="step-icon w-6 h-6"></div>
            <span class="step-text text-sm">Final Validation</span>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(dialog);
  }

  _hideProgressDialog() {
    const dialog = document.getElementById("generation-progress-dialog");
    if (dialog) {
      dialog.remove();
    }
  }

  _updateProgressStep(step_name, status, display_text) {
    const step_element = document.querySelector(`[data-step="${step_name}"]`);
    if (!step_element) return;

    const icon = step_element.querySelector(".step-icon");
    const text = step_element.querySelector(".step-text");

    if (status === "in_progress") {
      icon.innerHTML = `
        <svg class="animate-spin h-5 w-5 text-blue-600" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
      `;
      text.className = "step-text text-sm font-medium text-blue-600";
    } else if (status === "completed") {
      icon.innerHTML = `
        <svg class="h-5 w-5 text-green-600" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
        </svg>
      `;
      text.className = "step-text text-sm text-gray-600 line-through";
    } else if (status === "failed") {
      icon.innerHTML = `
        <svg class="h-5 w-5 text-red-600" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
        </svg>
      `;
      text.className = "step-text text-sm font-medium text-red-600";
    }

    text.textContent = display_text;
  }

  _getCsrfToken() {
    return document.querySelector("[name=csrfmiddlewaretoken]").value;
  }

  _getStepDisplayName(step_name) {
    const display_names = {
      "structure": "Generating Structure",
      "content": "Generating Content",
      "preliminary_validation": "Validating Content",
      "internal_links": "Adding Internal Links",
      "final_validation": "Final Validation"
    };
    return display_names[step_name] || step_name;
  }

  _getBackendStepName(frontend_step_name) {
    const backend_names = {
      "structure": "generate_structure",
      "content": "generate_content",
      "preliminary_validation": "preliminary_validation",
      "internal_links": "insert_internal_links",
      "final_validation": "final_validation"
    };
    return backend_names[frontend_step_name] || frontend_step_name;
  }

  _appendPostButton(container, generatedPostId) {
    container.innerHTML = '';

    const profileSettingsJSON = localStorage.getItem("userProfileSettings");
    const projectSettingsJSON = localStorage.getItem(`projectSettings:${this.projectIdValue}`);

    const profileSettings = profileSettingsJSON ? JSON.parse(profileSettingsJSON) : {};
    const projectSettings = projectSettingsJSON ? JSON.parse(projectSettingsJSON) : {};

    const hasPro = profileSettings.has_pro_subscription || false;
    const hasAutoSubmit = projectSettings.has_auto_submission_setting || false;

    let buttonHtml;

    if (hasPro && hasAutoSubmit) {
      // Pro user with settings: Enabled Post button
      buttonHtml = `
        <button
          data-action="post-button#post"
          class="inline-flex items-center px-3 py-1.5 text-xs font-medium text-white bg-gray-800 rounded border border-gray-800 transition-colors hover:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-gray-500"
        >
          <svg class="mr-1 w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path>
          </svg>
          Post
        </button>
      `;
    } else if (hasPro && !hasAutoSubmit) {
      // Pro user without settings: Disabled link to settings
      buttonHtml = `
        <a
          href="${this.projectSettingsUrlValue}#blogging-agent-settings"
          class="inline-flex items-center px-3 py-1.5 text-xs font-medium text-gray-500 bg-gray-100 rounded border border-gray-200 transition-colors hover:bg-gray-50"
          data-controller="tooltip"
          data-tooltip-message-value="You need to set up the API endpoint for automatic posting in your project settings."
          data-action="mouseenter->tooltip#show mouseleave->tooltip#hide"
        >
          <svg class="mr-1 w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
          </svg>
          Setup
        </a>
      `;
    } else {
      // Not a pro user: Disabled link to pricing
      buttonHtml = `
        <a
          href="${this.pricingUrlValue}"
          class="inline-flex items-center px-3 py-1.5 text-xs font-medium text-gray-500 bg-gray-100 rounded border border-gray-200 transition-colors hover:bg-gray-50"
          data-controller="tooltip"
          data-tooltip-message-value="This feature is available for Pro subscribers only."
          data-action="mouseenter->tooltip#show mouseleave->tooltip#hide"
        >
          <svg class="mr-1 w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path>
          </svg>
          Pro Only
        </a>
      `;
    }

    const wrapperDiv = document.createElement('div');
    wrapperDiv.setAttribute('data-controller', 'post-button');
    wrapperDiv.setAttribute('data-post-button-generated-post-id-value', generatedPostId);
    wrapperDiv.setAttribute('data-post-button-project-id-value', this.projectIdValue);
    wrapperDiv.innerHTML = buttonHtml.trim();

    container.appendChild(wrapperDiv);
  }

  createFormGroup(id, value, label, isTextarea = false, extraClasses = "") {
    const div = document.createElement("div");
    div.setAttribute("data-controller", "copy");
    div.className = "relative" + (isTextarea ? " mb-4" : "");

    // Create label
    const labelEl = document.createElement("label");
    labelEl.className = "block text-sm font-medium text-gray-700";
    labelEl.textContent = label;

    // Create input/textarea
    const input = document.createElement(isTextarea ? "textarea" : "input");
    input.value = value;
    input.id = id;
    input.setAttribute("data-copy-target", "source");
    input.className = `block mt-1 ${isTextarea ? "mb-2" : ""} w-full font-mono text-sm rounded-md border sm:text-sm pr-20 ${extraClasses}`;
    input.readOnly = true;

    // Create copy button
    const copyButton = document.createElement("button");
    copyButton.setAttribute("data-action", "copy#copy");
    copyButton.setAttribute("data-copy-target", "button");
    copyButton.className = "absolute right-2" + (isTextarea ? " bottom-2" : " top-[30px]") + " px-3 py-1 text-sm font-semibold text-white bg-pink-600 rounded-md hover:bg-pink-700";
    copyButton.textContent = "Copy";

    // Add elements to the div
    div.appendChild(labelEl);
    div.appendChild(input);
    div.appendChild(copyButton);

    return div;
  }
}
