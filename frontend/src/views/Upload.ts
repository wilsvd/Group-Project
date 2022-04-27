import AbstractView from "./AbstractView";
import { $, html } from "../constants";
import { validateURL, uploadPDF } from "../modules/api";
import { dropHandler, dragOverHandler } from "../modules/drag_drop";
import { isValidPDF } from "../modules/pdf";

export default class extends AbstractView {
  constructor() {
    super();
    this.setTitle("Upload");
  }

  getHtml() {
    return html`
    <div class="tab-contents">
    <h1>Content Visualisation</h1>
    <sl-divider></sl-divider>
        <form id="upload-form">
          <div id="drop-zone">
          <label for="pdfpicker-file">
            <span id="pfdpicker-text-default">
              <a
                id="pdfpicker-link"
                href="javascript:;"
              >
                Click here
              </a>
              or drop your .pdf files here
              </span>
              <span id="pdfpicker-text"></span>
            </label>
            <input
              required
              type="file"
              name="file"
              id="pdfpicker-file"
              accept=".pdf"
              style="display: none"
            />
          </div>
          <div class="tab-contents url-form" required style="display: none">
            <label for="pdfpicker-url"
              >URL :
              <input type="text" id="pdfpicker-url" />
            </label>
          </div>

          <div
            class="tab-contents"
            id="selection-boxes"
            style="display: none"
          ></div>
            <!-- Button below for implementing URL -->
            <input
              class="tab-contents"
              id="url-input"
              type="submit"
              name=""
              value="Upload URL"
              style="display: none"
            />
          </div>
        </form>
      </div>
    `;
  }

  setupListeners() {
    const pdfpickerInput = $("pdfpicker-file") as HTMLInputElement;
    pdfpickerInput.addEventListener(
      "change",
      () => {
        const files = pdfpickerInput.files;
        const pdfPickerSpan = $("pdfpicker-text");
        const defPdfPickerSpan = $("pfdpicker-text-default");
        // checks file exists and passes PDF checks.

        if (files.length > 0 && isValidPDF(files[0])) {
          pdfPickerSpan.innerText = `File accepted: ${files[0].name}`;

          uploadPDF(files[0]);
        } else {
          // throws alert for wrong file type
          pdfpickerInput.value = "";
          pdfPickerSpan.innerText = "File Rejected: Please add .pdf file type";
        }
        pdfPickerSpan.style.display = "block";
        defPdfPickerSpan.style.display = "none";
      },
      false
    );

    // Upload URL
    const urlInput = $("url-input");
    urlInput.addEventListener("click", validateURL);

    // Drophandler
    const dropZone = $("drop-zone");
    dropZone.addEventListener("drop", (ev) => {
      dropHandler(ev);
    });

    dropZone.addEventListener("dragover", (ev) => dragOverHandler(ev));

    const pdfPickerAnchor = $("pdfpicker-link");
    pdfPickerAnchor.addEventListener("click", () => pdfpickerInput.click());
  }
}