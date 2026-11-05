import 'admin-lte';

import { initColorScheme } from './color-scheme.js';

initColorScheme();

// the tooltips of the pages (data-bs-toggle="tooltip"), e.g. the explanations of the cards of the organizations,
// delegated to the body so that the elements added by the scripts have theirs too, e.g. the cards of the projects
// pages copied into a single list (js/projects.js)
new window.bootstrap.Tooltip(document.body, {selector: '[data-bs-toggle="tooltip"]'});
