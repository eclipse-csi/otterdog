import { buildSchema } from 'graphql';

import CodeMirror from 'codemirror';
import 'codemirror/addon/hint/show-hint';
import 'codemirror/addon/lint/lint';
import 'codemirror/mode/javascript/javascript';
import 'codemirror-graphql/hint';
import 'codemirror-graphql/lint';
import 'codemirror-graphql/mode';

export function createGraphQLEditor(element, schema) {

  // Construct a schema, using GraphQL schema language
  var gqlSchema = buildSchema(schema);

  CodeMirror.commands.autocomplete = function(cm) {
    CodeMirror.showHint(cm, CodeMirror.hint.graphql);
  };

  var editor = CodeMirror.fromTextArea(element, {
    mode: 'graphql',
    lint: {
      schema: gqlSchema
    },
    hintOptions: {
      schema: gqlSchema
    },
    extraKeys: {"Ctrl-Space": "autocomplete"}
  });

  return editor;
};

export function createJavascriptEditor(element) {
  var editor = CodeMirror.fromTextArea(element, {
    mode: 'javascript',
    lineWrapping: true,
    readOnly: true
  });

  return editor;
};
