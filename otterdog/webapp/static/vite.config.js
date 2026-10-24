import path from "path"
import {defineConfig} from "vite"
import { viteStaticCopy } from 'vite-plugin-static-copy'

const outRootDir = path.join(import.meta.dirname, "assets")
const outVendorDir = "vendor"

// Copies vendor file(s) into vendor/<folder>, stripping `stripBase` leading path
// segments from `src` (true flattens to just the basename).
const vendorFile = (src, folder, stripBase = true) => ({
    src: "../node_modules/" + src,
    dest: folder ? outVendorDir + "/" + folder : outVendorDir,
    rename: {stripBase}
})

export default defineConfig({
    root: path.join(import.meta.dirname, "./src/"),
    base: "/assets",

    plugins: [
        viteStaticCopy({
            targets: [
                vendorFile("jquery/dist/jquery.min.js", "jquery"),
                vendorFile("bootstrap/dist/js/bootstrap.bundle.min.js", "bootstrap"),
                vendorFile("chart.js/dist/chart.umd.js", "chartjs"),
                vendorFile("moment/min/moment.min.js", "moment"),
                vendorFile("datatables.net/js/dataTables.min.js", "datatables"),
                vendorFile("datatables.net-bs5/css/dataTables.bootstrap5.min.css", "datatables"),
                vendorFile("datatables.net-bs5/js/dataTables.bootstrap5.min.js", "datatables"),
                vendorFile("datatables.net-responsive/js/dataTables.responsive.min.js", "datatables"),
                vendorFile("datatables.net-responsive-bs5/js/responsive.bootstrap5.min.js", "datatables"),
                vendorFile("datatables.net-responsive-bs5/css/responsive.bootstrap5.min.css", "datatables"),
                vendorFile("marked/lib/marked.umd.js", "marked"),
                // preserves the css/ and webfonts/ subfolders, so strip only the node_modules/@fortawesome/fontawesome-free/ prefix
                vendorFile("@fortawesome/fontawesome-free/(css|webfonts)/**/*", "fontawesome-free", 3),
            ]
        }),
    ],
    css: {
        preprocessorOptions: {
            scss: {
                loadPaths: [path.join(import.meta.dirname, "node_modules")],
                // Bootstrap and AdminLTE still rely on @import and the global Sass functions
                quietDeps: true,
                silenceDeprecations: ["import", "global-builtin", "color-functions", "if-function"],
            },
        },
    },
    resolve: {
        alias: [
            {find: "#", replacement: path.join(import.meta.dirname, "node_modules")},
        ]
    },

    build: {
        minify: true,
        manifest: "manifest.json",
        assetsDir: "bundled",
        outDir: outRootDir,
        emptyOutDir: false,
        // copyPublicDir: false,
        rolldownOptions: {
          preserveEntrySignatures: 'exports-only',
          input: [
            "src/js/app.js",
            "src/js/datagrid.js",
            "src/js/editor.js",
            "src/js/highlight.js",
            "src/js/playground.js",
            "src/css/app.scss",
            "src/css/highlight.css",
            "src/css/playground.css",
          ],
          output: {
            // CodeMirror, used by the GraphQL editor of the query page and by the playground, and GraphQL are split
            // into separate chunks, loaded by the pages and cached independently
            codeSplitting: {
              groups: [
                {
                  name: "codemirror",
                  test: /[\\/]node_modules[\\/](@codemirror|@lezer|codemirror|crelt|style-mod|w3c-keyname)[\\/]/,
                },
                {
                  name: "graphql",
                  test: /[\\/]node_modules[\\/](graphql|graphql-language-service|cm6-graphql|vscode-languageserver-types|nullthrows|picomatch-browser)[\\/]/,
                },
              ],
            },
          },
        },
    }
})
