import {element, icon} from "./dom.js";

// Returns the description of a function or a property of the default configuration, shown next to the list of
// completions or when hovering its name: {title, type, description, notes, value, source}, source being the object of
// the reference describing it, which it links to.
export function tooltipContent(info, documentationUrl) {
  const content = element("div", "playground-tooltip");
  content.append(...infoContent(info, documentationUrl));
  // keeps the focus in the editor, so that following the link of the description does not close the completions
  content.addEventListener("mousedown", (event) => event.preventDefault());
  return content;
}

function infoContent(info, documentationUrl) {
  const content = [element("div", "playground-tooltip-title", info.title)];
  if (info.type) {
    content.push(element("div", "text-secondary", info.type));
  }
  if (info.description) {
    content.push(withCode(element("div", "mt-1"), info.description));
  }
  if (info.notes) {
    content.push(withCode(element("div", "mt-1 text-secondary"), info.notes));
  }
  if (info.value !== null && info.value !== undefined) {
    content.push(withCode(element("div", "mt-1"), "Default value: `" + info.value + "`"));
  }
  if (info.source) {
    content.push(sourceLink(info.source, documentationUrl));
  }
  return content;
}

// the link to the page of the reference describing the object
function sourceLink(source, documentationUrl) {
  const link = element("a", null, "Reference: " + source.title + " ");
  link.href = documentationUrl + source.url;
  link.target = "_blank";
  link.rel = "noopener";
  link.append(icon("fas fa-arrow-up-right-from-square fa-xs"));
  const container = element("div", "mt-1 playground-tooltip-source");
  container.append(link);
  return container;
}

// a text whose `code` spans are shown as code
function withCode(container, text) {
  text.split(/`([^`]*)`/).forEach((part, index) => container.append(index % 2 === 1 ? element("code", null, part) : part));
  return container;
}
