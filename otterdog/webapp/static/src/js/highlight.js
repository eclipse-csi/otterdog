import hljs from 'highlight.js/lib/core';
import yaml from 'highlight.js/lib/languages/yaml';

// Then register the languages you need
hljs.registerLanguage('yaml', yaml);
hljs.highlightAll();
