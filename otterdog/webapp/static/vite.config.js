import path from "path"
import {defineConfig} from "vite"
import { viteStaticCopy } from 'vite-plugin-static-copy'

const outRootDir = path.join(__dirname, "assets")
const outVendorDir = "vendor"

// Copies vendor file(s) into vendor/<folder>, stripping `stripBase` leading path
// segments from `src` (true flattens to just the basename).
const vendorFile = (src, folder, stripBase = true) => ({
    src: "../node_modules/" + src,
    dest: folder ? outVendorDir + "/" + folder : outVendorDir,
    rename: {stripBase}
})

export default defineConfig({
    root: path.join(__dirname, "./src/"),
    base: "/assets",

    plugins: [
        viteStaticCopy({
            targets: [
                vendorFile("jquery/dist/jquery.min.js", "jquery"),
                vendorFile("bootstrap/dist/js/bootstrap.bundle.min.js", "bootstrap"),
                vendorFile("bootstrap/dist/css/bootstrap.min.css", "bootstrap"),
                vendorFile("chart.js/dist/chart.umd.js", "chartjs"),
                vendorFile("jsgrid/dist/jsgrid.min.(js|css)", "jsgrid"),
                vendorFile("jsgrid/dist/jsgrid-theme.min.css", "jsgrid"),
                vendorFile("moment/min/moment.min.js", "moment"),
                vendorFile("datatables.net/js/jquery.dataTables.min.js", "datatables"),
                vendorFile("datatables.net-bs4/css/dataTables.bootstrap4.min.css", "datatables"),
                vendorFile("datatables.net-bs4/js/dataTables.bootstrap4.min.js", "datatables"),
                vendorFile("datatables.net-responsive/js/dataTables.responsive.min.js", "datatables"),
                vendorFile("datatables.net-responsive-bs4/js/responsive.bootstrap4.min.js", "datatables"),
                vendorFile("datatables.net-responsive-bs4/css/responsive.bootstrap4.min.css", "datatables"),
                vendorFile("marked/marked.min.js", "marked"),
                // preserves the css/ and webfonts/ subfolders, so strip only the node_modules/@fortawesome/fontawesome-free/ prefix
                vendorFile("@fortawesome/fontawesome-free/(css|webfonts)/**/*", "fontawesome-free", 3),
                // preserves the package's internal directory structure, so strip only the node_modules/ prefix
                vendorFile("codemirror-mode-jsonnet", null, 1),
            ]
        }),
    ],
    resolve: {
        alias: [
            {find: "#", replacement: path.join(__dirname, "node_modules")},
        ]
    },

    build: {
        minify: true,
        manifest: "manifest.json",
        assetsDir: "bundled",
        outDir: outRootDir,
        emptyOutDir: false,
        // copyPublicDir: false,
        rollupOptions: {
          preserveEntrySignatures: 'exports-only',
          input: [
            "src/js/app.js",
            "src/js/editor.js",
            "src/js/highlight.js",
            "src/css/app.css",
            "src/css/editor.css",
            "src/css/highlight.css",
          ],
        },
    }
})
