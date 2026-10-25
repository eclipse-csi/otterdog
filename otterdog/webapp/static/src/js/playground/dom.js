// Helpers creating and updating the elements of the playground.

export const byId = (id) => document.getElementById(id);

export function element(tag, className, text) {
  const result = document.createElement(tag);
  if (className) {
    result.className = className;
  }
  if (text !== undefined) {
    result.textContent = text;
  }
  return result;
}

export function icon(className) {
  const result = element("i", className);
  result.setAttribute("aria-hidden", "true");
  return result;
}

// a link running an action instead of navigating
export function actionLink(text, className, action) {
  const link = element("a", className, text);
  link.href = "#";
  link.addEventListener("click", (event) => {
    event.preventDefault();
    action();
  });
  return link;
}

// marks the current element of a group, e.g. the example shown in the list of examples
export function markCurrent(elements, current) {
  for (const other of elements) {
    other.classList.toggle("active", other === current);
    if (other === current) {
      other.setAttribute("aria-current", "true");
    } else {
      other.removeAttribute("aria-current");
    }
  }
}

// shows a feedback in a button for a while
export function flash(button, iconClass, text) {
  const [iconElement, textElement] = [button.querySelector("i"), button.querySelector("span")];
  const [originalIcon, originalText] = [iconElement.className, textElement.textContent];
  iconElement.className = "fas " + iconClass;
  textElement.textContent = text;
  button.disabled = true;
  setTimeout(() => {
    iconElement.className = originalIcon;
    textElement.textContent = originalText;
    button.disabled = false;
  }, 2000);
}
