// Tables paged, sorted and filtered server side by the paged endpoints of the api (/api/tasks, ...).
//
// These endpoints take the parameters of jsGrid, which rendered these tables before:
// pageIndex, pageSize, sortField, sortOrder and the value of each filter keyed by its field,
// a nested field like id.org_id being sent as id[org_id]. They return {data, itemsCount, totalCount},
// itemsCount being the number of items matching the filters and totalCount the one without filters.
//
// DataTables is loaded as a vendor script by the pages using this module.

const DataTable = window.DataTable;

const FILTER_DELAY = 400;

export const escapeHtml = (value) => DataTable.util.escapeHtml(String(value));

// renders the cell of a column with the given function, the raw value being kept for
// anything else than display (e.g. the type detection of DataTables)
export function display(render) {
  return (value, type, row) => (type === "display" ? render(value, row) : value);
}

export const checkbox = display((value) =>
  '<input class="form-check-input" type="checkbox" disabled' + (value ? " checked" : "") + ">"
);

const parameterName = (field) => field.replace(/\.([^.]+)/g, "[$1]");

function loadPage(url, columns) {
  return (request, callback) => {
    const params = new URLSearchParams({
      pageIndex: Math.floor(request.start / request.length) + 1,
      pageSize: request.length,
    });

    // without any order, the endpoint applies its default one
    if (request.order.length > 0) {
      params.set("sortField", columns[request.order[0].column].data);
      params.set("sortOrder", request.order[0].dir);
    }

    request.columns.forEach((column, index) => {
      if (column.search.value) {
        params.set(parameterName(columns[index].data), column.search.value);
      }
    });

    const draw = (data, count, total) =>
      callback({ draw: request.draw, data: data, recordsTotal: total, recordsFiltered: count });

    fetch(url + "?" + params)
      .then((response) => {
        if (!response.ok) {
          throw new Error(response.status + " " + response.statusText);
        }
        return response.json();
      })
      .then((response) => draw(response.data, response.itemsCount, response.totalCount))
      .catch((error) => {
        console.error("failed to load '" + url + "':", error);
        draw([], 0, 0);
      });
  };
}

function filterControl(column) {
  let control;

  switch (column.filter) {
    case "text":
    case "number":
      control = document.createElement("input");
      control.type = column.filter === "text" ? "search" : "number";
      control.className = "form-control form-control-sm";
      break;

    case "boolean":
      control = document.createElement("select");
      control.className = "form-select form-select-sm";
      control.add(new Option("", ""));
      control.add(new Option("Yes", "true"));
      control.add(new Option("No", "false"));
      break;

    default:
      return null;
  }

  control.setAttribute("aria-label", "Filter by " + column.title);
  return control;
}

// adds a row with the filter of each column below their title
function addFilterRow(table, columns) {
  const header = table.createTHead();
  const titles = header.insertRow();
  const filters = header.insertRow();

  return columns.map((column) => {
    titles.appendChild(document.createElement("th"));

    const cell = document.createElement("th");
    cell.dataset.dtOrder = "disable";
    filters.appendChild(cell);

    const control = filterControl(column);
    if (control) {
      cell.appendChild(control);
    }
    return control;
  });
}

export function createPagedTable(selector, { url, columns, ...options }) {
  const table = document.querySelector(selector);
  const controls = addFilterRow(table, columns);

  const api = new DataTable(table, {
    serverSide: true,
    processing: true,
    ajax: loadPage(url, columns),
    columns: columns.map(({ filter, ...column }) => column),
    // plain values are escaped, columns with a render function take care of it themselves
    columnDefs: [{ targets: "_all", render: DataTable.render.text(), defaultContent: "" }],
    // the titles go into the first row of the header, the filters stay in the second one
    titleRow: 0,
    order: [],
    pageLength: 20,
    lengthMenu: [10, 20, 50, 100],
    // the endpoints only support filtering by column, there is no global search
    layout: { topEnd: null },
    autoWidth: false,
    ...options,
  });

  controls.forEach((control, index) => {
    if (!control) {
      return;
    }

    const search = () => api.column(index).search(control.value).draw();
    if (control.tagName === "SELECT") {
      control.addEventListener("change", search);
    } else {
      // reload once the typing stops rather than on every key stroke
      control.addEventListener("input", DataTable.util.debounce(search, FILTER_DELAY));
    }
  });

  return api;
}
