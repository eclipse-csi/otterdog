import { buildSchema } from 'graphql';

import { EditorView, basicSetup } from 'codemirror';
import { graphql } from 'cm6-graphql';

import { codeTheme } from './code-theme.js';

export function createGraphQLEditor(element, schema) {

  // Construct a schema, using GraphQL schema language
  const gqlSchema = buildSchema(schema);

  // basicSetup provides autocompletion (Ctrl-Space) and the lint
  // keymap, graphql() the language, completions and lint source,
  // codeTheme() the colors of the color mode of the page
  const editor = new EditorView({
    doc: element.value,
    extensions: [basicSetup, graphql(gqlSchema), codeTheme()]
  });

  // CodeMirror 6 has no fromTextArea(): replace the textarea with the editor
  element.after(editor.dom);
  element.style.display = 'none';

  return editor;
};
