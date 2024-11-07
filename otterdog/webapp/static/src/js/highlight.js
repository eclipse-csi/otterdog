import hljs from 'highlight.js/lib/core';
import yaml from 'highlight.js/lib/languages/yaml';
import json from 'highlight.js/lib/languages/json';

// Then register the languages you need
hljs.registerLanguage('yaml', yaml);
hljs.registerLanguage('json', json);
hljs.highlightAll();
