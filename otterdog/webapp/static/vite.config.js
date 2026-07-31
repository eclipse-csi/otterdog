import path from "path"
import {defineConfig} from "vite"
import { viteStaticCopy } from 'vite-plugin-static-copy'

const outRootDir = path.join(__dirname, "assets")
const outVendorDir = "vendor"

export default defineConfig({
    root: path.join(__dirname, "./src/"),
    base: "/assets",

    plugins: [
        viteStaticCopy({
            targets: [
                {
                    src: "../node_modules/jquery/dist/jquery.min.js",
                    dest: outVendorDir + "/jquery",
                    rename: {stripBase: true}
                },
                {
                    src: "../node_modules/bootstrap/dist/js/bootstrap.bundle.min.js",
                    dest: outVendorDir + "/bootstrap",
                    rename: {stripBase: true}
                },
                {
                    src: "../node_modules/bootstrap/dist/css/bootstrap.min.css",
                    dest: outVendorDir + "/bootstrap",
                    rename: {stripBase: true}
                },
                {
                    src: "../node_modules/@fortawesome/fontawesome-free/(css|webfonts)/**/*",
                    dest: outVendorDir + "/fontawesome-free",
                    rename: {stripBase: 3}
                },
                {
                    src: "../node_modules/chart.js/dist/chart.umd.js",
                    dest: outVendorDir + "/chartjs",
                    rename: {stripBase: true}
                },
                {
                    src: "../node_modules/jsgrid/dist/jsgrid.min.(js|css)",
                    dest: outVendorDir + "/jsgrid",
                    rename: {stripBase: true}
                },
                {
                    src: "../node_modules/jsgrid/dist/jsgrid-theme.min.css",
                    dest: outVendorDir + "/jsgrid",
                    rename: {stripBase: true}
                },
                {
                    src: "../node_modules/moment/min/moment.min.js",
                    dest: outVendorDir + "/moment",
                    rename: {stripBase: true}
                },
                {
                    src: "../node_modules/datatables.net/js/jquery.dataTables.min.js",
                    dest: outVendorDir + "/datatables",
                    rename: {stripBase: true}
                },
                {
                    src: "../node_modules/datatables.net-bs4/css/dataTables.bootstrap4.min.css",
                    dest: outVendorDir + "/datatables",
                    rename: {stripBase: true}
                },
                {
                    src: "../node_modules/datatables.net-bs4/js/dataTables.bootstrap4.min.js",
                    dest: outVendorDir + "/datatables",
                    rename: {stripBase: true}
                },
                {
                    src: "../node_modules/datatables.net-responsive/js/dataTables.responsive.min.js",
                    dest: outVendorDir + "/datatables",
                    rename: {stripBase: true}
                },
                {
                    src: "../node_modules/datatables.net-responsive-bs4/js/responsive.bootstrap4.min.js",
                    dest: outVendorDir + "/datatables",
                    rename: {stripBase: true}
                },
                {
                    src: "../node_modules/datatables.net-responsive-bs4/css/responsive.bootstrap4.min.css",
                    dest: outVendorDir + "/datatables",
                    rename: {stripBase: true}
                },
                {
                    src: "../node_modules/codemirror-mode-jsonnet",
                    dest: outVendorDir,
                    rename: {stripBase: 1}
                },
                {
                    src: "../node_modules/marked/marked.min.js",
                    dest: outVendorDir + "/marked",
                    rename: {stripBase: true}
                },
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
