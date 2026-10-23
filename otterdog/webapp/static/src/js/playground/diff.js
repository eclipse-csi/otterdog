// The changes between two evaluated configurations, and their grouping by section and element of the configuration.

// properties identifying the elements of a list, e.g. the name of a repository or the url of a webhook
const ELEMENT_KEYS = ["name", "pattern", "url", "login", "id"];

// the organization and its settings first, then the other sections in the order of the configuration
const SECTION_RANKS = {"": 0, settings: 1};

export const isObject = (value) => value !== null && typeof value === "object" && !Array.isArray(value);

const isScalar = (value) => value === null || typeof value !== "object";

function isKeyOf(key, elements) {
  const values = elements.map((element) => (isObject(element) ? element[key] : undefined));
  return values.every((value) => typeof value === "string" || typeof value === "number")
    && new Set(values).size === values.length;
}

// Returns the changes from a configuration to another one, as {type: "added" | "removed", segments, path, value} and
// {type: "changed", segments, path, before, after}, the elements of lists being matched by their name, pattern, url, ...
//
// The segments of the path of a change are {name} for a property, {element} for an element of a list, its index for
// lists without key, and {values: true} for a value of a list of values like topics.
export function diffConfigurations(before, after) {
  const changes = [];
  diffValues(before, after, [], changes);
  return changes;
}

export function pathOf(segments) {
  return segments.map((segment, index) => {
    if (segment.name !== undefined) {
      return index === 0 ? segment.name : "." + segment.name;
    }
    return segment.values ? "[]" : "[" + segment.element + "]";
  }).join("");
}

function pushChange(changes, type, segments, values) {
  changes.push({type, segments, path: pathOf(segments), ...values});
}

function diffValues(before, after, segments, changes) {
  if (isObject(before) && isObject(after)) {
    diffEntries(new Map(Object.entries(before)), new Map(Object.entries(after)), (name) => ({name}), segments, changes);
  } else if (Array.isArray(before) && Array.isArray(after)) {
    diffLists(before, after, segments, changes);
  } else if (JSON.stringify(before) !== JSON.stringify(after)) {
    pushChange(changes, "changed", segments, {before, after});
  }
}

// compares entries matched by their key: the properties of objects, the elements of lists by their name, index, ...
function diffEntries(before, after, segmentOf, segments, changes) {
  for (const [key, value] of after) {
    const path = [...segments, segmentOf(key)];
    if (before.has(key)) {
      diffValues(before.get(key), value, path, changes);
    } else {
      pushChange(changes, "added", path, {value});
    }
  }
  for (const [key, value] of before) {
    if (!after.has(key)) {
      pushChange(changes, "removed", [...segments, segmentOf(key)], {value});
    }
  }
}

function diffLists(before, after, segments, changes) {
  if ([...before, ...after].every(isScalar)) {
    diffValueLists(before, after, segments, changes);
    return;
  }

  // elements are matched by their name, pattern, ..., otherwise by their index
  const key = ELEMENT_KEYS.find((k) => isKeyOf(k, before) && isKeyOf(k, after));
  const entriesOf = key === undefined
    ? (list) => new Map(list.entries())
    : (list) => new Map(list.map((element) => [element[key], element]));
  diffEntries(entriesOf(before), entriesOf(after), (element) => ({element}), segments, changes);
}

// lists of values like topics are compared as sets, a different order being a change of the whole list
function diffValueLists(before, after, segments, changes) {
  const previous = before.map((value) => JSON.stringify(value));
  const current = after.map((value) => JSON.stringify(value));
  const added = after.filter((value, index) => !previous.includes(current[index]));
  const removed = before.filter((value, index) => !current.includes(previous[index]));

  const valueSegments = [...segments, {values: true}];
  added.forEach((value) => pushChange(changes, "added", valueSegments, {value}));
  removed.forEach((value) => pushChange(changes, "removed", valueSegments, {value}));
  if (added.length + removed.length === 0 && previous.join() !== current.join()) {
    pushChange(changes, "changed", segments, {before, after});
  }
}

// Groups changes by section of the configuration (settings, repositories, ...) and by element of its lists (a
// repository, a ruleset of a repository, ...), the changes of the properties of an element being its rows.
export function changeTree(changes) {
  const sections = new Map();
  for (const change of changes) {
    const [section, segments] = sectionOf(change.segments);
    if (!sections.has(section)) {
      sections.set(section, newNode("", section));
    }
    addChange(sections.get(section), segments, change);
  }

  const rank = (section) => SECTION_RANKS[section] ?? 2;
  return [...sections.entries()].sort(([a], [b]) => rank(a) - rank(b));
}

const newNode = (kind, label) => ({kind, label, rows: [], change: null, children: new Map()});

// properties of the organization itself, e.g. its name, are grouped in their own section
function sectionOf(segments) {
  return segments.length === 1 ? ["", segments] : [segments[0].name, segments.slice(1)];
}

// adds a change to the node of the element it is part of, the elements of lists being the children of a node
function addChange(node, segments, change) {
  let names = [];
  for (const segment of segments) {
    if (segment.element !== undefined) {
      node = childOf(node, names.join("."), String(segment.element));
      names = [];
    } else if (segment.name !== undefined) {
      names.push(segment.name);
    }
  }

  const key = names.join(".");
  if (key === "" && change.type !== "changed") {
    // an element added or removed as a whole, e.g. a repository
    node.change = change;
  } else {
    node.rows.push({key, change});
  }
}

function childOf(node, kind, label) {
  const id = kind + "[" + label + "]";
  if (!node.children.has(id)) {
    node.children.set(id, newNode(kind, label));
  }
  return node.children.get(id);
}

export function changeCount(node) {
  const own = node.rows.length + (node.change === null ? 0 : 1);
  return [...node.children.values()].reduce((count, child) => count + changeCount(child), own);
}

// the type of the changes of a node, "changed" for different types
export function changeTypeOf(node) {
  if (node.change !== null) {
    return node.change.type;
  }
  const types = new Set(node.rows.map((row) => row.change.type));
  for (const child of node.children.values()) {
    types.add(changeTypeOf(child));
  }
  return types.size === 1 ? [...types][0] : "changed";
}

export function formatValue(value) {
  const text = JSON.stringify(value);
  return text.length > 120 ? text.slice(0, 119) + "…" : text;
}
