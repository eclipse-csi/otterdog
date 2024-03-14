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
                    dest: outVendorDir + "/jquery"
                },
                {
                    src: "../node_modules/bootstrap/dist/js/bootstrap.bundle.min.js",
                    dest: outVendorDir + "/bootstrap"
                },
                {
                    src: "../node_modules/bootstrap/dist/css/bootstrap.min.css",
                    dest: outVendorDir + "/bootstrap"
                },
                {
                    src: "../node_modules/@fortawesome/fontawesome-free/(css|webfonts)/",
                    dest: outVendorDir + "/fontawesome-free"
                },
                {
                    src: "../node_modules/chart.js/dist/chart.umd.js",
                    dest: outVendorDir + "/chartjs"
                },
                {
                    src: "../node_modules/jsgrid/dist/jsgrid.min.(js|css)",
                    dest: outVendorDir + "/jsgrid"
                },
                {
                    src: "../node_modules/jsgrid/dist/jsgrid-theme.min.css",
                    dest: outVendorDir + "/jsgrid"
                },
                {
                    src: "../node_modules/moment/min/moment.min.js",
                    dest: outVendorDir + "/moment"
                },
                {
                    src: "../node_modules/datatables.net/js/jquery.dataTables.min.js",
                    dest: outVendorDir + "/datatables"
                },
                {
                    src: "../node_modules/datatables.net-bs4/css/dataTables.bootstrap4.min.css",
                    dest: outVendorDir + "/datatables"
                },
                {
                    src: "../node_modules/datatables.net-bs4/js/dataTables.bootstrap4.min.js",
                    dest: outVendorDir + "/datatables"
                },
                {
                    src: "../node_modules/datatables.net-responsive/js/dataTables.responsive.min.js",
                    dest: outVendorDir + "/datatables"
                },
                {
                    src: "../node_modules/datatables.net-responsive-bs4/js/responsive.bootstrap4.min.js",
                    dest: outVendorDir + "/datatables"
                },
                {
                    src: "../node_modules/datatables.net-responsive-bs4/css/responsive.bootstrap4.min.css",
                    dest: outVendorDir + "/datatables"
                }
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
            "src/css/app.css",
            "src/css/editor.css"
          ],
        },
    }
})
